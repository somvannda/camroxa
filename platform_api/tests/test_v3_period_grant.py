"""Period and daily grant lots for the credits-only wallet."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from platform_api.services.billing_calendar import next_billing_midnight
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

    async def insert_lot_if_absent(self, **kwargs) -> dict | None:
        tag = kwargs["tag"]
        period_start = kwargs.get("period_start")
        user_id = kwargs["user_id"]
        if tag == "daily_grant" and await self.find_daily_grant(user_id, period_start):
            return None
        if tag == "grant" and await self.find_period_grant(user_id, period_start):
            return None
        return await self.insert_lot(**kwargs)

    async def grow_period_lot(
        self, lot_id: UUID, extra_units: int, *, below_units: int
    ) -> bool:
        for lot in self.lots:
            if str(lot["id"]) != str(lot_id):
                continue
            if int(lot["amount_units"]) >= below_units:
                return False
            lot["amount_units"] = int(lot["amount_units"]) + extra_units
            lot["remaining_units"] = int(lot.get("remaining_units") or 0) + extra_units
            return True
        return False

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


def _monthly_free_plan() -> dict:
    """Production-shape Free plan: 50 credits/month, no daily allowance."""
    return {
        "id": str(FREE_PLAN_ID),
        "name": "Free",
        "price_cents": 0,
        "monthly_credits": 50,
        "daily_credits": 0,
        "billing_cycle_days": 30,
    }


class FakePlanRepo:
    """License lookup; `ctx=None` mirrors a license-less Free account."""

    def __init__(self, ctx: object | None = None) -> None:
        self.ctx = ctx

    async def get_user_active_subscription_context(self, user_id: UUID) -> object | None:
        return self.ctx


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
async def test_period_grant_grants_full_allowance_on_paid_upgrade() -> None:
    """A paid upgrade must grant the full allowance, not net off free usage.

    Regression (part 1): the Free monthly ``grant`` lot occupies the unique
    ``(user_id, period_start)`` slot, so the paid allowance used to be silently
    skipped and a just-paid user kept only their leftover Free credits.
    Regression (part 2): the grant must not be reduced by credits the user
    already spent on the Free plan — a top-up adds the full plan allowance.
    """
    wallet = FakeWallet()
    store = FakeStore(_monthly_free_plan())
    service = PeriodGrantService(store=store, credit_repo=wallet)

    free = await service.ensure_period_grant(USER_ID)
    assert free["granted"] is True
    assert wallet.balance == credits_to_units(50)

    # Same period, now on the paid plan (e.g. Free -> Starter at $5 / 1,000).
    store.plan = _paid_plan()
    store.license_plan = _paid_plan()

    upgraded = await service.ensure_period_grant(USER_ID)
    assert upgraded["granted"] is True
    assert upgraded["credits"] == 1000
    # Full paid allowance added on top of the untouched Free balance (50).
    assert wallet.balance == credits_to_units(1050)
    assert len(store.lots) == 1
    assert store.lots[0]["amount_units"] == credits_to_units(1050)

    # Idempotent: the lot now holds at least the allowance, so re-runs do not
    # re-credit.
    again = await service.ensure_period_grant(USER_ID)
    assert again["granted"] is False
    assert again["reason"] == "already_granted"
    assert wallet.balance == credits_to_units(1050)


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
async def test_period_grant_anchors_license_less_free_to_calendar_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a monthly Free grant must not restack every day.

    The monthly allowance was anchored to ``billing_today()`` for accounts with no
    subscription/license (the Free plan, monthly 50 / daily 0), so it minted 50
    credits every day and, because each lot lived a full billing cycle, the grants
    stacked. It must be one grant per calendar month that expires at the next
    month start.
    """
    wallet = FakeWallet()
    store = FakeStore(_monthly_free_plan())
    service = PeriodGrantService(
        store=store, credit_repo=wallet, plan_repo=FakePlanRepo(ctx=None)
    )

    oct_start = date(2026, 10, 1)
    nov_start = date(2026, 11, 1)
    nov_midnight = datetime(2026, 11, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "platform_api.services.v3.period_grant_service.billing_month_start",
        lambda *args, **kwargs: oct_start,
    )
    monkeypatch.setattr(
        "platform_api.services.v3.period_grant_service.next_billing_month_start",
        lambda **kwargs: nov_midnight,
    )

    first = await service.ensure_period_grant(USER_ID)
    assert first["granted"] is True
    assert store.lots[0]["tag"] == "grant"
    assert store.lots[0]["period_start"] == oct_start
    assert store.lots[0]["expires_at"] == nov_midnight
    assert wallet.balance == credits_to_units(50)

    # A later poll in the same month does not mint again.
    second = await service.ensure_period_grant(USER_ID)
    assert second["granted"] is False
    assert second["reason"] == "already_granted"
    assert wallet.balance == credits_to_units(50)

    # The next calendar month mints exactly one more allowance.
    monkeypatch.setattr(
        "platform_api.services.v3.period_grant_service.billing_month_start",
        lambda *args, **kwargs: nov_start,
    )
    third = await service.ensure_period_grant(USER_ID)
    assert third["granted"] is True
    assert wallet.balance == credits_to_units(100)
    assert len(store.lots) == 2


@pytest.mark.asyncio
async def test_period_grant_uses_license_cycle_when_subscribed() -> None:
    """Licensed accounts keep the activation-anchored period (not the month)."""

    class CtxPlan:
        billing_cycle_days = 30

    class Ctx:
        plan = CtxPlan()
        activated_at = datetime(2026, 9, 15, tzinfo=timezone.utc)

    wallet = FakeWallet()
    store = FakeStore(_paid_plan())
    store.license_plan = _paid_plan()
    service = PeriodGrantService(
        store=store, credit_repo=wallet, plan_repo=FakePlanRepo(ctx=Ctx())
    )

    result = await service.ensure_period_grant(USER_ID)
    assert result["granted"] is True
    # 30-day cycle activated 2026-09-15 -> current period starts 2026-09-15,
    # not the calendar-month fallback used for license-less accounts.
    assert result["period_start"] == "2026-09-15"
    # The lot expires at the period boundary (2026-10-15 00:00 +07), so it cannot
    # overlap the following period's grant.
    expected_expiry = next_billing_midnight(from_date=date(2026, 10, 14)).isoformat()
    assert result["expires_at"] == expected_expiry
