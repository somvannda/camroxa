"""Tests for yearly-plan monthly credit resets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from platform_api.services.v2.subscription_service import (
    MONTHLY_CREDIT_RESET_DAYS,
    Subscription,
    SubscriptionService,
    next_credit_reset_at,
)


def test_subscription_service_wraps_raw_pool() -> None:
    """Regression: the startup loop passed a raw asyncpg pool, so fetch_all /
    fetch_one were missing and process_due_subscriptions crashed every 15 min."""

    class RawPool:
        pass

    service = SubscriptionService(db=RawPool(), cutluy=object())
    assert hasattr(service._db, "fetch_all")
    assert hasattr(service._db, "fetch_one")


def test_subscription_service_keeps_existing_adapter() -> None:
    from platform_api.db.asyncpg_adapter import AsyncpgPoolAdapter

    class RawPool:
        pass

    adapter = AsyncpgPoolAdapter(RawPool())
    service = SubscriptionService(db=adapter, cutluy=object())
    assert service._db is adapter


def test_next_credit_reset_at_monthly_uses_billing_period_end() -> None:
    period_end = datetime(2026, 9, 1, 0, 0, 0)
    last_reset = datetime(2026, 8, 1, 0, 0, 0)
    assert next_credit_reset_at(
        billing_cycle="monthly",
        current_period_end=period_end,
        last_credit_reset=last_reset,
    ) == period_end


def test_next_credit_reset_at_yearly_uses_30_day_cadence() -> None:
    period_end = datetime(2027, 1, 1, 0, 0, 0)
    last_reset = datetime(2026, 8, 1, 0, 0, 0)
    assert next_credit_reset_at(
        billing_cycle="yearly",
        current_period_end=period_end,
        last_credit_reset=last_reset,
    ) == last_reset + timedelta(days=MONTHLY_CREDIT_RESET_DAYS)


@pytest.mark.asyncio
async def test_reset_quota_if_needed_refreshes_yearly_mid_cycle() -> None:
    service = SubscriptionService.__new__(SubscriptionService)
    service._db = AsyncMock()
    service._log_monthly_credit_reset = AsyncMock()
    service._sync_v3_period_grant = AsyncMock()
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id="sub-1",
        user_id="user-1",
        plan_id="plan-1",
        status="active",
        billing_cycle="yearly",
        current_period_start=now - timedelta(days=60),
        current_period_end=now + timedelta(days=300),
        cancel_at_period_end=False,
        monthly_credits_granted=500,
        monthly_credits_used=120,
        topup_credits_balance=0,
        external_subscription_id=None,
        last_credit_reset=now - timedelta(days=MONTHLY_CREDIT_RESET_DAYS + 1),
    )

    reset = await service.reset_quota_if_needed(subscription)

    assert reset is True
    service._db.execute.assert_awaited_once()
    service._log_monthly_credit_reset.assert_awaited_once_with(
        user_id="user-1",
        subscription_id="sub-1",
        monthly_credits=500,
    )


@pytest.mark.asyncio
async def test_reset_quota_if_needed_skips_yearly_before_monthly_due() -> None:
    service = SubscriptionService.__new__(SubscriptionService)
    service._db = AsyncMock()
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id="sub-1",
        user_id="user-1",
        plan_id="plan-1",
        status="active",
        billing_cycle="yearly",
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=360),
        cancel_at_period_end=False,
        monthly_credits_granted=500,
        monthly_credits_used=10,
        topup_credits_balance=0,
        external_subscription_id=None,
        last_credit_reset=now - timedelta(days=5),
    )

    reset = await service.reset_quota_if_needed(subscription)

    assert reset is False
    service._db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_user_subscription_survives_missing_plan_row() -> None:
    service = SubscriptionService.__new__(SubscriptionService)
    now = datetime.now(timezone.utc)
    row = {
        "id": "sub-1",
        "user_id": "user-1",
        "plan_id": "missing-plan",
        "status": "active",
        "billing_cycle": "monthly",
        "current_period_start": now - timedelta(days=1),
        "current_period_end": now + timedelta(days=29),
        "cancel_at_period_end": False,
        "monthly_credits_granted": 1000,
        "monthly_credits_used": 23,
        "topup_credits_balance": 400,
        "external_subscription_id": None,
        "last_credit_reset": now - timedelta(days=1),
        "created_at": now - timedelta(days=1),
        "cancelled_at": None,
        "plan_name": "Pro",
    }
    service._db = AsyncMock()
    service._db.fetch_one = AsyncMock(side_effect=[row, dict(row)])
    service.reset_quota_if_needed = AsyncMock(return_value=False)

    result = await service.get_user_subscription("user-1")

    sql = service._db.fetch_one.await_args_list[0].args[0]
    assert "LEFT JOIN plans" in sql
    assert "current_period_end > NOW()" in sql
    assert result is not None
    assert result["plan_name"] == "Pro"
    assert result["total_credits_available"] == 1377


@pytest.mark.asyncio
async def test_reset_quota_if_needed_expires_at_period_end() -> None:
    """CutLuy is one-time: an ended period must expire, never silently renew.

    Regression: the maintenance loop used to advance current_period_end and
    re-grant the monthly credits with no payment, so every web subscriber renewed
    for free forever.
    """
    service = SubscriptionService.__new__(SubscriptionService)
    service._db = AsyncMock()
    service._log_monthly_credit_reset = AsyncMock()
    service._sync_v3_period_grant = AsyncMock()
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id="sub-1",
        user_id="user-1",
        plan_id="plan-1",
        status="active",
        billing_cycle="monthly",
        current_period_start=now - timedelta(days=30),
        current_period_end=now - timedelta(hours=1),
        cancel_at_period_end=False,
        monthly_credits_granted=1000,
        monthly_credits_used=1000,
        topup_credits_balance=0,
        external_subscription_id=None,
        last_credit_reset=now - timedelta(days=30),
    )

    reset = await service.reset_quota_if_needed(subscription)

    assert reset is False
    sql, *args = service._db.execute.await_args.args
    assert "status = 'expired'" in sql
    assert args == ["sub-1"]
    # No new period, no re-grant.
    service._sync_v3_period_grant.assert_not_awaited()
    service._log_monthly_credit_reset.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_quota_if_needed_monthly_before_period_end_does_nothing() -> None:
    service = SubscriptionService.__new__(SubscriptionService)
    service._db = AsyncMock()
    now = datetime.now(timezone.utc)
    subscription = Subscription(
        id="sub-1",
        user_id="user-1",
        plan_id="plan-1",
        status="active",
        billing_cycle="monthly",
        current_period_start=now - timedelta(days=5),
        current_period_end=now + timedelta(days=25),
        cancel_at_period_end=False,
        monthly_credits_granted=1000,
        monthly_credits_used=10,
        topup_credits_balance=0,
        external_subscription_id=None,
        last_credit_reset=now - timedelta(days=5),
    )

    reset = await service.reset_quota_if_needed(subscription)

    assert reset is False
    service._db.execute.assert_not_awaited()
