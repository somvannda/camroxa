"""Tests for web music play tokens."""

from __future__ import annotations

import json
from uuid import UUID

import pytest

from platform_api.services.web_music_play_tokens import (
    PLAY_TOKEN_TTL_SECONDS,
    create_play_token,
    play_url_for_token,
    resolve_play_token,
)


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        assert ttl == PLAY_TOKEN_TTL_SECONDS
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)


@pytest.mark.asyncio
async def test_create_and_resolve_public_play_token() -> None:
    redis = _FakeRedis()
    task_id = UUID("11111111-1111-1111-1111-111111111111")
    token = await create_play_token(redis, task_id=task_id, variant="ok", access="public")
    assert token
    assert play_url_for_token(token).startswith("/api/v1/web-music/play/")
    resolved = await resolve_play_token(redis, token)
    assert resolved is not None
    assert resolved["task_id"] == str(task_id)
    assert resolved["variant"] == "ok"
    assert resolved["access"] == "public"


@pytest.mark.asyncio
async def test_create_and_resolve_owner_play_token() -> None:
    redis = _FakeRedis()
    task_id = UUID("22222222-2222-2222-2222-222222222222")
    user_id = UUID("33333333-3333-3333-3333-333333333333")
    token = await create_play_token(
        redis,
        task_id=task_id,
        variant="alt",
        access="owner",
        user_id=user_id,
    )
    resolved = await resolve_play_token(redis, token)
    assert resolved == {
        "task_id": str(task_id),
        "variant": "alt",
        "access": "owner",
        "user_id": str(user_id),
    }


@pytest.mark.asyncio
async def test_resolve_play_token_rejects_invalid_payload() -> None:
    redis = _FakeRedis()
    redis._store["web_music:play:bad"] = json.dumps({"task_id": "", "variant": "ok", "access": "public"})
    assert await resolve_play_token(redis, "bad") is None
