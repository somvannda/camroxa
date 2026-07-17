from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform_api.services.streaming_config_service import (
    STREAMING_B2_APPLICATION_KEY_KEY,
    STREAMING_B2_KEY_ID_KEY,
    mask_secret_value,
    resolve_streaming_storage_config,
    save_streaming_storage_config,
)


@pytest.mark.asyncio
async def test_resolve_streaming_storage_config_from_env() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    settings = MagicMock()
    settings.streaming_b2_key_id = "key-123"
    settings.streaming_b2_application_key = "app-secret"
    settings.streaming_b2_bucket = "camxora-media"
    settings.streaming_b2_region = "us-west-004"
    settings.streaming_b2_endpoint = ""
    settings.streaming_cdn_base_url = "https://media.camxora.com"
    settings.streaming_stream_url_ttl_seconds = 3600

    config = await resolve_streaming_storage_config(pool, settings=settings)
    assert config.configured is True
    assert config.key_id == "key-123"
    assert config.secret_source == "environment"
    assert config.endpoint.endswith("backblazeb2.com")


@pytest.mark.asyncio
async def test_save_streaming_storage_config_persists_keys() -> None:
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)

    settings = MagicMock()
    settings.encryption_master_key = ""
    settings.streaming_b2_key_id = ""
    settings.streaming_b2_application_key = ""
    settings.streaming_b2_bucket = "camxora-media"
    settings.streaming_b2_region = "us-west-004"
    settings.streaming_b2_endpoint = ""
    settings.streaming_cdn_base_url = ""
    settings.streaming_stream_url_ttl_seconds = 3600

    with patch("platform_api.services.streaming_config_service.get_settings", return_value=settings):
        public = await save_streaming_storage_config(
            pool,
            key_id="key-123",
            application_key="app-secret",
            bucket="camxora-media",
            region="us-west-004",
            endpoint="https://s3.us-west-004.backblazeb2.com",
            cdn_base_url="https://media.camxora.com",
            stream_url_ttl_seconds=3600,
        )

    assert public.bucket == "camxora-media"
    assert pool.execute.await_count >= 5


def test_mask_secret_value() -> None:
    assert mask_secret_value("abcd1234wxyz") == "abcd••••wxyz"
