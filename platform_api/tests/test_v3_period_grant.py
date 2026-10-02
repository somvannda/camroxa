"""Period and daily grant lots for the credits-only wallet."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

from platform_api.services.billing_calendar import billing_today
from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.period_grant_service import PeriodGrantService


USER_ID = uuid4()
FREE_PLAN_ID = uuid4()
PAID_PLAN_ID = uuid4()


class FakeWallet:
    def __init__(self, balance: int = 0) -> None:
        self.balance = balance
        self.txs: list[dict] = []

    async def get_balance(self, user_id: UUID | str) -> int:
        return self.balance

    async def add_credits(self, user_id, amount: int, reason: str, ref_id=None, **kwargs) -> int:
        self.balance += amount
        self.txs.append({"reason": reason, "amount": amount, "ref_id": ref_id})
        return self.balance

    async def atomic_deduct(self, user_id, amount: int, reason: str, ref_id=None, metadata=None) -> bool:
        if self.balance < amount:
            return False
        self.balance -= amount
        return True


class FakeStore:
    def __init__(self, plan: dict | None) -> None:
        self.plan = plan
        self.license_plan = plan
        self.lots: list[dict] = []

    async def resolve_charge_plan(self, user_id: UUID) -> dict | None:
        return self.plan

    async def get_plan_for_user(self, user_id: UUID) -> dict | None:
        return self.license_plan

    async def find_period_grant(self, user_id: UUID, period_start: date) -> dict | None:
        for lot in self.lots:
            if lot["tag"] == "grant" and lot["period_start"] == period_start:
                return lot
        return None

    async def find_daily_grant(self, user_id: UUID, period_start: date) -> dict | None:
        for lot in self.lots:
            if lot["tag"] == "daily_grant" and lot["period_start"] == period_start:
                return lot
        return None

    async def insert_lot(self, **kwargs) -> dict:
        if "remaining_units" not in kwargs:
            kwargs["remaining_units"] = kwargs["amount_units"]
        lot = {"id": uuid4(), **kwargs}
        self.lots.append(lot)
        return lot

    async def insert_lot_if_absent(self, **kwargs) -> dict | None:
        tag = kwargs["tag"]
        period_start = kwargs.get("period_start")
        user_id = kwargs["user_id"]
        if tag == "daily_grant" and await self.find_daily_grant(user_id, period_start):
            return None
        if tag == "grant" and await self.find_period_grant(user_id, period_start):
            return None
        return await self.insert_lot(**kwargs)

    async def top_up_period_grant(self, lot_id, *, target_units: int, expires_at) -> int:
        for lot in self.lots:
            if lot["id"] != lot_id:
                continue
            delta = target_units - int(lot["amount_units"])
            if delta <= 0:
                return 0
            lot["amount_units"] = target_units
            lot["remaining_units"] = int(lot["remaining_units"]) + delta
            lot["expires_at"] = expires_at
            return delta
        return 0

    async def get_web_subscription_period_start(self, user_id: UUID) -> date | None:
        return None

    async def expired_grant_lots(self, user_id: UUID | None = None) -> list[dict]:
        return []

    async def zero_lot_remaining(self, lot_id: UUID) -> None:
        return None


def _free_plan() -> dict:
    return {
        "id": str(FREE_PLAN_ID),
        "name": "Free",
        "price_cents": 0,
        "monthly_credits": 0,
        "daily_credits": 50,
        "billing_cycle_days": 30,
    }


def _paid_plan() -> dict:
    return {
        "id": str(PAID_PLAN_ID),
        "name": "Starter",
        "price_cents": 1000,
        "monthly_credits": 1000,
        "daily_credits": 0,
        "billing_cycle_days": 30,
    }


@pytest.mark.asyncio
async def test_daily_grant_mints_free_plan_credits() -> None:
    wallet = FakeWallet()
    store = FakeStore(_free_plan())
    service = PeriodGrantService(store=store, credit_repo=wallet)

    first = await service.ensure_daily_grant(USER_ID)
    assert first["granted"] is True
    assert first["credits"] == 50
    assert wallet.balance == credits_to_units(50)
    assert store.lots[0]["tag"] == "daily_grant"

    second = await service.ensure_daily_grant(USER_ID)
    assert second["granted"] is False
    assert second["reason"] == "already_granted"
    assert wallet.balance == credits_to_units(50)


@pytest.mark.asyncio
async def test_daily_grant_skips_paid_plan_with_zero_daily() -> None:
    wallet = FakeWallet()
    store = FakeStore(_paid_plan())
    service = PeriodGrantService(store=store, credit_repo=wallet)

    result = await service.ensure_daily_grant(USER_ID)
    assert result["granted"] is False
    assert result["reason"] == "no_daily_credits"
    assert wallet.balance == 0
    assert store.lots == []


@pytest.mark.asyncio
async def test_period_grant_uses_paid_web_plan() -> None:
    wallet = FakeWallet()
    store = FakeStore(_paid_plan())
    store.license_plan = None
    service = PeriodGrantService(store=store, credit_repo=wallet)

    first = await service.ensure_period_grant(USER_ID)
    assert first["granted"] is True
    assert first["credits"] == 1000
    assert wallet.balance == credits_to_units(1000)
    assert store.lots[0]["tag"] == "grant"

    second = await service.ensure_period_grant(USER_ID)
    assert second["granted"] is False
    assert second["reason"] == "already_granted"
    assert wallet.balance == credits_to_units(1000)


@pytest.mark.asyncio
async def test_daily_grant_does_not_credit_when_lot_insert_fails() -> None:
    """Regression: wallet must not move if the daily_grant lot is rejected."""
    wallet = FakeWallet()
    store = FakeStore(_free_plan())

    async def boom(**kwargs):
        raise RuntimeError("lot tag rejected")

    store.insert_lot_if_absent = boom  # type: ignore[method-assign]
    service = PeriodGrantService(store=store, credit_repo=wallet)

    with pytest.raises(RuntimeError, match="lot tag rejected"):
        await service.ensure_daily_grant(USER_ID)
    assert wallet.balance == 0
    assert wallet.txs == []


@pytest.mark.asyncio
async def test_daily_grant_race_conflict_does_not_credit() -> None:
    wallet = FakeWallet()
    store = FakeStore(_free_plan())

    async def miss(user_id, period_start):
        return None

    async def conflict(**kwargs):
        return None

    store.find_daily_grant = miss  # type: ignore[method-assign]
    store.insert_lot_if_absent = conflict  # type: ignore[method-assign]
    service = PeriodGrantService(store=store, credit_repo=wallet)

    result = await service.ensure_daily_grant(USER_ID)
    assert result["granted"] is False
    assert result["reason"] == "already_granted"
    assert wallet.balance == 0
    assert wallet.txs == []


@pytest.mark.asyncio
async def test_period_grant_does_not_credit_when_lot_insert_fails() -> None:
    wallet = FakeWallet()
    store = FakeStore(_paid_plan())

    async def boom(**kwargs):
        raise RuntimeError("lot insert failed")

    store.insert_lot_if_absent = boom  # type: ignore[method-assign]
    service = PeriodGrantService(store=store, credit_repo=wallet)

    with pytest.raises(RuntimeError, match="lot insert failed"):
        await service.ensure_period_grant(USER_ID)
    assert wallet.balance == 0
    assert wallet.txs == []


@pytest.mark.asyncio
async def test_period_grant_anchors_to_web_subscription_period() -> None:
    """CutLuy web subscribers have no license; anchor the period to their subscription."""
    wallet = FakeWallet()
    store = FakeStore(_paid_plan())
    store.license_plan = None
    anchor = date(2026, 9, 1)

    async def web_period(user_id: UUID) -> date:
        return anchor

    store.get_web_subscription_period_start = web_period  # type: ignore[method-assign]
    service = PeriodGrantService(store=store, credit_repo=wallet)

    result = await service.ensure_period_grant(USER_ID)
    assert result["granted"] is True
    assert result["period_start"] == anchor.isoformat()
    assert store.lots[0]["period_start"] == anchor


@pytest.mark.asyncio
async def test_period_grant_tops_up_smaller_same_period_lot() -> None:
    """Free -> paid on the same day grows the existing grant instead of skipping it."""
    wallet = FakeWallet(balance=credits_to_units(50))
    store = FakeStore(_paid_plan())
    store.license_plan = None
    period_start = billing_today()
    store.lots.append(
        {
            "id": uuid4(),
            "user_id": USER_ID,
            "tag": "grant",
            "amount_units": credits_to_units(50),
            "remaining_units": credits_to_units(50),
            "expires_at": None,
            "period_start": period_start,
        }
    )
    service = PeriodGrantService(store=store, credit_repo=wallet)

    result = await service.ensure_period_grant(USER_ID)
    assert result["granted"] is True
    assert result["reason"] == "grant_upgraded"
    assert result["credits"] == 950
    assert wallet.balance == credits_to_units(1000)
    assert store.lots[0]["amount_units"] == credits_to_units(1000)

    again = await service.ensure_period_grant(USER_ID)
    assert again["granted"] is False
    assert again["reason"] == "already_granted"
    assert wallet.balance == credits_to_units(1000)
