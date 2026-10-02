"""Async HTTP client for the Suno music generation API.

Handles task submission, status polling, lyrics generation, and credit balance
retrieval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from platform_api.config import Settings
from platform_api.exceptions import ExternalServiceError
from platform_api.services.suno_status_messages import (
    is_suno_failure_status,
    is_suno_pending_status,
    is_suno_success_status,
    suno_submit_error_message,
    suno_task_failure_message,
)

logger = logging.getLogger(__name__)

# Timeout for Suno API requests (seconds)
_SUNO_TIMEOUT = 30.0
_SUNO_LYRICS_POLL_INTERVAL_SECONDS = 2.0
_SUNO_LYRICS_MAX_WAIT_SECONDS = 120.0

SunoLyricsPollState = Literal["pending", "success", "failed"]
SunoGeneratePollState = Literal["pending", "success", "failed"]


@dataclass(frozen=True)
class SunoGeneratePollResult:
    """Parsed state from GET /api/v1/generate/record-info."""

    state: SunoGeneratePollState
    audio_url_ok: str = ""
    audio_url_alt: str = ""
    image_url_ok: str = ""
    image_url_alt: str = ""
    duration_ok: float | None = None
    duration_alt: float | None = None
    tags_ok: str = ""
    tags_alt: str = ""
    audio_id_ok: str = ""
    audio_id_alt: str = ""
    error: str = ""


@dataclass(frozen=True)
class SunoLyricsPollResult:
    """Parsed state from GET /api/v1/lyrics/record-info."""

    state: SunoLyricsPollState
    text: str = ""
    title: str = ""
    error: str = ""


def extract_suno_lyrics_task_id(response: dict[str, Any]) -> str:
    """Return taskId from POST /api/v1/lyrics response."""
    code = int(response.get("code", 0) or 0)
    if code != 200:
        raise ExternalServiceError(
            suno_submit_error_message(code=code, msg=response.get("msg", ""), context="lyrics"),
            is_retryable=code in {429, 430, 500, 455},
            details={"provider": "suno", "reason": "lyrics_submit_failed", "code": code},
        )
    data = response.get("data")
    task_id = str(data.get("taskId", "")).strip() if isinstance(data, dict) else ""
    if not task_id:
        raise ExternalServiceError(
            "Suno lyrics submit returned empty taskId.",
            is_retryable=False,
            details={"provider": "suno", "reason": "missing_task_id"},
        )
    return task_id


def _coerce_task_id(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value).strip()
    return str(value).strip()


def _task_id_from_mapping(payload: dict[str, Any]) -> str:
    for key in ("taskId", "task_id", "id"):
        task_id = _coerce_task_id(payload.get(key))
        if task_id:
            return task_id
    nested = payload.get("response")
    if isinstance(nested, dict):
        for key in ("taskId", "task_id", "id"):
            task_id = _coerce_task_id(nested.get(key))
            if task_id:
                return task_id
    return ""


def extract_suno_generate_task_id(response: dict[str, Any]) -> str:
    """Return taskId from POST /api/v1/generate response."""
    flat_task_id = _coerce_task_id(response.get("taskId") or response.get("task_id"))
    if flat_task_id and "code" not in response:
        return flat_task_id

    code = int(response.get("code", 0) or 0)
    if code != 200:
        raise ExternalServiceError(
            suno_submit_error_message(code=code, msg=response.get("msg", ""), context="generate"),
            is_retryable=code in {429, 430, 455, 500},
            details={"provider": "suno", "reason": "generate_submit_failed", "code": code},
        )

    data = response.get("data")
    if isinstance(data, dict):
        task_id = _task_id_from_mapping(data)
        if task_id:
            return task_id
    elif isinstance(data, str):
        task_id = data.strip()
        if task_id:
            return task_id

    if flat_task_id:
        return flat_task_id

    api_message = str(response.get("msg", "")).strip()
    raise ExternalServiceError(
        api_message or "Suno generate returned empty taskId.",
        is_retryable=False,
        details={
            "provider": "suno",
            "reason": "missing_task_id",
            "response": str(response)[:500],
        },
    )


def parse_suno_lyrics_poll(response: dict[str, Any]) -> SunoLyricsPollResult:
    """Parse GET /api/v1/lyrics/record-info into pending/success/failed."""
    code = int(response.get("code", 0) or 0)
    if code != 200:
        return SunoLyricsPollResult(
            state="failed",
            error=suno_task_failure_message(api_code=code, api_msg=response.get("msg", "")),
        )

    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    status = str(data.get("status", "")).strip().upper()
    if is_suno_pending_status(status):
        return SunoLyricsPollResult(state="pending")

    if status != "SUCCESS":
        error_message = str(data.get("errorMessage", "")).strip()
        return SunoLyricsPollResult(
            state="failed",
            error=suno_task_failure_message(
                status=status,
                error_message=error_message,
            ),
        )

    response_block = data.get("response") if isinstance(data.get("response"), dict) else {}
    variants = response_block.get("data") if isinstance(response_block.get("data"), list) else []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        text = str(variant.get("text", "")).strip()
        title = str(variant.get("title", "")).strip()
        variant_status = str(variant.get("status", "")).strip().lower()
        if text and (not variant_status or variant_status == "complete"):
            return SunoLyricsPollResult(state="success", text=text, title=title)

    return SunoLyricsPollResult(
        state="failed",
        error="Suno lyrics returned no completed variants.",
    )


def _extract_clip_download_url(clip: dict[str, Any]) -> str:
    """Return the best URL for downloading a finished MP3 (not stream preview).

    Prefer callback/record-info download links. Suno documents both
    ``audioUrl`` (camelCase, live callbacks) and ``audio_url`` (snake_case,
    generate-complete docs). Either is accepted; ``source_audio_url`` is the
    unsigned ``cdn1.suno.ai/{id}.mp3`` link, which CloudFront rejects with
    MissingKey unless a Key-Pair-Id is present.
    """
    from platform_api.services.suno_audio_resolver import is_disallowed_suno_audio_url

    audio_id = _extract_clip_audio_id(clip)
    primary = ""
    for key in (
        "audioUrl",
        "audio_url",
        "sourceAudioUrl",
        "source_audio_url",
    ):
        url = str(clip.get(key, "")).strip()
        if url and not is_disallowed_suno_audio_url(url):
            primary = prefer_suno_mpeg_cdn_url(url, audio_id)
            break
    # Reseller hosts (sunoapi.org / apibox) return the short-lived
    # ``tempfile.aiquickdraw.com`` link as ``audio_url`` and the durable
    # ``audiostream.api.box`` link as ``stream_audio_url``. The temp link is
    # purged within hours, so prefer the stream host when we see it.
    if "tempfile.aiquickdraw.com" in primary:
        for key in (
            "source_stream_audio_url",
            "sourceStreamAudioUrl",
            "stream_audio_url",
            "streamAudioUrl",
        ):
            url = str(clip.get(key, "")).strip()
            if url and not is_disallowed_suno_audio_url(url):
                return url
    if primary:
        return primary
    # Callback only carried rejected hosts (e.g. musicfile cover JPEG) or no
    # usable URL. The finished MP3 lives on the tempfile host keyed by clip id.
    # Same id => no new Suno generation/charge.
    if audio_id:
        return tempfile_url_for_suno_audio_id(audio_id)
    return ""


def _extract_clip_image_url(clip: dict[str, Any]) -> str:
    for key in (
        "image_url",
        "imageUrl",
        "source_image_url",
        "sourceImageUrl",
        "cover_url",
        "coverUrl",
    ):
        url = str(clip.get(key, "")).strip()
        if url:
            return url
    return ""


def _extract_clip_duration(clip: dict[str, Any]) -> float | None:
    for key in ("duration", "audio_duration", "audioDuration"):
        raw = clip.get(key)
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _extract_clip_tags(clip: dict[str, Any]) -> str:
    tags = clip.get("tags")
    if isinstance(tags, str):
        return tags.strip()
    if isinstance(tags, list):
        return ", ".join(str(item).strip() for item in tags if str(item).strip())
    return str(clip.get("style", "") or "").strip()


def _extract_clip_audio_id(clip: dict[str, Any]) -> str:
    """Return Suno clip id used as audioId for timestamped lyrics."""
    for key in ("id", "audioId", "audio_id", "clip_id", "clipId"):
        value = str(clip.get(key) or "").strip()
        if value:
            return value
    return ""


_SUNO_CDN_HOST_MARKERS = ("cdn1.suno.ai", "cdn2.suno.ai", "cdn.suno.ai")
_SIGNED_CDN_QUERY_MARKERS = ("key-pair-id=", "signature=", "policy=")
_TEMPFILE_AUDIO_PREFIX = "https://tempfile.aiquickdraw.com/r/"
_NON_MPEG_CDN_SUFFIXES = (".m4a", ".mp4", ".webm", ".opus", ".aac")
# Reseller "durable" stream host. It now answers 200 audio/mpeg with a 0-byte
# body, so it must be rewritten to the working ``tempfile`` sibling (same clip id).
_STREAM_HOST_MARKER = "audiostream.api.box"


def _stream_host_clip_id(url: str) -> str:
    """Clip id from ``audiostream.api.box/stream/<id>.mp3`` ('' when absent)."""
    from urllib.parse import urlsplit

    name = (urlsplit(str(url or "")).path or "").rstrip("/").rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name.strip()


def _suno_cdn_clip_id(url: str) -> str:
    from urllib.parse import unquote, urlsplit

    name = unquote(urlsplit(str(url or "")).path or "").rsplit("/", 1)[-1].strip()
    if not name:
        return ""
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name.strip()


def is_unsigned_suno_cdn_url(url: str | None) -> bool:
    """True for CloudFront-blocked ``cdn*.suno.ai`` links (no signed query)."""
    from urllib.parse import urlsplit

    text = str(url or "").strip()
    if not text.startswith(("http://", "https://")):
        return False
    parts = urlsplit(text)
    host = (parts.netloc or "").lower()
    if not any(marker in host for marker in _SUNO_CDN_HOST_MARKERS):
        return False
    query = (parts.query or "").lower()
    return not any(marker in query for marker in _SIGNED_CDN_QUERY_MARKERS)


def tempfile_url_for_suno_audio_id(audio_id: str | None) -> str:
    """Working download host for a Suno clip id (unsigned CDN returns 403)."""
    value = str(audio_id or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return prefer_suno_mpeg_cdn_url(value)
    return f"{_TEMPFILE_AUDIO_PREFIX}{value}.mp3"


def cdn_url_for_suno_audio_id(audio_id: str | None) -> str:
    """Download URL from a clip/audio id when callbacks omit ``audio_url_*``.

    Unsigned ``cdn1.suno.ai/{id}.mp3`` is CloudFront MissingKey. The tempfile
    path ``/r/{id}.mp3`` is the working sibling used in live callbacks.
    """
    return tempfile_url_for_suno_audio_id(audio_id)


def prefer_suno_mpeg_cdn_url(url: str, audio_id: str | None = None) -> str:
    """Prefer a downloadable MPEG URL. Unsigned Suno CDN is rewritten to tempfile.

    Studio download always wants the MP3. Same clip id; no extra generate.
    """
    from urllib.parse import urlsplit, urlunsplit

    text = str(url or "").strip()
    if not text.startswith(("http://", "https://")):
        return tempfile_url_for_suno_audio_id(audio_id)
    if _STREAM_HOST_MARKER in (urlsplit(text).netloc or "").lower():
        # The stream host is dead (empty 200s). Use the real-MP3 sibling keyed by
        # the same clip id so existing rows and fresh callbacks stay downloadable.
        clip = str(audio_id or "").strip()
        if not clip or clip.startswith(("http://", "https://")):
            clip = _stream_host_clip_id(text)
        sibling = tempfile_url_for_suno_audio_id(clip)
        return sibling or text
    if is_unsigned_suno_cdn_url(text):
        clip = str(audio_id or "").strip()
        if not clip or clip.startswith(("http://", "https://")):
            clip = _suno_cdn_clip_id(text)
        guessed = tempfile_url_for_suno_audio_id(clip)
        if guessed:
            return guessed
    lower = text.lower()
    if lower.endswith(".mp3") or ".mp3?" in lower:
        return text
    parts = urlsplit(text)
    host = (parts.netloc or "").lower()
    if not any(marker in host for marker in _SUNO_CDN_HOST_MARKERS):
        return text
    path = parts.path or ""
    path_lower = path.lower()
    for suffix in _NON_MPEG_CDN_SUFFIXES:
        if path_lower.endswith(suffix):
            new_path = path[: -len(suffix)] + ".mp3"
            return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))
    clip_id = str(audio_id or "").strip()
    if clip_id and not clip_id.startswith(("http://", "https://")):
        return tempfile_url_for_suno_audio_id(clip_id)
    return text


_MIN_MPEG_SNIFF_BYTES = 256


def payload_is_mpeg_audio(content: bytes) -> bool:
    """True when bytes look like MP3 (ID3 or MPEG frame), not MP4/M4A/Opus."""
    if not content or len(content) < _MIN_MPEG_SNIFF_BYTES:
        return False
    if content[4:8] == b"ftyp":
        return False
    if content[:3] == b"ID3":
        return True
    if content[0] == 0xFF and (content[1] & 0xE0) == 0xE0 and (content[1] & 0xF6) != 0xF0:
        return True
    return False


def coerce_suno_download_url(*, url: str | None = None, audio_id: str | None = None) -> str:
    """Prefer a downloadable http(s) URL; unsigned Suno CDN becomes tempfile.

    Suno CDN ``.m4a`` links are rewritten to MPEG so the desktop never
    saves Opus-in-MP4 under an ``*_OK.mp3`` name.
    """
    text = str(url or "").strip()
    if text.startswith(("http://", "https://")):
        return prefer_suno_mpeg_cdn_url(text, audio_id)
    return tempfile_url_for_suno_audio_id(audio_id)


def _clip_metadata(clip: dict[str, Any]) -> tuple[str, str, float | None, str, str]:
    return (
        _extract_clip_audio_url(clip),
        _extract_clip_image_url(clip),
        _extract_clip_duration(clip),
        _extract_clip_tags(clip),
        _extract_clip_audio_id(clip),
    )


def _extract_clip_audio_url(clip: dict[str, Any]) -> str:
    download_url = _extract_clip_download_url(clip)
    if download_url:
        return download_url
    for key in (
        "stream_audio_url",
        "streamAudioUrl",
        "source_stream_audio_url",
        "sourceStreamAudioUrl",
    ):
        url = str(clip.get(key, "")).strip()
        if url:
            return url
    return ""


def _iter_generate_clips(data: dict[str, Any]) -> list[dict[str, Any]]:
    clips: list[dict[str, Any]] = []
    response_block = data.get("response")
    if isinstance(response_block, dict):
        nested = response_block.get("data")
        if isinstance(nested, list):
            clips.extend(item for item in nested if isinstance(item, dict))
        suno_data = response_block.get("sunoData")
        if isinstance(suno_data, list):
            clips.extend(item for item in suno_data if isinstance(item, dict))
    direct = data.get("data")
    if isinstance(direct, list):
        clips.extend(item for item in direct if isinstance(item, dict))
    return clips


def parse_suno_generate_poll(response: dict[str, Any]) -> SunoGeneratePollResult:
    """Parse GET /api/v1/generate/record-info into pending/success/failed."""
    code = int(response.get("code", 0) or 0)
    if code != 200:
        return SunoGeneratePollResult(
            state="failed",
            error=suno_task_failure_message(api_code=code, api_msg=response.get("msg", "")),
        )

    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    status = str(data.get("status", "")).strip().upper()
    error_message = str(data.get("errorMessage", "")).strip()
    clips = _iter_generate_clips(data)
    audio_urls: list[str] = []
    image_urls: list[str] = []
    durations: list[float | None] = []
    tags: list[str] = []
    audio_ids: list[str] = []
    for clip in clips:
        audio_url, image_url, duration, clip_tags, audio_id = _clip_metadata(clip)
        # Keep clips that only have an id (URL arrives later / CDN synthesize).
        if not audio_url:
            audio_url = cdn_url_for_suno_audio_id(audio_id)
        if not audio_url and not audio_id:
            continue
        if not audio_url:
            continue
        audio_urls.append(audio_url)
        image_urls.append(image_url)
        durations.append(duration)
        tags.append(clip_tags)
        audio_ids.append(audio_id)

    if audio_urls:
        return SunoGeneratePollResult(
            state="success",
            audio_url_ok=audio_urls[0],
            audio_url_alt=audio_urls[1] if len(audio_urls) > 1 else "",
            image_url_ok=image_urls[0] if image_urls else "",
            image_url_alt=image_urls[1] if len(image_urls) > 1 else "",
            duration_ok=durations[0] if durations else None,
            duration_alt=durations[1] if len(durations) > 1 else None,
            tags_ok=tags[0] if tags else "",
            tags_alt=tags[1] if len(tags) > 1 else "",
            audio_id_ok=audio_ids[0] if audio_ids else "",
            audio_id_alt=audio_ids[1] if len(audio_ids) > 1 else "",
        )

    if is_suno_failure_status(status):
        return SunoGeneratePollResult(
            state="failed",
            error=suno_task_failure_message(status=status, error_message=error_message),
        )

    if is_suno_pending_status(status):
        return SunoGeneratePollResult(state="pending")

    if is_suno_success_status(status):
        return SunoGeneratePollResult(
            state="failed",
            error="Suno reported success but returned no audio URLs.",
        )

    return SunoGeneratePollResult(
        state="failed",
        error=suno_task_failure_message(status=status, error_message=error_message),
    )


def _suno_api_code(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    raw = payload.get("code", 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _extract_suno_wav_url(data: dict[str, Any]) -> str | None:
    for key in ("audioWavUrl", "wavUrl", "audio_wav_url", "wav_url", "url"):
        url = str(data.get(key) or "").strip()
        if url.startswith("http"):
            return url
    nested = data.get("response")
    if isinstance(nested, dict):
        for key in ("audioWavUrl", "wavUrl", "audio_wav_url", "wav_url", "url"):
            url = str(nested.get(key) or "").strip()
            if url.startswith("http"):
                return url
    return None


def extract_suno_wav_task_id(response: dict[str, Any]) -> str:
    """Return taskId from POST /api/v1/wav/generate response."""
    if not isinstance(response, dict):
        raise ExternalServiceError(
            "Suno WAV submit returned an invalid response.",
            is_retryable=True,
            details={"provider": "suno", "reason": "invalid_wav_submit"},
        )
    code = _suno_api_code(response)
    if code == 409:
        # A WAV record already exists for this (taskId, audioId): reuse the
        # existing WAV task id so we can poll/upload it instead of failing.
        data = response.get("data")
        if isinstance(data, dict):
            task_id = _task_id_from_mapping(data)
            if task_id:
                return task_id
        raise ExternalServiceError(
            "Suno WAV record already exists but no existing taskId returned.",
            is_retryable=False,
            details={"provider": "suno", "reason": "wav_already_exists"},
        )
    if code != 200:
        raise ExternalServiceError(
            suno_submit_error_message(code=code, msg=response.get("msg", ""), context="wav_generate"),
            is_retryable=code in {429, 430, 455, 500} or code == 0,
            details={"provider": "suno", "reason": "wav_submit_failed", "code": code},
        )
    data = response.get("data")
    if isinstance(data, dict):
        task_id = _task_id_from_mapping(data)
        if task_id:
            return task_id
    task_id = _coerce_task_id(response.get("taskId") or response.get("task_id"))
    if task_id:
        return task_id
    raise ExternalServiceError(
        "Suno WAV submit returned empty taskId.",
        is_retryable=False,
        details={"provider": "suno", "reason": "missing_wav_task_id"},
    )


def parse_suno_wav_poll(response: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Parse GET /api/v1/wav/record-info response.

    Returns:
        Tuple of (status, wav_url, error_message).
        Status is one of: pending, success, failed.
    """
    if not isinstance(response, dict):
        return ("pending", None, None)
    code = _suno_api_code(response)
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    status = str(data.get("status", "")).strip().upper()
    error_message = str(data.get("errorMessage") or data.get("error") or "").strip()
    wav_url = _extract_suno_wav_url(data) or _extract_suno_wav_url(response)

    if wav_url and (code == 200 or is_suno_success_status(status) or not status):
        return ("success", wav_url, None)
    if is_suno_failure_status(status):
        return (
            "failed",
            None,
            suno_task_failure_message(status=status, error_message=error_message),
        )
    if is_suno_success_status(status):
        if wav_url:
            return ("success", wav_url, None)
        return ("pending", None, None)
    # Non-200 / not-found / still processing: keep waiting. Do not mark failed.
    return ("pending", None, None)


def _classify_error(exc: Exception, *, context: str = "") -> ExternalServiceError:
    """Convert an httpx exception or HTTP error response into an ExternalServiceError.

    Retryable: timeouts, rate limits (429), 5xx server errors.
    Permanent: 4xx client errors (except 429).
    """
    if isinstance(exc, httpx.TimeoutException):
        return ExternalServiceError(
            f"Suno API timeout: {context}",
            is_retryable=True,
            details={"provider": "suno", "reason": "timeout"},
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        is_retryable = status == 429 or status >= 500
        return ExternalServiceError(
            f"Suno API error {status}: {context}",
            is_retryable=is_retryable,
            details={
                "provider": "suno",
                "status_code": status,
                "reason": exc.response.text[:500] if exc.response.text else "",
            },
        )

    # Network-level failures (DNS, connection reset, etc.) are retryable
    return ExternalServiceError(
        f"Suno API connection error: {context} - {exc}",
        is_retryable=True,
        details={"provider": "suno", "reason": "connection_error"},
    )


class SunoClient:
    """Async client for the Suno music generation API."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.suno_api_base_url.rstrip("/")
        self._callback_base_url = settings.suno_callback_base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            timeout=float(settings.suno_timeout_seconds),
            connect=10.0,
        )

    def _build_client(self, api_key: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        """No persistent client — kept for lifecycle compatibility."""
        return

    async def submit_task(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool = False,
        callback_url: str | None = None,
        api_key: str | None = None,
        negative_tags: str | None = None,
        vocal_gender: str | None = None,
        style_weight: float | None = None,
        weirdness_constraint: float | None = None,
        audio_weight: float | None = None,
    ) -> dict[str, Any]:
        """Submit a music generation task to Suno.

        Args:
            model: Suno model version (e.g. "V6", "V6_MINI", "V6_WILD").
            title: Song title.
            lyrics: Song lyrics.
            style: Music style/genre descriptor.
            instrumental: Whether to generate an instrumental track.
            callback_url: URL for Suno to notify on completion.
            negative_tags: Comma-separated styles to avoid.
            vocal_gender: Preferred vocal gender ('m' or 'f').
            style_weight: Style adherence weight (0.0-1.0).
            weirdness_constraint: Creativity/novelty constraint (0.0-1.0).
            audio_weight: Audio consistency weight (0.0-1.0).

        Returns:
            Response dict from Suno containing the task ID and status.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )

        normalized_title = str(title or "").strip()
        normalized_lyrics = str(lyrics or "").strip()
        normalized_style = str(style or "").strip() or "Contemporary pop"
        if not normalized_title:
            raise ExternalServiceError(
                "Suno requires a song title in custom mode.",
                is_retryable=False,
                details={"provider": "suno", "reason": "missing_title"},
            )
        if not instrumental and not normalized_lyrics:
            raise ExternalServiceError(
                "Suno requires lyrics in custom mode.",
                is_retryable=False,
                details={"provider": "suno", "reason": "missing_lyrics"},
            )

        callback = str(callback_url or "").strip()
        if not callback:
            if self._callback_base_url:
                callback = f"{self._callback_base_url}/api/v3/callbacks/suno"
            else:
                callback = "https://localhost/api/v3/callbacks/suno"

        payload: dict[str, Any] = {
            "model": model,
            "title": normalized_title,
            "prompt": normalized_lyrics,
            "style": normalized_style,
            "instrumental": instrumental,
            "customMode": True,
            "callBackUrl": callback,
        }

        # V6 exposes a dedicated ``lyrics`` field that takes priority over
        # ``prompt`` in custom mode. Send both so V6 sings the exact lyrics.
        if str(model or "").strip().upper().startswith("V6"):
            payload["lyrics"] = normalized_lyrics

        if negative_tags:
            payload["negativeTags"] = str(negative_tags).strip()
        if vocal_gender and vocal_gender.lower() in ("m", "f"):
            payload["vocalGender"] = vocal_gender.lower()
        if style_weight is not None and 0 <= style_weight <= 1:
            payload["styleWeight"] = round(float(style_weight), 2)
        if weirdness_constraint is not None and 0 <= weirdness_constraint <= 1:
            payload["weirdnessConstraint"] = round(float(weirdness_constraint), 2)
        if audio_weight is not None and 0 <= audio_weight <= 1:
            payload["audioWeight"] = round(float(audio_weight), 2)

        client = self._build_client(api_key)
        try:
            response = await client.post("/api/v1/generate", json=payload)
            response.raise_for_status()
            body = response.json()
            task_id = extract_suno_generate_task_id(body)
            return {"taskId": task_id, "code": body.get("code", 200), "data": body.get("data")}
        except ExternalServiceError as exc:
            if exc.details.get("reason") == "missing_task_id":
                logger.warning("Suno generate response missing taskId: %s", exc.details.get("response"))
            raise
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="submit_task") from exc
        finally:
            await client.aclose()

    async def check_status(self, task_id: str, *, api_key: str | None = None) -> dict[str, Any]:
        """Check the status of a previously submitted Suno task.

        Args:
            task_id: The Suno-assigned task identifier.

        Returns:
            Response dict with task status, audio URLs (if complete), etc.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        client = self._build_client(api_key)
        try:
            response = await client.get("/api/v1/generate/record-info", params={"taskId": task_id})
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context=f"check_status({task_id})") from exc
        finally:
            await client.aclose()

    async def get_timestamped_lyrics(
        self,
        *,
        task_id: str,
        audio_id: str,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Fetch word-aligned lyrics for a generated clip (karaoke timestamps).

        POST /api/v1/generate/get-timestamped-lyrics
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        normalized_task = str(task_id or "").strip()
        normalized_audio = str(audio_id or "").strip()
        if not normalized_task or not normalized_audio:
            raise ExternalServiceError(
                "Suno timestamped lyrics require taskId and audioId.",
                is_retryable=False,
                details={"provider": "suno", "reason": "missing_ids"},
            )
        client = self._build_client(api_key)
        try:
            response = await client.post(
                "/api/v1/generate/get-timestamped-lyrics",
                json={"taskId": normalized_task, "audioId": normalized_audio},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(
                exc,
                context=f"get_timestamped_lyrics({normalized_task})",
            ) from exc
        finally:
            await client.aclose()

    async def get_credit_balance(self, *, api_key: str | None = None) -> dict[str, Any]:
        """Retrieve the current Suno API credit balance.

        Returns:
            Response dict containing the credit balance information.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        client = self._build_client(api_key)
        try:
            response = await client.get("/api/v1/generate/credit")
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="get_credit_balance") from exc
        finally:
            await client.aclose()

    async def submit_lyrics_task(
        self,
        *,
        prompt: str,
        callback_url: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Submit a lyrics-only generation task (POST /api/v1/lyrics).

        Suno bills ~2 API credits per lyrics job. Prompt is limited to 200 chars.
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        payload: dict[str, Any] = {
            "prompt": str(prompt or "").strip()[:200],
            "callBackUrl": callback_url
            or (
                f"{self._callback_base_url}/api/v3/callbacks/suno-lyrics"
                if self._callback_base_url
                else "https://localhost/callbacks/suno-lyrics"
            ),
        }
        client = self._build_client(api_key)
        try:
            response = await client.post("/api/v1/lyrics", json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context="submit_lyrics_task") from exc
        finally:
            await client.aclose()

    async def check_lyrics_status(
        self,
        task_id: str,
        *,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Poll lyrics task status (GET /api/v1/lyrics/record-info)."""
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        client = self._build_client(api_key)
        try:
            response = await client.get(
                "/api/v1/lyrics/record-info",
                params={"taskId": task_id},
            )
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(exc, context=f"check_lyrics_status({task_id})") from exc
        finally:
            await client.aclose()

    async def generate_lyrics_blocking(
        self,
        *,
        prompt: str,
        callback_url: str | None = None,
        api_key: str | None = None,
        poll_interval_seconds: float = _SUNO_LYRICS_POLL_INTERVAL_SECONDS,
        max_wait_seconds: float = _SUNO_LYRICS_MAX_WAIT_SECONDS,
    ) -> tuple[str, str]:
        """Submit a lyrics task and poll until completion."""
        import asyncio
        import time

        submit_response = await self.submit_lyrics_task(
            prompt=prompt,
            callback_url=callback_url,
            api_key=api_key,
        )
        task_id = extract_suno_lyrics_task_id(submit_response)
        started = time.monotonic()
        last_error = ""
        while time.monotonic() - started < max_wait_seconds:
            poll_response = await self.check_lyrics_status(task_id, api_key=api_key)
            parsed = parse_suno_lyrics_poll(poll_response)
            if parsed.state == "pending":
                await asyncio.sleep(poll_interval_seconds)
                continue
            if parsed.state == "success":
                return parsed.text, parsed.title
            last_error = parsed.error or "Suno lyrics generation failed."
            raise ExternalServiceError(
                last_error,
                is_retryable=False,
                details={"provider": "suno", "reason": "lyrics_generation_failed"},
            )

        raise ExternalServiceError(
            f"Suno lyrics timed out after {int(max_wait_seconds)}s.",
            is_retryable=True,
            details={"provider": "suno", "reason": "lyrics_timeout", "task_id": task_id},
        )

    async def submit_wav_task(
        self,
        *,
        task_id: str,
        audio_id: str,
        callback_url: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Submit a WAV conversion task (POST /api/v1/wav/generate).

        Args:
            task_id: The original music generation task ID.
            audio_id: The specific audio clip ID to convert.
            callback_url: Optional callback URL for async notification.
            api_key: Suno API key (required).

        Returns:
            Response dict containing the WAV task ID.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        normalized_task = str(task_id or "").strip()
        if not normalized_task:
            raise ExternalServiceError(
                "taskId is required for WAV conversion.",
                is_retryable=False,
                details={"provider": "suno", "reason": "missing_task_id"},
            )
        normalized_audio = str(audio_id or "").strip()
        if not normalized_audio:
            raise ExternalServiceError(
                "audioId is required for WAV conversion.",
                is_retryable=False,
                details={"provider": "suno", "reason": "missing_audio_id"},
            )
        client = self._build_client(api_key)
        try:
            payload: dict[str, Any] = {
                "taskId": normalized_task,
                "audioId": normalized_audio,
            }
            if callback_url:
                payload["callBackUrl"] = str(callback_url).strip()
            response = await client.post("/api/v1/wav/generate", json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(
                exc,
                context=f"submit_wav_task({normalized_task}, {normalized_audio})",
            ) from exc
        finally:
            await client.aclose()

    async def poll_wav_status(
        self,
        *,
        wav_task_id: str,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Poll WAV conversion status (GET /api/v1/wav/record-info).

        Args:
            wav_task_id: The WAV conversion task ID.
            api_key: Suno API key (required).

        Returns:
            Response dict containing status and audioWavUrl when ready.

        Raises:
            ExternalServiceError: On timeout, HTTP error, or connection failure.
        """
        if not api_key:
            raise ExternalServiceError(
                "Suno API key is not configured. Add a key to the Key Pool.",
                is_retryable=False,
                details={"provider": "suno"},
            )
        normalized_task = str(wav_task_id or "").strip()
        if not normalized_task:
            raise ExternalServiceError(
                "wavTaskId is required for polling WAV status.",
                is_retryable=False,
                details={"provider": "suno", "reason": "missing_wav_task_id"},
            )
        client = self._build_client(api_key)
        try:
            response = await client.get(f"/api/v1/wav/record-info?taskId={normalized_task}")
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise _classify_error(
                exc,
                context=f"poll_wav_status({normalized_task})",
            ) from exc
        finally:
            await client.aclose()
