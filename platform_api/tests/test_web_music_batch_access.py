"""Batch generation is a credit-pack feature (packs-only billing).

The Free plan grants 50 credits per month for **single** songs. Batch sizes above
1 unlock only with a pack purchase (or a grandfathered paid plan), which the quota
payload exposes as ``premium_unlocked``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.services.web_music_service import WebMusicService


USER_ID = uuid4()


def _free_plan() -> dict:
    return {
        "id": str(uuid4()),
        "name": "free",
        "price_cents": 0,
        "monthly_credits": 50,
        "daily_credits": 0,
        "music_credits": 10,
    }


def _bridge(*, spendable: int, premium_unlocked: bool) -> SimpleNamespace:
    return SimpleNamespace(
        spendable_credits=AsyncMock(return_value=(spendable, 10, False)),
        premium_unlocked=AsyncMock(return_value=premium_unlocked),
    )


def _service(*, flag_on: bool, spendable: int, premium_unlocked: bool) -> WebMusicService:
    service = WebMusicService(MagicMock(), MagicMock())
    service._credits_only_v3_enabled = AsyncMock(return_value=flag_on)
    service._web_music_charge_bridge = lambda: _bridge(
        spendable=spendable, premium_unlocked=premium_unlocked
    )
    service._with_queue_fields = AsyncMock(
        side_effect=lambda _uid, quota: {**quota, "queue_limit": 20, "queue_used": 0}
    )
    service._has_pro = AsyncMock(return_value=False)
    service._has_web_subscription = AsyncMock(return_value=False)
    service._has_paid_web_subscription = AsyncMock(return_value=False)
    service._v3_store_service = MagicMock(return_value=SimpleNamespace(
        get_active_free_plan=AsyncMock(return_value=_free_plan())
    ))
    return service


def _legacy_balance(*, topup: int, has_subscription: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        total_available=50 + topup,
        has_subscription=has_subscription,
        monthly_granted=50,
        monthly_used=0,
        topup_balance=topup,
        daily_free_limit=0,
        daily_free_used=0,
        daily_free_remaining=0,
    )


@pytest.mark.asyncio
async def test_free_plan_with_50_credits_cannot_batch() -> None:
    service = _service(flag_on=True, spendable=50, premium_unlocked=False)

    payload = await service.usage_today(USER_ID)

    assert payload["credits_remaining"] == 50
    assert payload["premium_unlocked"] is False


@pytest.mark.asyncio
async def test_pack_buyer_can_batch() -> None:
    service = _service(flag_on=True, spendable=8_731, premium_unlocked=True)

    payload = await service.usage_today(USER_ID)

    assert payload["premium_unlocked"] is True


@pytest.mark.asyncio
async def test_usage_today_is_v3_only_even_when_flag_off() -> None:
    # Credits-only: the legacy v2 ledger must be ignored entirely, even if the
    # old feature flag is off. Quota always comes from the v3 wallet.
    service = _service(flag_on=False, spendable=50, premium_unlocked=False)
    service._credit_service = SimpleNamespace(
        get_detailed_balance=AsyncMock(return_value=_legacy_balance(topup=8_681))
    )

    payload = await service.usage_today(USER_ID)

    assert payload["credits_remaining"] == 50
    assert payload["premium_unlocked"] is False


def test_legacy_pack_unlocked_reads_topup_and_grandfathered_plan() -> None:
    service = WebMusicService(MagicMock(), MagicMock())

    assert service._legacy_pack_unlocked(_legacy_balance(topup=0)) is False
    assert service._legacy_pack_unlocked(_legacy_balance(topup=100)) is True
    assert (
        service._legacy_pack_unlocked(_legacy_balance(topup=0, has_subscription=True)) is True
    )
