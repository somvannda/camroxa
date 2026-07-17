"""Tests for itemized split-draft billing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from platform_api.ai.models import TextRouting
from platform_api.ai.purposes.draft_routing import DraftRouting, build_draft_routing
from platform_api.exceptions import ValidationError
from platform_api.services.draft_billing import (
    calculate_batch_draft_cost,
    calculate_split_draft_price,
)


def _routing(
    *,
    lyric_provider: str = "slai",
    lyric_model: str = "xiaomi/mimo-v2.5-pro",
    title_provider: str = "openai",
    title_model: str = "gpt-4o-mini",
    album_provider: str = "slai",
    album_model: str = "xiaomi/mimo-v2.5-pro",
) -> DraftRouting:
    return DraftRouting(
        lyric=TextRouting(provider=lyric_provider, sub_model=lyric_model),
        title=TextRouting(provider=title_provider, sub_model=title_model),
        album=TextRouting(provider=album_provider, sub_model=album_model),
    )


@pytest.mark.asyncio
async def test_calculate_split_draft_price_sums_all_slots() -> None:
    pricing = AsyncMock()

    async def _get_price(ai_service: str, operation_type: str, sub_model: str | None = None) -> int:
        return {
            ("openai", "title"): 32,
            ("slai", "album"): 176,
            ("slai", "lyric"): 216,
        }[(ai_service, operation_type)]

    pricing.get_price = AsyncMock(side_effect=_get_price)

    total = await calculate_split_draft_price(pricing, _routing())
    assert total == 424
    assert pricing.get_price.await_count == 3


@pytest.mark.asyncio
async def test_calculate_split_draft_price_skips_forced_fields() -> None:
    pricing = AsyncMock()
    pricing.get_price = AsyncMock(return_value=10)

    full = await calculate_split_draft_price(pricing, _routing())
    no_title = await calculate_split_draft_price(pricing, _routing(), include_title=False)
    no_album = await calculate_split_draft_price(pricing, _routing(), include_album=False)
    lyric_only = await calculate_split_draft_price(
        pricing, _routing(), include_title=False, include_album=False
    )

    assert full == 30
    assert no_title == 20
    assert no_album == 20
    assert lyric_only == 10


@pytest.mark.asyncio
async def test_calculate_batch_draft_cost_accounts_for_shared_album() -> None:
    pricing = AsyncMock()
    pricing.get_price = AsyncMock(return_value=3)
    routing = _routing()

    assert await calculate_batch_draft_cost(pricing, routing, 1) == 9

    pricing.get_price.reset_mock()
    assert await calculate_batch_draft_cost(pricing, routing, 4) == 27
    assert pricing.get_price.await_count == 5


@pytest.mark.asyncio
async def test_build_draft_routing_uses_per_slot_providers() -> None:
    pricing = AsyncMock()

    async def _get_price(ai_service: str, operation_type: str, sub_model: str | None = None) -> int:
        return {
            ("deepseek", "lyric"): 5,
            ("openai", "title"): 2,
            ("deepseek", "album"): 4,
        }[(ai_service, operation_type)]

    pricing.get_price = AsyncMock(side_effect=_get_price)
    routing = build_draft_routing(
        SimpleNamespace(provider="deepseek", sub_model="deepseek-chat"),
        SimpleNamespace(provider="openai", sub_model="gpt-4o-mini"),
        SimpleNamespace(provider="deepseek", sub_model="deepseek-chat"),
    )

    assert await calculate_split_draft_price(pricing, routing) == 11


@pytest.mark.asyncio
async def test_missing_pricing_raises_validation_error() -> None:
    from platform_api.exceptions import ExternalServiceError

    pricing = AsyncMock()
    pricing.get_price = AsyncMock(
        side_effect=ExternalServiceError("No pricing configured for ai_service 'slai'")
    )

    with pytest.raises(ValidationError, match="Draft generation pricing is not configured"):
        await calculate_split_draft_price(pricing, _routing())
