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


@pytest.mark.asyncio
async def test_resolve_music_chain_orders_primary_then_fallback() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "music": {"provider": "suno", "sub_model": None, "is_active": True},
            },
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    chain = await service.resolve_music_chain("music")

    # Primary first, then the configured chain, deduped.
    assert [item.provider for item in chain] == ["suno", "camxora_music_api"]
    assert all(item.sub_model is None for item in chain)


@pytest.mark.asyncio
async def test_resolve_music_chain_skips_inactive_fallback() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "music": {"provider": "suno", "is_active": True},
            },
            "ai_routing_music_fallback_chain": [
                {"provider": "camxora_music_api", "is_active": False},
            ],
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    chain = await service.resolve_music_chain("music")

    assert [item.provider for item in chain] == ["suno"]


@pytest.mark.asyncio
async def test_resolve_music_chain_falls_back_when_primary_has_no_keys() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "music": {"provider": "suno", "is_active": True},
            },
        }
    )

    async def _pool_status(provider: str) -> dict:
        return {"active_keys": 1 if provider == "camxora_music_api" else 0}

    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(side_effect=_pool_status)

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    chain = await service.resolve_music_chain("music")

    assert [item.provider for item in chain] == ["camxora_music_api"]


@pytest.mark.asyncio
async def test_save_music_fallback_chain_rejects_non_music_provider() -> None:
    from platform_api.exceptions import ValidationError

    service = AIRoutingService(
        settings_repo=_FakeSettingsRepo(),
        key_pool_service=AsyncMock(),
    )
    with pytest.raises(ValidationError):
        await service.save_music_fallback_chain([{"provider": "deepseek"}])


@pytest.mark.asyncio
async def test_resolve_skips_inactive_primary_assignment() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "lyric": {
                    "provider": "openai",
                    "sub_model": "gpt-4o-mini",
                    "is_active": False,
                },
            },
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    routing = await service.resolve("lyric")

    assert routing.provider == "deepseek"


@pytest.mark.asyncio
async def test_resolve_falls_back_when_primary_has_no_keys() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "lyric": {
                    "provider": "openai",
                    "sub_model": "gpt-4o-mini",
                    "is_active": True,
                },
            },
        }
    )

    async def _pool_status(provider: str) -> dict:
        return {"active_keys": 1 if provider == "deepseek" else 0}

    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(side_effect=_pool_status)

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    routing = await service.resolve("lyric")

    assert routing.provider == "deepseek"


@pytest.mark.asyncio
async def test_resolve_raises_only_when_no_provider_has_keys() -> None:
    from platform_api.exceptions import NoAvailableKeysError

    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "lyric": {
                    "provider": "openai",
                    "sub_model": "gpt-4o-mini",
                    "is_active": True,
                },
            },
        }
    )
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 0})

    service = AIRoutingService(settings_repo=settings, key_pool_service=key_pool)
    with pytest.raises(NoAvailableKeysError):
        await service.resolve("lyric")


@pytest.mark.asyncio
async def test_save_assignments_rejects_unregistered_model() -> None:
    from platform_api.exceptions import ValidationError

    service = AIRoutingService(
        settings_repo=_FakeSettingsRepo(), key_pool_service=AsyncMock()
    )
    with pytest.raises(ValidationError):
        await service.save_assignments(
            {"lyric": {"provider": "deepseek", "sub_model": "does-not-exist"}}
        )


@pytest.mark.asyncio
async def test_save_assignments_rejects_empty_payload() -> None:
    from platform_api.exceptions import ValidationError

    service = AIRoutingService(
        settings_repo=_FakeSettingsRepo(), key_pool_service=AsyncMock()
    )
    with pytest.raises(ValidationError):
        await service.save_assignments({})


@pytest.mark.asyncio
async def test_snapshot_and_restore_config() -> None:
    settings = _FakeSettingsRepo(
        {
            "ai_routing_assignments": {
                "lyric": {
                    "provider": "deepseek",
                    "sub_model": "deepseek-v4-flash",
                    "is_active": True,
                },
            },
            "ai_routing_text_fallback_chain": [
                {
                    "provider": "slai",
                    "sub_model": "xiaomi/mimo-v2.5-pro",
                    "is_active": True,
                },
            ],
        }
    )
    service = AIRoutingService(settings_repo=settings, key_pool_service=AsyncMock())

    snapshot = await service.snapshot_config()
    await service.save_assignments(
        {"lyric": {"provider": "openai", "sub_model": "gpt-4o-mini"}}
    )
    assert (await service._load_assignments())["lyric"]["provider"] == "openai"

    await service.restore_config(snapshot)
    restored = await service._load_assignments()
    assert restored["lyric"]["provider"] == "deepseek"
    assert restored["lyric"]["sub_model"] == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_save_assignments_persists_canonical_model_id() -> None:
    settings = _FakeSettingsRepo()
    service = AIRoutingService(settings_repo=settings, key_pool_service=AsyncMock())

    await service.save_assignments(
        {"lyric": {"provider": "deepseek", "sub_model": "deepseek-chat"}}
    )

    stored = await settings.get_system_setting("ai_routing_assignments")
    assert stored["lyric"]["sub_model"] == "deepseek-v4-flash"
