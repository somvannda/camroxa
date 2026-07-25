"""Tests for active/inactive routing and fallback filtering."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.services.ai_routing_service import AIRoutingService


class _FakeSettingsRepo:
    def __init__(self, settings: dict | None = None) -> None:
        self._settings = settings or {}

    async def get_system_setting(self, key: str):
        return self._settings.get(key)

    async def upsert_system_settings(self, values: dict) -> None:
        self._settings.update(values)


@pytest.mark.asyncio
async def test_resolve_text_chain_skips_inactive_fallback_entries() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "lyric": {
                    "provider": "deepseek",
                    "sub_model": "deepseek-chat",
                    "is_active": True,
                },
            },
            "ai_routing_text_fallback_chain": [
                {
                    "provider": "openai",
                    "sub_model": "gpt-4o-mini",
                    "is_active": False,
                },
                {
                    "provider": "slai",
                    "sub_model": "xiaomi/mimo-v2.5-pro",
                    "is_active": True,
                },
            ],
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    chain = await service.resolve_text_chain("lyric")
    providers = [item.provider for item in chain]
    provider_order = list(dict.fromkeys(providers))

    assert provider_order == ["deepseek", "slai"]
    assert "openai" not in providers
    # Intra-provider: preferred deepseek model first, then sibling(s).
    deepseek_models = [item.sub_model for item in chain if item.provider == "deepseek"]
    assert deepseek_models[0] == "deepseek-v4-flash"
    assert "deepseek-v4-pro" in deepseek_models


@pytest.mark.asyncio
async def test_resolve_text_chain_skips_inactive_primary() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "lyric": {
                    "provider": "openai",
                    "sub_model": "gpt-4o-mini",
                    "is_active": False,
                },
            },
            "ai_routing_text_fallback_chain": [
                {
                    "provider": "deepseek",
                    "sub_model": "deepseek-chat",
                    "is_active": True,
                },
            ],
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    chain = await service.resolve_text_chain("lyric")
    providers = [item.provider for item in chain]
    provider_order = list(dict.fromkeys(providers))

    assert provider_order == ["deepseek"]
    assert "openai" not in providers
    assert [item.sub_model for item in chain if item.provider == "deepseek"] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]

@pytest.mark.asyncio
async def test_sanitize_assignments_keeps_suno_for_music_operation() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "music": {"provider": "suno", "sub_model": "V5", "is_active": True},
                "title": {"provider": "suno", "sub_model": "lyrics", "is_active": True},
            },
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    assignments = await service._load_assignments()

    assert "music" in assignments
    assert assignments["music"]["provider"] == "suno"
    assert assignments["music"]["sub_model"] is None
    assert "title" not in assignments
