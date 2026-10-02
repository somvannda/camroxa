"""Tests for public usage-rates payload (website pricing)."""

from __future__ import annotations

import pytest

from platform_api.services.credit_units import CREDIT_SCALE
from platform_api.services.public_usage_rates_service import (
    PUBLIC_OPERATIONS,
    build_public_usage_rates,
)


class _FakeRouting:
    def __init__(self, provider: str = "suno", sub_model: str = "V5") -> None:
        self.provider = provider
        self.sub_model = sub_model


class _FakeRoutingService:
    async def resolve(self, operation_type: str) -> _FakeRouting:
        if operation_type in ("background_image", "thumbnail_image"):
            return _FakeRouting(provider="slai", sub_model="cx/gpt-image-2.5")
        if operation_type == "music":
            return _FakeRouting(provider="suno", sub_model="V5")
        return _FakeRouting(provider="slai", sub_model="xiaomi/mimo-v2.5-pro")


class _FakePricingService:
    """Prices in micro-units (CREDIT_SCALE)."""

    def __init__(self, prices: dict[str, int]) -> None:
        self.prices = prices

    async def get_price(
        self, ai_service: str, operation_type: str, sub_model: str | None = None
    ) -> int:
        del ai_service, sub_model
        return self.prices[operation_type]


@pytest.mark.asyncio
async def test_public_ops_exclude_polish_and_include_draft_image_music() -> None:
    assert "polish" not in PUBLIC_OPERATIONS
    assert PUBLIC_OPERATIONS == (
        "lyric",
        "title",
        "album",
        "music",
        "background_image",
        "thumbnail_image",
        "video",
        "video_merge",
    )


@pytest.mark.asyncio
async def test_estimated_full_song_is_lyric_title_album_plus_one_music() -> None:
    """Overage package estimate uses one Suno charge, not ×2 for Primary + Secondary."""
    prices = {
        "lyric": 5 * CREDIT_SCALE,
        "title": 3 * CREDIT_SCALE,
        "album": 3 * CREDIT_SCALE,
        "music": int(7.5 * CREDIT_SCALE),
        "background_image": 5 * CREDIT_SCALE,
        "thumbnail_image": 5 * CREDIT_SCALE,
        "video": 3 * CREDIT_SCALE,
        "video_merge": 10 * CREDIT_SCALE,
    }
    payload = await build_public_usage_rates(
        routing_service=_FakeRoutingService(),
        pricing_service=_FakePricingService(prices),
    )

    assert [item["operation_type"] for item in payload["items"]] == list(PUBLIC_OPERATIONS)
    assert all(item["available"] for item in payload["items"])
    assert payload["estimated_full_song_credits"] == pytest.approx(5 + 3 + 3 + 7.5)
    assert "Suno package = Primary + Secondary channel" in payload["disclaimer"]
    assert "billed once" in payload["disclaimer"]


@pytest.mark.asyncio
async def test_estimated_full_song_none_when_music_unavailable() -> None:
    class FlakyPricing(_FakePricingService):
        async def get_price(
            self, ai_service: str, operation_type: str, sub_model: str | None = None
        ) -> int:
            if operation_type == "music":
                raise RuntimeError("music pricing missing")
            return await super().get_price(ai_service, operation_type, sub_model)

    prices = {
        "lyric": 5 * CREDIT_SCALE,
        "title": 3 * CREDIT_SCALE,
        "album": 3 * CREDIT_SCALE,
        "music": 75 * CREDIT_SCALE // 10,
        "background_image": 5 * CREDIT_SCALE,
        "thumbnail_image": 5 * CREDIT_SCALE,
    }
    payload = await build_public_usage_rates(
        routing_service=_FakeRoutingService(),
        pricing_service=FlakyPricing(prices),
    )

    music = next(i for i in payload["items"] if i["operation_type"] == "music")
    assert music["available"] is False
    assert payload["estimated_full_song_credits"] is None
