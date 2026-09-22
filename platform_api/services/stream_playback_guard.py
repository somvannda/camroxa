"""Stop curl-style Range stitchers from dumping a play/stream URL to disk.

Native <audio> still works: Chrome/Safari send Sec-Fetch-Dest: audio (or a
music-web Referer on older browsers). A sequential dump of new 256 KiB windows
faster than playback is 429'd. Retrying the same window is free. Official
download endpoints are not guarded here.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from platform_api.exceptions import ForbiddenError, RateLimitedError
from platform_api.middleware.geo_access import MUSIC_WEB_HOSTS
from platform_api.services.audio_origin_proxy import _PLAY_CHUNK_BYTES, parse_clamped_range

logger = logging.getLogger(__name__)

STREAM_PACE_PREFIX = "web_music:stream_pace:"
STREAM_PACE_TTL_SECONDS = 900
STREAM_UNIQUE_WINDOW_LIMIT = 10
STREAM_UNIQUE_WINDOW_SECONDS = 15.0

_LOCAL_PLAY_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "music.localhost",
    }
)
_ALLOWED_FETCH_DEST = frozenset({"audio"})
_PLAYBACK_DENIED_MESSAGE = "Play this track in Camxora Music."


@dataclass(frozen=True)
class PaceSnapshot:
    seen: frozenset[int]
    new_at: tuple[float, ...]


@dataclass(frozen=True)
class PaceDecision:
    allowed: bool
    retry_after: int
    snapshot: PaceSnapshot


def _header(headers: Mapping[str, str] | None, name: str) -> str:
    if not headers:
        return ""
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value:
            return str(value).strip()
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return str(value or "").strip()
    return ""


def _referer_host(referer: str) -> str:
    raw = str(referer or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.hostname or parsed.netloc or "").split(":")[0].strip().lower()
    return host


def is_music_web_play_host(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    if not normalized:
        return False
    if normalized in MUSIC_WEB_HOSTS or normalized in _LOCAL_PLAY_HOSTS:
        return True
    return normalized.endswith(".localhost")


def is_browser_audio_request(headers: Mapping[str, str] | None) -> bool:
    """True for a media element request, false for curl/Postman/fetch dumps."""
    dest = _header(headers, "sec-fetch-dest").lower()
    if dest:
        return dest in _ALLOWED_FETCH_DEST
    host = _referer_host(_header(headers, "referer") or _header(headers, "referrer"))
    return is_music_web_play_host(host)


def window_id_for_range(range_header: str | None) -> int:
    start, _end = parse_clamped_range(range_header)
    return max(0, start) // _PLAY_CHUNK_BYTES


def evaluate_unique_window_pace(
    snapshot: PaceSnapshot,
    window_id: int,
    *,
    now: float,
    limit: int = STREAM_UNIQUE_WINDOW_LIMIT,
    period: float = STREAM_UNIQUE_WINDOW_SECONDS,
) -> PaceDecision:
    """Allow retries of a seen window; cap new windows in a sliding period."""
    if window_id in snapshot.seen:
        return PaceDecision(True, 0, snapshot)
    recent = tuple(ts for ts in snapshot.new_at if now - ts < period)
    if len(recent) >= limit:
        oldest = min(recent)
        retry_after = max(1, int(math.ceil(period - (now - oldest))))
        return PaceDecision(False, retry_after, PaceSnapshot(snapshot.seen, recent))
    return PaceDecision(
        True,
        0,
        PaceSnapshot(snapshot.seen | {window_id}, recent + (now,)),
    )


def _pace_key(scope: str) -> str:
    return f"{STREAM_PACE_PREFIX}{scope}"


def _snapshot_from_raw(raw: Any) -> PaceSnapshot:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not raw:
        return PaceSnapshot(frozenset(), ())
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return PaceSnapshot(frozenset(), ())
    if not isinstance(data, dict):
        return PaceSnapshot(frozenset(), ())
    seen_raw = data.get("seen") or []
    new_at_raw = data.get("new_at") or []
    seen = frozenset(int(item) for item in seen_raw if str(item).lstrip("-").isdigit())
    new_at = tuple(float(item) for item in new_at_raw)
    return PaceSnapshot(seen, new_at)


def assert_browser_audio_request(headers: Mapping[str, str] | None) -> None:
    if is_browser_audio_request(headers):
        return
    raise ForbiddenError(
        _PLAYBACK_DENIED_MESSAGE,
        details={"code": "playback_client_denied"},
    )


async def enforce_unique_window_pace(
    redis: Any | None,
    scope: str,
    range_header: str | None,
    *,
    now: float | None = None,
) -> None:
    if redis is None:
        return
    key = _pace_key(str(scope or "").strip())
    if key == STREAM_PACE_PREFIX:
        return
    window_id = window_id_for_range(range_header)
    stamp = float(now if now is not None else time.time())
    try:
        raw = await redis.get(key)
        snapshot = _snapshot_from_raw(raw)
        decision = evaluate_unique_window_pace(snapshot, window_id, now=stamp)
        if not decision.allowed:
            raise RateLimitedError(
                "Playback is catching up. Try again in a moment.",
                retry_after=decision.retry_after,
                details={"code": "stream_window_pace"},
            )
        payload = json.dumps(
            {
                "seen": sorted(decision.snapshot.seen),
                "new_at": list(decision.snapshot.new_at),
            }
        )
        await redis.setex(key, STREAM_PACE_TTL_SECONDS, payload)
    except RateLimitedError:
        raise
    except Exception as exc:
        logger.warning("Stream window pace skipped: %s", exc)


async def enforce_stream_playback_guard(
    *,
    redis: Any | None,
    scope: str,
    range_header: str | None,
    request_headers: Mapping[str, str] | None,
) -> None:
    """Reject non-player clients, then pace unique Range windows per scope."""
    if request_headers is not None:
        assert_browser_audio_request(request_headers)
    await enforce_unique_window_pace(redis, scope, range_header)
