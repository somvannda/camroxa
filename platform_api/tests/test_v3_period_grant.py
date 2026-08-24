"""Period and daily grant lots for the credits-only wallet."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest

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
        lot = {"id": uuid4(), **kwargs}
        self.lots.append(lot)
        return lot

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
