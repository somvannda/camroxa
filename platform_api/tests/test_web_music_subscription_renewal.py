"""Web-music subscription renewal (CutLuy one-time → fresh charge)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from platform_api.services.v2.subscription_service import (
    RENEWAL_WINDOW_DAYS,
    SubscriptionService,
)


def _service() -> SubscriptionService:
    service = SubscriptionService.__new__(SubscriptionService)
    service._db = AsyncMock()
    service._sync_v3_period_grant = AsyncMock()
    return service


def _offer_row(*, days_to_end: int, price_cents: int = 500) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": "sub-1",
        "plan_id": "plan-1",
        "status": "active",
        "billing_cycle": "monthly",
        "current_period_start": now - timedelta(days=25),
        "current_period_end": now + timedelta(days=days_to_end),
        "cancel_at_period_end": False,
        "monthly_credits_granted": 1000,
        "plan_name": "Starter",
        "price_cents": price_cents,
        "monthly_credits": 1000,
        "billing_cycle_days": 30,
    }


@pytest.mark.asyncio
async def test_renewal_offer_renewable_within_window() -> None:
    service = _service()
    service._db.fetch_one = AsyncMock(return_value=_offer_row(days_to_end=5))

    offer = await service.get_renewal_offer("user-1")

    assert offer is not None
    assert offer["eligible"] is True
    assert offer["renewable"] is True
    assert offer["renewal_window_days"] == RENEWAL_WINDOW_DAYS
    # `.days` truncates, so a "5 days out" timestamp can read 4 at the boundary.
    assert offer["days_left"] in (4, 5)


@pytest.mark.asyncio
async def test_renewal_offer_closed_far_out() -> None:
    service = _service()
    service._db.fetch_one = AsyncMock(return_value=_offer_row(days_to_end=20))

    offer = await service.get_renewal_offer("user-1")

    assert offer is not None
    assert offer["renewable"] is False
    assert offer["renewal_opens_in_days"] in (12, 13)


@pytest.mark.asyncio
async def test_renewal_offer_none_for_free_plan() -> None:
    service = _service()
    service._db.fetch_one = AsyncMock(
        return_value=_offer_row(days_to_end=5, price_cents=0)
    )

    assert await service.get_renewal_offer("user-1") is None


@pytest.mark.asyncio
async def test_fulfill_renewal_stacks_from_future_period_end() -> None:
    service = _service()
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=3)
    service.get_plan_by_id = AsyncMock(
        return_value=SimpleNamespace(monthly_credits=1000, billing_cycle_days=30)
    )
    service._db.fetch_one = AsyncMock(return_value={"id": "sub-1"})
    row = {"id": "sub-1", "plan_id": "plan-1", "current_period_end": end}

    ok = await service._fulfill_renewal(row, "pay_1")

    assert ok is True
    args = service._db.fetch_one.await_args.args
    assert args[1] == end
    assert args[2] == end + timedelta(days=30)
    service._sync_v3_period_grant.assert_awaited_once_with("sub-1")


@pytest.mark.asyncio
async def test_fulfill_renewal_starts_now_when_expired() -> None:
    service = _service()
    service.get_plan_by_id = AsyncMock(
        return_value=SimpleNamespace(monthly_credits=2300, billing_cycle_days=30)
    )
    service._db.fetch_one = AsyncMock(return_value={"id": "sub-1"})
    expired = datetime.now(timezone.utc) - timedelta(days=10)
    row = {"id": "sub-1", "plan_id": "plan-1", "current_period_end": expired}

    before = datetime.now(timezone.utc)
    ok = await service._fulfill_renewal(row, "pay_1")
    after = datetime.now(timezone.utc)

    assert ok is True
    args = service._db.fetch_one.await_args.args
    base = args[1]
    assert before <= base <= after
    assert args[2] == base + timedelta(days=30)


@pytest.mark.asyncio
async def test_fulfill_renewal_is_idempotent_per_payment() -> None:
    service = _service()
    service.get_plan_by_id = AsyncMock(
        return_value=SimpleNamespace(monthly_credits=1000, billing_cycle_days=30)
    )
    service._db.fetch_one = AsyncMock(return_value=None)  # UPDATE matched no row
    row = {
        "id": "sub-1",
        "plan_id": "plan-1",
        "current_period_end": datetime.now(timezone.utc) + timedelta(days=3),
    }

    ok = await service._fulfill_renewal(row, "pay_1")

    assert ok is False
    service._sync_v3_period_grant.assert_not_awaited()
