"""Tests for get_available_providers DB-backed cost display."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.services.ai_routing_service import AIRoutingService


class _FakeModelCostRepo:
    async def get_all(self) -> list[dict]:
        return [
            {
                "ai_service": "suno",
                "sub_model": "lyrics",
                "operation_type": "lyric",
                "cost_usd": 0.004,
            },
            {
                "ai_service": "deepseek",
                "sub_model": "deepseek-v4-flash",
                "operation_type": "title",
                "cost_usd": 0.00012,
            },
        ]


@pytest.mark.asyncio
async def test_get_available_providers_uses_db_costs_and_operation_filter() -> None:
    key_pool = AsyncMock()
    key_pool.get_pool_status = AsyncMock(return_value={"active_keys": 1})

    service = AIRoutingService(
        settings_repo=AsyncMock(),
        key_pool_service=key_pool,
        model_cost_repo=_FakeModelCostRepo(),
    )
    providers = await service.get_available_providers()
    text = providers["text_generation"]

    suno = next(item for item in text if item["provider"] == "suno")
    lyrics_detail = next(d for d in suno["sub_models_detail"] if d["name"] == "lyrics")
    assert lyrics_detail["cost_usd_by_operation"] == {"lyric": 0.004}
    assert lyrics_detail["cost_usd"] == 0.004
    assert lyrics_detail["cost_tier"] == "~0.4 credits (~$0.004)"
    assert lyrics_detail["operations"] == ["lyric"]

    deepseek = next(item for item in text if item["provider"] == "deepseek")
    flash_detail = next(
        d for d in deepseek["sub_models_detail"] if d["name"] == "deepseek-v4-flash"
    )
    assert flash_detail["cost_usd_by_operation"]["title"] == 0.00012
    assert "title" in flash_detail["operations"]
    assert "deepseek-v4-pro" in deepseek["sub_models"]