"""Tests for SLAI image provider configuration service."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.services.slai_image_config_service import (
    SETTINGS_KEY,
    defaults_from_env,
    get_cached_slai_image_provider_config,
    load_slai_image_provider_config,
    normalize_config,
    save_slai_image_provider_config,
    set_cached_slai_image_provider_config,
)


@pytest.mark.asyncio
async def test_load_uses_system_settings_when_present() -> None:
    repo = AsyncMock()
    repo.get_system_setting = AsyncMock(
        return_value={
            "min_interval_seconds": 8.0,
            "max_concurrent": 2,
            "provider_retries": 7,
            "retry_base_delay_seconds": 6.0,
            "retry_max_delay_seconds": 60.0,
            "fallback_provider_retries": 2,
        }
    )

    config = await load_slai_image_provider_config(repo)
    assert config.min_interval_seconds == 8.0
    assert config.max_concurrent == 2
    assert config.provider_retries == 7
    assert get_cached_slai_image_provider_config().provider_retries == 7


@pytest.mark.asyncio
async def test_save_persists_and_updates_cache() -> None:
    repo = AsyncMock()
    repo.upsert_system_settings = AsyncMock()

    config = await save_slai_image_provider_config(
        repo,
        {
            "min_interval_seconds": 10.0,
            "max_concurrent": 1,
            "provider_retries": 6,
            "retry_base_delay_seconds": 4.0,
            "retry_max_delay_seconds": 30.0,
            "fallback_provider_retries": 1,
        },
    )

    repo.upsert_system_settings.assert_awaited_once()
    saved = repo.upsert_system_settings.await_args.args[0]
    assert SETTINGS_KEY in saved
    assert config.provider_retries == 6
    assert get_cached_slai_image_provider_config().provider_retries == 6


def test_normalize_config_clamps_invalid_values() -> None:
    defaults = defaults_from_env()
    config = normalize_config(
        {
            "min_interval_seconds": -5,
            "max_concurrent": 99,
            "provider_retries": 0,
            "retry_base_delay_seconds": 500,
            "retry_max_delay_seconds": 0.5,
            "fallback_provider_retries": 99,
        },
        defaults=defaults,
    )
    assert config.min_interval_seconds == 0.0
    assert config.max_concurrent == 8
    assert config.provider_retries == 1
    assert config.retry_max_delay_seconds == 1.0
    assert config.fallback_provider_retries == 5


def test_set_cached_applies_rate_limiter() -> None:
    config = set_cached_slai_image_provider_config(
        normalize_config(
            {
                "min_interval_seconds": 3.0,
                "max_concurrent": 2,
                "provider_retries": 4,
                "retry_base_delay_seconds": 2.0,
                "retry_max_delay_seconds": 20.0,
                "fallback_provider_retries": 1,
            }
        )
    )
    assert config.max_concurrent == 2
