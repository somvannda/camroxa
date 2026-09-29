"""Renewal carry-over: leftover grant + allowance become the next period's grant."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.models.domain import Plan
from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.period_grant_service import PeriodGrantService


@pytest.mark.asyncio
async def test_carryover_adds_leftover_to_allowance_and_zeroes_old_lots() -> None:
    user_id = uuid4()
    plan = Plan(id=uuid4(), name="Monthly · 2-channel", price_cents=7900, billing_cycle_days=30)
    ctx = MagicMock()
    ctx.plan = plan
    ctx.activated_at = datetime.now(timezone.utc) - timedelta(days=2)

    store = MagicMock()
    store.find_period_grant = AsyncMock(return_value=None)
    store.grant_remaining_units = AsyncMock(return_value=credits_to_units(100))
    store.list_lots = AsyncMock(
        return_value=[
            {"id": uuid4(), "tag": "grant", "remaining_units": credits_to_units(100)},
            {"id": uuid4(), "tag": "pack", "remaining_units": credits_to_units(50)},
        ]
    )
    store.zero_lot_remaining = AsyncMock()
    store.insert_lot_if_absent = AsyncMock(return_value={"id": uuid4()})

    credit_repo = MagicMock()
    credit_repo.add_credits = AsyncMock()
    credit_repo.get_balance = AsyncMock(return_value=credits_to_units(5250))

    plan_repo = MagicMock()
    plan_repo.get_user_active_subscription_context = AsyncMock(return_value=ctx)

    service = PeriodGrantService(store=store, credit_repo=credit_repo, plan_repo=plan_repo)
    result = await service.carryover_period_grant(
        user_id=user_id,
        monthly_credits=5150,
        billing_cycle_days=30,
        new_expires_at=datetime.now(timezone.utc) + timedelta(days=58),
    )

    assert result["granted"] is True
    assert result["carried_credits"] == 100

    # New lot = leftover (100) + allowance (5150) = 5250 credits.
    insert_kwargs = store.insert_lot_if_absent.await_args.kwargs
    assert insert_kwargs["amount_units"] == credits_to_units(5250)
    assert insert_kwargs["tag"] == "grant"

    # Only the new allowance is added to the wallet (the leftover is already there).
    assert credit_repo.add_credits.await_args.args[1] == credits_to_units(5150)

    # Only the expiring grant lot is zeroed; the non-expiring pack is untouched.
    assert store.zero_lot_remaining.await_count == 1


@pytest.mark.asyncio
async def test_carryover_is_idempotent_for_the_same_period() -> None:
    store = MagicMock()
    store.find_period_grant = AsyncMock(return_value={"id": uuid4()})
    store.grant_remaining_units = AsyncMock()
    store.insert_lot_if_absent = AsyncMock()
    credit_repo = MagicMock()
    credit_repo.add_credits = AsyncMock()

    service = PeriodGrantService(store=store, credit_repo=credit_repo, plan_repo=None)
    result = await service.carryover_period_grant(
        user_id=uuid4(),
        monthly_credits=5150,
        billing_cycle_days=30,
        new_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    assert result["granted"] is False
    store.insert_lot_if_absent.assert_not_awaited()
    credit_repo.add_credits.assert_not_awaited()
