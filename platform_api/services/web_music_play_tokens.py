"""Short-lived play tokens for web music streaming (hide raw task IDs)."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Literal
from uuid import UUID

logger = logging.getLogger(__name__)

PLAY_TOKEN_PREFIX = "web_music:play:"
PLAY_TOKEN_TTL_SECONDS = 900  # 15 minutes

PlayAccess = Literal["owner", "public"]


def _redis_key(token: str) -> str:
    return f"{PLAY_TOKEN_PREFIX}{token}"


async def create_play_token(
    redis: Any,
    *,
    task_id: UUID,
    variant: str,
    access: PlayAccess,
    user_id: UUID | None = None,
) -> str:
    """Mint a single-use-style play token stored in Redis."""
    token = secrets.token_urlsafe(32)
    payload = {
        "task_id": str(task_id),
        "variant": str(variant or "ok").strip().lower(),
        "access": access,
        "user_id": str(user_id) if user_id else None,
    }
    await redis.setex(_redis_key(token), PLAY_TOKEN_TTL_SECONDS, json.dumps(payload))
    return token


def play_url_for_token(token: str) -> str:
    from platform_api.http_paths import canonical_api_path

    return canonical_api_path(f"web-music/play/{token}")


async def resolve_play_token(redis: Any, token: str) -> dict[str, Any] | None:
    raw = str(token or "").strip()
    if not raw or len(raw) > 128:
        return None
    try:
        cached = await redis.get(_redis_key(raw))
    except Exception as exc:
        logger.warning("Play token Redis lookup failed: %s", exc)
        return None
    if not cached:
        return None
    try:
        if isinstance(cached, bytes):
            cached = cached.decode("utf-8")
        data = json.loads(str(cached))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    task_id = str(data.get("task_id") or "").strip()
    variant = str(data.get("variant") or "ok").strip().lower()
    access = str(data.get("access") or "").strip().lower()
    if not task_id or variant not in {"ok", "alt"} or access not in {"owner", "public"}:
        return None
    return {
        "task_id": task_id,
        "variant": variant,
        "access": access,
        "user_id": str(data.get("user_id") or "").strip() or None,
    }
