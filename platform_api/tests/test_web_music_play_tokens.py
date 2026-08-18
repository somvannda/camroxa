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


@pytest.mark.asyncio
async def test_owner_play_urls_are_unique_per_task_and_variant() -> None:
    from unittest.mock import MagicMock
    from uuid import uuid4

    from platform_api.services.web_music_service import WebMusicService

    service = WebMusicService(pool=MagicMock(), generation_service=MagicMock(), redis=MagicMock())
    user_id = uuid4()
    task_a = uuid4()
    task_b = uuid4()
    url_a = await service._mint_owner_play_url(user_id, task_a, "ok")
    url_b = await service._mint_owner_play_url(user_id, task_b, "ok")
    url_a_alt = await service._mint_owner_play_url(user_id, task_a, "alt")
    assert url_a != url_b
    assert url_a != url_a_alt
    assert url_a == f"/api/v1/web-music/generations/{task_a}/stream/ok"
    assert url_a_alt == f"/api/v1/web-music/generations/{task_a}/stream/alt"
    assert url_b == f"/api/v1/web-music/generations/{task_b}/stream/ok"


def test_web_music_storage_key_is_unique_per_task() -> None:
    from uuid import uuid4

    from platform_api.services.streaming_upload_service import (
        b2_key_is_task_scoped,
        web_music_storage_key,
    )

    user_id = uuid4()
    task_a = uuid4()
    task_b = uuid4()
    key_a = web_music_storage_key(user_id=user_id, suno_task_id=task_a, variant="ok", ext="mp3")
    key_b = web_music_storage_key(user_id=user_id, suno_task_id=task_b, variant="ok", ext="mp3")
    shared = f"web-music/{user_id}/untitled-ok.mp3"
    assert key_a != key_b
    assert str(task_a) in key_a
    assert b2_key_is_task_scoped(key_a, task_a) is True
    assert b2_key_is_task_scoped(key_a, task_b) is False
    assert b2_key_is_task_scoped(shared, task_a) is False


@pytest.mark.asyncio
async def test_signed_get_url_uses_cdn_path_when_configured() -> None:
    from platform_api.services.storage_service import StorageService
    from platform_api.services.streaming_config_service import StreamingStorageConfig

    config = StreamingStorageConfig(
        key_id="key",
        application_key="secret",
        bucket="bucket",
        region="us-west-004",
        endpoint="https://s3.example",
        cdn_base_url="https://cdn.example",
        stream_url_ttl_seconds=60,
        secret_source="environment",
        configured=True,
    )
    storage = StorageService(config)
    url = await storage.get_signed_get_url("web-music/u/t/ok.mp3")
    assert url == "https://cdn.example/web-music/u/t/ok.mp3"


@pytest.mark.asyncio
async def test_origin_playback_skips_shared_untitled_b2_key() -> None:
    from unittest.mock import MagicMock
    from uuid import uuid4

    from platform_api.services.web_music_service import WebMusicService

    service = WebMusicService(pool=MagicMock(), generation_service=MagicMock(), redis=MagicMock())
    task_id = uuid4()
    user_id = uuid4()
    row = {
        "status": "SUCCESS",
        "b2_storage_key_ok": f"web-music/{user_id}/untitled-ok.mp3",
        "b2_storage_key_alt": f"web-music/{user_id}/untitled-alt.mp3",
        "audio_url_ok": "https://cdn.example.com/fire-ok.mp3",
        "audio_url_alt": "https://cdn.example.com/fire-alt.mp3",
    }
    origin = await service._origin_playback_url(row, task_id=task_id, variant_key="ok")
    assert origin == ("https://cdn.example.com/fire-ok.mp3", "suno")
    origin_alt = await service._origin_playback_url(row, task_id=task_id, variant_key="alt")
    assert origin_alt == ("https://cdn.example.com/fire-alt.mp3", "suno")

