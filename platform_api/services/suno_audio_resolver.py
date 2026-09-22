"""Resolve and download Suno MP3 files for server-side streaming uploads."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from platform_api.clients.suno_client import (
    SunoGeneratePollResult,
    _extract_clip_download_url,
    _iter_generate_clips,
    cdn_url_for_suno_audio_id,
    coerce_suno_download_url,
    parse_suno_generate_poll,
    payload_is_mpeg_audio,
    prefer_suno_mpeg_cdn_url,
)
from platform_api.services.storage_service import StorageServiceError

logger = logging.getLogger(__name__)

_MIN_MP3_BYTES = 4096
_CHUNK_SIZE = 1024 * 1024
_DISALLOWED_URL_MARKERS = (
    ".m4a",
    ".aac",
    ".m3u8",
    "/m4a/",
    "audio/mp4",
    "video/mp4",
    "x-m4a",
    # musicfile.removeai.ai is the cover/stream host, not the finished MP3
    # (GET returns 200 audio/mp3 with 0 bytes). Never store it as a download URL.
    "musicfile.removeai.ai",
)
_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)",
    "Accept": "audio/mpeg,application/octet-stream,*/*;q=0.8",
}
_INVALID_URL_LITERALS = frozenset({"none", "null", "undefined", "n/a", "nil"})


def normalize_http_download_url(url: str | None) -> str:
    """Return a usable http(s) download URL or empty string."""
    text = str(url or "").strip()
    if not text or text.lower() in _INVALID_URL_LITERALS:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return ""


def is_http_download_url(url: str | None) -> bool:
    return bool(normalize_http_download_url(url))


@dataclass(frozen=True, slots=True)
class SunoTaskDownloadUrls:
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
    refreshed: bool = False


def is_disallowed_suno_audio_url(url: str | None) -> bool:
    """Reject stream previews, m4a/aac, and HLS URLs — we want finished MP3 files."""
    text = str(url or "").strip().lower()
    if not text:
        return True
    if any(marker in text for marker in _DISALLOWED_URL_MARKERS):
        return True
    if text.endswith(".mp3") or ".mp3?" in text:
        return False
    if "cdn1.suno.ai/" in text and text.endswith(".mp3"):
        return False
    # Suno source_audio_url should be mp3; reject unknown extensions on direct file URLs.
    path = text.split("?", 1)[0]
    if "." in path.rsplit("/", 1)[-1]:
        ext = path.rsplit(".", 1)[-1]
        if ext not in {"mp3"}:
            return True
    return False


def validate_mp3_bytes(data: bytes) -> bool:
    """True when bytes look like MP3 (ID3 tag or MPEG frame sync), not m4a/other."""
    if len(data) < 4:
        return False
    if data[:3] == b"ID3":
        return True
    # MPEG audio frame sync: 0xFF followed by 0xE0+ (11 set bits)
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    # ftyp box => MP4/M4A container
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return False
    return False


def build_download_url_candidates(*urls: str | None) -> list[str]:
    """Return unique non-empty download URL candidates in priority order.

    Suno CDN ``.m4a`` (Opus) links are rewritten to the sibling ``.mp3``.
    """
    seen: set[str] = set()
    candidates: list[str] = []
    for raw in urls:
        url = prefer_suno_mpeg_cdn_url(normalize_http_download_url(raw))
        if not url or url in seen or is_disallowed_suno_audio_url(url):
            continue
        seen.add(url)
        candidates.append(url)
    return candidates


def urls_from_generate_poll(result: SunoGeneratePollResult) -> SunoTaskDownloadUrls:
    return SunoTaskDownloadUrls(
        audio_url_ok=normalize_http_download_url(result.audio_url_ok),
        audio_url_alt=normalize_http_download_url(result.audio_url_alt),
        image_url_ok=normalize_http_download_url(result.image_url_ok),
        image_url_alt=normalize_http_download_url(result.image_url_alt),
        duration_ok=result.duration_ok,
        duration_alt=result.duration_alt,
        tags_ok=str(result.tags_ok or "").strip(),
        tags_alt=str(result.tags_alt or "").strip(),
        audio_id_ok=str(result.audio_id_ok or "").strip(),
        audio_id_alt=str(result.audio_id_alt or "").strip(),
        refreshed=True,
    )


def urls_from_record_info_payload(payload: dict[str, Any]) -> SunoTaskDownloadUrls:
    parsed = parse_suno_generate_poll(payload)
    if parsed.state != "success":
        return SunoTaskDownloadUrls()
    return urls_from_generate_poll(parsed)


def variant_url_candidates(
    *,
    variant: str,
    stored_ok: str,
    stored_alt: str,
    refreshed: SunoTaskDownloadUrls | None,
    include_other_variant: bool = False,
) -> list[str]:
    refreshed_ok = refreshed.audio_url_ok if refreshed else ""
    refreshed_alt = refreshed.audio_url_alt if refreshed else ""
    if variant == "alt":
        urls: list[str | None] = [refreshed_alt, stored_alt]
        if include_other_variant:
            urls.extend([refreshed_ok, stored_ok])
        return build_download_url_candidates(*urls)
    urls = [refreshed_ok, stored_ok]
    if include_other_variant:
        urls.extend([refreshed_alt, stored_alt])
    return build_download_url_candidates(*urls)


async def refresh_suno_task_download_urls(
    external_task_id: str,
    *,
    poll_status,
) -> SunoTaskDownloadUrls:
    """Re-fetch downloadable MP3 URLs from Suno record-info."""
    task_id = str(external_task_id or "").strip()
    if not task_id:
        return SunoTaskDownloadUrls()
    try:
        poll_result = await poll_status(task_id)
    except Exception as exc:
        logger.warning("Suno record-info refresh failed for task %s: %s", task_id, str(exc)[:200])
        return SunoTaskDownloadUrls()
    if poll_result.state != "success":
        return SunoTaskDownloadUrls()
    return urls_from_generate_poll(poll_result)


async def recover_suno_task_download_urls(pool: Any, external_task_id: str) -> dict[str, str]:
    """Fresh playable URLs for an expired task, keyed by clip id.

    Uses the provider's Recovery Audio endpoint. It is scoped to the API
    key/account that generated the task, so every active Suno key is tried
    until one recovers the task. Returns ``{clip_id: audio_url}`` (may be .m4a).
    """
    import asyncio
    import os

    import httpx

    from platform_api.services.key_encryption import KeyEncryption

    task_id = str(external_task_id or "").strip()
    if not task_id:
        return {}
    rows = await pool.fetch(
        """
        SELECT encrypted_key_value
        FROM api_key_entries
        WHERE provider = 'suno' AND status = 'active'
        ORDER BY priority DESC, created_at ASC
        """
    )
    if not rows:
        return {}
    master_key = os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY", "").strip()
    if not master_key:
        return {}
    encryption = KeyEncryption(master_key=master_key)
    base = os.environ.get("PLATFORM_SUNO_API_BASE_URL", "https://apibox.erweima.ai").strip().rstrip("/")
    callback = os.environ.get("PLATFORM_SUNO_CALLBACK_BASE_URL", "").strip().rstrip("/")
    callback_url = (
        f"{callback}/api/v3/callbacks/suno" if callback else "https://api.camxora.com/health"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        for row in rows:
            try:
                api_key = encryption.decrypt(bytes(row["encrypted_key_value"]))
            except Exception:
                continue
            try:
                response = await client.post(
                    f"{base}/api/v1/suno/recovery",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"sunoTaskId": task_id, "callBackUrl": callback_url},
                )
                body = response.json()
            except Exception as exc:
                logger.warning("Recovery request failed for task %s: %s", task_id, str(exc)[:160])
                continue
            if int(body.get("code", 0) or 0) != 200:
                continue
            data = body.get("data")
            tracks = data if isinstance(data, list) else []
            recovery_task_id = str(body.get("task_id") or "").strip()
            if not tracks and recovery_task_id:
                # Async recovery: poll record-info until it finishes.
                for _ in range(20):
                    await asyncio.sleep(2.0)
                    try:
                        poll = await client.get(
                            f"{base}/api/v1/suno/recovery/record-info",
                            headers={"Authorization": f"Bearer {api_key}"},
                            params={"task_id": recovery_task_id},
                        )
                        poll_body = poll.json()
                    except Exception:
                        continue
                    poll_code = int(poll_body.get("code", 0) or 0)
                    if poll_code == 200:
                        poll_data = poll_body.get("data")
                        tracks = poll_data if isinstance(poll_data, list) else []
                        break
                    if poll_code == 500:
                        break
            mapping: dict[str, str] = {}
            for item in tracks:
                if not isinstance(item, dict):
                    continue
                if str(item.get("status") or "").lower() != "success":
                    continue
                clip_id = str(item.get("id") or "").strip()
                url = normalize_http_download_url(item.get("audio_url"))
                if clip_id and url:
                    mapping[clip_id] = url
            if mapping:
                return mapping
    return {}


async def poll_suno_generate_with_pool(pool: Any, external_task_id: str):
    """Poll Suno record-info using the DB pool (works outside FastAPI lifespan)."""
    import os
    from types import SimpleNamespace

    from platform_api.clients.suno_client import SunoClient, SunoGeneratePollResult, parse_suno_generate_poll
    from platform_api.services.key_encryption import KeyEncryption

    task_id = str(external_task_id or "").strip()
    if not task_id:
        return SunoGeneratePollResult(state="failed", error="Missing Suno task id.")

    row = await pool.fetchrow(
        """
        SELECT encrypted_key_value
        FROM api_key_entries
        WHERE provider = 'suno' AND status = 'active'
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        """
    )
    if not row:
        return SunoGeneratePollResult(state="failed", error="No active Suno API key configured.")

    master_key = os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY", "").strip()
    if not master_key:
        return SunoGeneratePollResult(state="failed", error="Encryption master key is not configured.")

    encryption = KeyEncryption(master_key=master_key)
    api_key = encryption.decrypt(bytes(row["encrypted_key_value"]))
    settings = SimpleNamespace(
        suno_api_base_url=os.environ.get("PLATFORM_SUNO_API_BASE_URL", "https://apibox.erweima.ai").strip(),
        suno_callback_base_url=os.environ.get("PLATFORM_SUNO_CALLBACK_BASE_URL", "").strip(),
        suno_timeout_seconds=int(os.environ.get("PLATFORM_SUNO_TIMEOUT_SECONDS", "30") or 30),
    )
    client = SunoClient(settings)
    response = await client.check_status(task_id, api_key=api_key)
    return parse_suno_generate_poll(response)


async def _suno_client_with_pool_key(pool: Any):
    """Return (SunoClient, api_key) using the active DB key pool entry."""
    import os
    from types import SimpleNamespace

    from platform_api.clients.suno_client import SunoClient
    from platform_api.services.key_encryption import KeyEncryption

    row = await pool.fetchrow(
        """
        SELECT encrypted_key_value
        FROM api_key_entries
        WHERE provider = 'suno' AND status = 'active'
        ORDER BY priority DESC, created_at ASC
        LIMIT 1
        """
    )
    if not row:
        raise RuntimeError("No active Suno API key configured.")

    master_key = os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY", "").strip()
    if not master_key:
        raise RuntimeError("Encryption master key is not configured.")

    encryption = KeyEncryption(master_key=master_key)
    api_key = encryption.decrypt(bytes(row["encrypted_key_value"]))
    settings = SimpleNamespace(
        suno_api_base_url=os.environ.get("PLATFORM_SUNO_API_BASE_URL", "https://apibox.erweima.ai").strip(),
        suno_callback_base_url=os.environ.get("PLATFORM_SUNO_CALLBACK_BASE_URL", "").strip(),
        suno_timeout_seconds=int(os.environ.get("PLATFORM_SUNO_TIMEOUT_SECONDS", "30") or 30),
    )
    return SunoClient(settings), api_key


async def fetch_timestamped_lrc_with_pool(
    pool: Any,
    *,
    external_task_id: str,
    audio_id: str,
    attempts: int = 4,
    delay_seconds: float = 2.0,
) -> str:
    """Fetch Suno aligned words and convert to LRC. Empty string on failure.

    Suno often returns empty/unusable alignments for a short window right after
    generation completes, so we retry a few times before giving up.
    """
    import asyncio

    from platform_api.services.suno_lrc import aligned_words_to_lrc, parse_aligned_words_payload

    task_id = str(external_task_id or "").strip()
    clip_id = str(audio_id or "").strip()
    if not task_id or not clip_id:
        return ""

    tries = max(1, int(attempts or 1))
    delay = max(0.0, float(delay_seconds or 0.0))
    last_error = ""
    for attempt in range(1, tries + 1):
        try:
            client, api_key = await _suno_client_with_pool_key(pool)
            payload = await client.get_timestamped_lyrics(
                task_id=task_id,
                audio_id=clip_id,
                api_key=api_key,
            )
            code = int(payload.get("code", 0) or 0)
            if code != 200:
                last_error = f"code={code} msg={str(payload.get('msg') or '')[:160]}"
                logger.warning(
                    "Suno timestamped lyrics failed task=%s audio=%s attempt=%s/%s %s",
                    task_id,
                    clip_id[:12],
                    attempt,
                    tries,
                    last_error,
                )
            else:
                lrc = aligned_words_to_lrc(parse_aligned_words_payload(payload))
                if lrc:
                    if attempt > 1:
                        logger.info(
                            "Suno timestamped lyrics ready task=%s audio=%s attempt=%s",
                            task_id,
                            clip_id[:12],
                            attempt,
                        )
                    return lrc
                last_error = "empty/unusable alignedWords"
                logger.info(
                    "Suno timestamped lyrics empty/unusable for task=%s audio=%s attempt=%s/%s",
                    task_id,
                    clip_id[:12],
                    attempt,
                    tries,
                )
        except Exception as exc:
            last_error = str(exc)[:200]
            logger.warning(
                "Suno timestamped lyrics error task=%s audio=%s attempt=%s/%s: %s",
                task_id,
                clip_id[:12],
                attempt,
                tries,
                last_error,
            )
        if attempt < tries and delay > 0:
            await asyncio.sleep(delay)

    if last_error:
        logger.warning(
            "Suno timestamped lyrics exhausted retries task=%s audio=%s last=%s",
            task_id,
            clip_id[:12],
            last_error,
        )
    return ""


def validate_wav_bytes(data: bytes) -> bool:
    """True when bytes look like a WAVE file (RIFF....WAVE)."""
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


async def origin_audio_range_is_playable(url: str) -> bool:
    """True when origin serves a short Range GET (CDN has the file, not a 403 placeholder)."""
    text = normalize_http_download_url(url)
    if not text:
        return False
    headers = {**_DOWNLOAD_HEADERS, "Range": "bytes=0-2047"}
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=4.0),
            follow_redirects=True,
            headers=_DOWNLOAD_HEADERS,
        ) as client:
            response = await client.get(text, headers=headers)
    except Exception as exc:
        logger.info("Origin audio probe failed url=%s: %s", text[:120], exc)
        return False
    if response.status_code not in {200, 206}:
        return False
    data = bytes(response.content or b"")
    if len(data) < 64:
        return False
    stripped = data.lstrip()[:32].lower()
    if stripped.startswith(b"<!doctype") or stripped.startswith(b"<html"):
        return False
    return True


def payload_is_wav_audio(data: bytes) -> bool:
    """Alias used by tests and older callers."""
    return validate_wav_bytes(data)


async def download_suno_mp3_bytes(url: str, *, fallback_urls: list[str] | None = None) -> bytes:
    """Download MP3 bytes, trying fallback URLs when the primary link is empty."""
    candidates = build_download_url_candidates(url, *(fallback_urls or []))
    if not candidates:
        raise StorageServiceError("No valid Suno MP3 download URL provided.")

    last_error: Exception | None = None
    for candidate in candidates:
        for attempt in range(1, 4):
            try:
                data = await _download_once(candidate)
                if len(data) >= _MIN_MP3_BYTES and payload_is_mpeg_audio(data):
                    return data
                if len(data) >= _MIN_MP3_BYTES:
                    last_error = StorageServiceError(
                        f"Suno download was not MPEG audio for {candidate[:120]}"
                    )
                else:
                    last_error = StorageServiceError(
                        f"Suno download returned empty body ({len(data)} bytes) for {candidate[:120]}"
                    )
            except Exception as exc:
                last_error = exc
            if attempt < 3:
                await asyncio.sleep(float(attempt))
    raise StorageServiceError(str(last_error or "Unable to download Suno MP3."))


async def download_suno_wav_bytes(url: str, *, fallback_urls: list[str] | None = None) -> bytes:
    """Download WAV bytes for one clip. Never used for MP3 sibling URLs."""
    candidates: list[str] = []
    seen: set[str] = set()
    for raw in (url, *(fallback_urls or [])):
        text = normalize_http_download_url(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        candidates.append(text)
    if not candidates:
        raise StorageServiceError("No valid Suno WAV download URL provided.")

    last_error: Exception | None = None
    for candidate in candidates:
        for attempt in range(1, 4):
            try:
                data = await _download_once(candidate, reject_mp4=False)
                if validate_wav_bytes(data):
                    return data
                last_error = StorageServiceError(
                    f"Suno download was not WAVE audio ({len(data)} bytes) for {candidate[:120]}"
                )
            except Exception as exc:
                last_error = exc
            if attempt < 3:
                await asyncio.sleep(float(attempt))
    raise StorageServiceError(str(last_error or "Unable to download Suno WAV."))


async def _download_once(url: str, *, reject_mp4: bool = True) -> bytes:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=15.0),
        headers=_DOWNLOAD_HEADERS,
        follow_redirects=True,
    ) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = str(response.headers.get("content-type") or "").lower()
            if reject_mp4 and any(
                marker in content_type for marker in ("audio/mp4", "video/mp4", "x-m4a", "audio/aac")
            ):
                raise StorageServiceError(f"Suno returned non-MP3 content-type: {content_type}")
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes(chunk_size=_CHUNK_SIZE):
                if chunk:
                    chunks.append(chunk)
            return b"".join(chunks)


def extract_callback_download_urls(raw_payload: dict[str, Any]) -> SunoTaskDownloadUrls:
    """Parse sunoapi.org callback payloads with nested clip arrays."""
    from platform_api.clients.suno_client import (
        _extract_clip_audio_id,
        _extract_clip_duration,
        cdn_url_for_suno_audio_id,
    )

    data_block = raw_payload.get("data")
    clips: list[dict[str, Any]] = []
    if isinstance(data_block, dict):
        nested = data_block.get("data")
        if isinstance(nested, list):
            clips.extend(item for item in nested if isinstance(item, dict))
    if not clips:
        return SunoTaskDownloadUrls()

    download_urls: list[str] = []
    audio_ids: list[str] = []
    image_urls: list[str] = []
    durations: list[float | None] = []
    for clip in clips:
        from platform_api.clients.suno_client import _extract_clip_image_url

        audio_id = _extract_clip_audio_id(clip)
        url = _extract_clip_download_url(clip) or cdn_url_for_suno_audio_id(audio_id)
        if not url and not audio_id:
            continue
        if not url:
            continue
        download_urls.append(url)
        audio_ids.append(audio_id)
        image_urls.append(_extract_clip_image_url(clip))
        durations.append(_extract_clip_duration(clip))
    if not download_urls:
        return SunoTaskDownloadUrls()

    return SunoTaskDownloadUrls(
        audio_url_ok=download_urls[0],
        audio_url_alt=download_urls[1] if len(download_urls) > 1 else "",
        audio_id_ok=audio_ids[0] if audio_ids else "",
        audio_id_alt=audio_ids[1] if len(audio_ids) > 1 else "",
        image_url_ok=image_urls[0] if image_urls else "",
        image_url_alt=image_urls[1] if len(image_urls) > 1 else "",
        duration_ok=durations[0] if durations else None,
        duration_alt=durations[1] if len(durations) > 1 else None,
        refreshed=True,
    )


def callback_indicates_success(raw_payload: dict[str, Any]) -> bool:
    code = raw_payload.get("code")
    if code is not None:
        try:
            if int(code) == 200:
                return True
        except (TypeError, ValueError):
            pass

    data_block = raw_payload.get("data")
    if isinstance(data_block, dict):
        callback_type = str(data_block.get("callbackType") or data_block.get("callback_type") or "").lower()
        if callback_type in {"complete", "first"}:
            return callback_type == "complete"
        status = str(data_block.get("status") or "").upper()
        if status in {"SUCCESS", "COMPLETE", "COMPLETED", "DONE"}:
            return True
    return False


def extract_callback_task_id(raw_payload: dict[str, Any]) -> str:
    for key in ("task_id", "taskId"):
        value = str(raw_payload.get(key) or "").strip()
        if value:
            return value
    data_block = raw_payload.get("data")
    if isinstance(data_block, dict):
        for key in ("task_id", "taskId"):
            value = str(data_block.get(key) or "").strip()
            if value:
                return value
    return ""


__all__ = [
    "SunoTaskDownloadUrls",
    "build_download_url_candidates",
    "callback_indicates_success",
    "cdn_url_for_suno_audio_id",
    "coerce_suno_download_url",
    "download_suno_mp3_bytes",
    "download_suno_wav_bytes",
    "extract_callback_download_urls",
    "extract_callback_task_id",
    "fetch_timestamped_lrc_with_pool",
    "is_disallowed_suno_audio_url",
    "is_http_download_url",
    "normalize_http_download_url",
    "origin_audio_range_is_playable",
    "payload_is_wav_audio",
    "refresh_suno_task_download_urls",
    "urls_from_record_info_payload",
    "validate_mp3_bytes",
    "validate_wav_bytes",
    "variant_url_candidates",
]
