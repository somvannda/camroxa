"""Timed music-web generation freeze (user + IP) and attack-signal counters.

Redis keys:
  musicweb:genfreeze:user:{id}
  musicweb:genfreeze:ip:{ip}

Auto TTL is PLATFORM_MUSIC_WEB_GEN_FREEZE_HOURS (default 6).
Admin may set 1 / 6 / 24 / 72 hours or clear the freeze.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import Request

from platform_api.config import get_settings
from platform_api.exceptions import GenerationFrozenError
from platform_api.middleware.geo_access import client_ip

logger = logging.getLogger(__name__)

USER_KEY_PREFIX = "musicweb:genfreeze:user:"
IP_KEY_PREFIX = "musicweb:genfreeze:ip:"
ALLOWED_HOURS = (1, 6, 24, 72)
DEFAULT_HOURS = 6

RATE_LIMIT_STORM_THRESHOLD = 8
RATE_LIMIT_STORM_WINDOW_SEC = 120
QUOTA_HAMMER_THRESHOLD = 10
QUOTA_HAMMER_WINDOW_SEC = 600
POLISH_PROBE_FREEZE_THRESHOLD = 10

_PROBE_RE = re.compile(
    r"(union\s+select|or\s+1\s*=\s*1|drop\s+table|;--|"
    r"\.\./|\.\.\\|/etc/passwd|<script\b|javascript:|onerror\s*=)",
    re.IGNORECASE,
)


class RedisClient(Protocol):
    async def get(self, name: str) -> str | bytes | None: ...
    async def setex(self, name: str, time: int, value: str) -> Any: ...
    async def incr(self, name: str) -> int: ...
    async def expire(self, name: str, time: int) -> Any: ...
    async def delete(self, *names: str) -> Any: ...
    async def ttl(self, name: str) -> int: ...


_redis: RedisClient | None = None


def configure_generation_freeze(redis: RedisClient) -> None:
    global _redis
    _redis = redis


def _client() -> RedisClient | None:
    return _redis


def default_freeze_hours() -> int:
    hours = int(get_settings().music_web_gen_freeze_hours or DEFAULT_HOURS)
    if hours in ALLOWED_HOURS:
        return hours
    return DEFAULT_HOURS


def user_freeze_key(user_id: str) -> str:
    return f"{USER_KEY_PREFIX}{user_id}"


def ip_freeze_key(ip: str) -> str:
    return f"{IP_KEY_PREFIX}{ip}"


def _decode(raw: str | bytes | None) -> dict[str, Any]:
    if raw is None:
        return {}
    text = raw.decode() if isinstance(raw, bytes) else str(raw)
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"reason": text or "frozen"}
    if isinstance(data, dict):
        return data
    return {"reason": str(data)}


def _payload(*, reason: str, hours: int, ip: str | None = None) -> str:
    body: dict[str, Any] = {
        "reason": reason,
        "hours": hours,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    if ip:
        body["ip"] = ip
    return json.dumps(body)


async def freeze_generation(
    *,
    user_id: str | None,
    ip: str | None,
    hours: int | None = None,
    reason: str,
) -> int:
    """Freeze generate for user and/or IP. Returns TTL seconds applied."""
    redis = _client()
    resolved_hours = hours if hours in ALLOWED_HOURS else default_freeze_hours()
    ttl = resolved_hours * 3600
    if redis is None:
        return ttl

    value = _payload(reason=reason, hours=resolved_hours, ip=ip)
    if user_id:
        await redis.setex(user_freeze_key(user_id), ttl, value)
    if ip and ip not in {"", "unknown", "127.0.0.1", "::1"}:
        await redis.setex(ip_freeze_key(ip), ttl, value)
    logger.warning(
        "Music web generation frozen user=%s ip=%s hours=%s reason=%s",
        user_id or "-",
        ip or "-",
        resolved_hours,
        reason,
    )
    await _alert_admins(
        user_id=user_id,
        ip=ip,
        hours=resolved_hours,
        reason=reason,
    )
    return ttl


async def unfreeze_generation(*, user_id: str, ip: str | None = None) -> None:
    redis = _client()
    if redis is None:
        return
    keys = [user_freeze_key(user_id)]
    stored = _decode(await redis.get(user_freeze_key(user_id)))
    stored_ip = str(stored.get("ip") or "").strip()
    if ip:
        keys.append(ip_freeze_key(ip))
    elif stored_ip:
        keys.append(ip_freeze_key(stored_ip))
    await redis.delete(*keys)


async def freeze_status(user_id: str) -> dict[str, Any]:
    redis = _client()
    empty = {
        "generation_frozen": False,
        "generation_frozen_reason": None,
        "generation_frozen_hours": None,
        "generation_frozen_retry_after": 0,
        "generation_frozen_ip": None,
    }
    if redis is None:
        return empty
    key = user_freeze_key(user_id)
    raw = await redis.get(key)
    if raw is None:
        return empty
    data = _decode(raw)
    ttl = int(await redis.ttl(key) or 0)
    retry_after = max(0, ttl) if ttl > 0 else 0
    return {
        "generation_frozen": True,
        "generation_frozen_reason": data.get("reason"),
        "generation_frozen_hours": data.get("hours"),
        "generation_frozen_retry_after": retry_after,
        "generation_frozen_ip": data.get("ip"),
    }


async def _lookup_freeze(
    redis: RedisClient, *, user_id: str | None, ip: str | None
) -> tuple[dict[str, Any], int] | None:
    checks: list[str] = []
    if user_id:
        checks.append(user_freeze_key(user_id))
    if ip and ip not in {"", "unknown"}:
        checks.append(ip_freeze_key(ip))
    for key in checks:
        raw = await redis.get(key)
        if raw is None:
            continue
        ttl = int(await redis.ttl(key) or 0)
        return _decode(raw), max(0, ttl)
    return None


async def enforce_generation_freeze(request: Request, user_id: str) -> None:
    """Raise GenerationFrozenError when this user or IP is frozen."""
    redis = _client()
    if redis is None:
        return
    ip = client_ip(request)
    found = await _lookup_freeze(redis, user_id=user_id, ip=ip)
    if found is None:
        return
    data, ttl = found
    hours = data.get("hours") or default_freeze_hours()
    retry_after = ttl if ttl > 0 else int(hours) * 3600
    raise GenerationFrozenError(
        _freeze_message(retry_after),
        details={"retry_after": retry_after, "reason": data.get("reason")},
    )


def _freeze_message(retry_after: int) -> str:
    hours_left = max(1, (retry_after + 3599) // 3600)
    if hours_left == 1:
        return "Music generation is paused for about 1 hour. Try again later."
    return f"Music generation is paused for about {hours_left} hours. Try again later."


async def _bump_and_maybe_freeze(
    *,
    counter_key: str,
    window_sec: int,
    threshold: int,
    user_id: str | None,
    ip: str | None,
    reason: str,
) -> int:
    redis = _client()
    if redis is None:
        return 0
    count = int(await redis.incr(counter_key))
    await redis.expire(counter_key, window_sec)
    if count >= threshold:
        await freeze_generation(user_id=user_id, ip=ip, reason=reason)
    return count


async def note_rate_limit_storm(request: Request, user_id: str) -> None:
    path = str(request.url.path or "").lower()
    if "/web-music/generate" not in path:
        return
    ip = client_ip(request)
    await _bump_and_maybe_freeze(
        counter_key=f"musicweb:attack:rl:{user_id}:{ip}",
        window_sec=RATE_LIMIT_STORM_WINDOW_SEC,
        threshold=RATE_LIMIT_STORM_THRESHOLD,
        user_id=user_id,
        ip=ip,
        reason="rate_limit_storm",
    )


async def note_quota_hammer(request: Request, user_id: str) -> None:
    ip = client_ip(request)
    await _bump_and_maybe_freeze(
        counter_key=f"musicweb:attack:quota:{user_id}:{ip}",
        window_sec=QUOTA_HAMMER_WINDOW_SEC,
        threshold=QUOTA_HAMMER_THRESHOLD,
        user_id=user_id,
        ip=ip,
        reason="quota_hammer",
    )


async def note_login_lockout(request: Request, email: str) -> None:
    ip = client_ip(request)
    user_id: str | None = None
    try:
        from platform_api.dependencies import get_user_repo

        user = await get_user_repo().get_by_email(email)
        if user is not None:
            user_id = str(user.id)
    except Exception as exc:
        logger.debug("Login-lockout freeze user lookup skipped: %s", exc)
    if user_id is None and (not ip or ip == "unknown"):
        return
    await freeze_generation(user_id=user_id, ip=ip, reason="login_lockout")


async def note_polish_probe_freeze(*, user_id: str | None, count: int) -> None:
    if count < POLISH_PROBE_FREEZE_THRESHOLD or not user_id:
        return
    await freeze_generation(user_id=user_id, ip=None, reason="polish_probe_storm")


def payload_looks_like_probe(*parts: str | None) -> bool:
    blob = " ".join(part or "" for part in parts)
    if not blob.strip():
        return False
    return _PROBE_RE.search(blob) is not None


async def reject_probe_payload(
    request: Request,
    user_id: str,
    *parts: str | None,
) -> None:
    if not payload_looks_like_probe(*parts):
        return
    ip = client_ip(request)
    await freeze_generation(user_id=user_id, ip=ip, reason="payload_probe")
    raise GenerationFrozenError(
        "Suspicious request blocked. Music generation is paused.",
        details={"retry_after": default_freeze_hours() * 3600, "reason": "payload_probe"},
    )


async def _alert_admins(
    *,
    user_id: str | None,
    ip: str | None,
    hours: int,
    reason: str,
) -> None:
    try:
        from platform_api.services.abuse_alert_service import get_abuse_alert_service

        service = get_abuse_alert_service()
        if service is None:
            return
        await service.note_generation_freeze(
            user_id=user_id,
            ip=ip,
            hours=hours,
            reason=reason,
        )
    except Exception as exc:
        logger.debug("Generation freeze admin alert skipped: %s", exc)
