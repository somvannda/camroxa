"""One-time CutLuy leftover mint does not collide with desktop leftover."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.web_ledger_conversion import (
    WebLedgerConversionService,
    web_remaining_ref_id,
)


USER_ID = uuid4()
OTHER_ID = uuid4()
PLAN_ID = uuid4()


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


class FakeStore:
    def __init__(self, rows: list[dict], refs: set[str] | None = None) -> None:
        self.rows = rows
        self.refs = set(refs or [])
        self.lots: list[dict] = []
        self.zeroed: list[UUID] = []
        self.desktop_applied = {str(USER_ID)}

    async def has_transaction_ref(self, ref_id: str) -> bool:
        return ref_id in self.refs

    async def list_active_web_subscribers(self, user_ids=None) -> list[dict]:
        if not user_ids:
            return list(self.rows)
        wanted = {str(uid) for uid in user_ids}
        return [row for row in self.rows if str(row["user_id"]) in wanted]

    async def insert_lot(self, **kwargs) -> dict:
        lot = {"id": uuid4(), **kwargs}
        self.lots.append(lot)
        return lot

    async def zero_web_subscription_remaining(self, user_id: UUID) -> None:
        self.zeroed.append(user_id)

    async def get_applied_conversion(self, user_id: UUID) -> dict | None:
        if str(user_id) in self.desktop_applied:
            return {"user_id": str(user_id), "status": "applied"}
        return None


def _row(*, user_id=USER_ID, granted=1000, used=200, topup=50) -> dict:
    return {
        "user_id": user_id,
        "subscription_id": uuid4(),
        "plan_id": PLAN_ID,
        "plan_name": "Starter",
        "price_cents": 1000,
        "monthly_credits_granted": granted,
        "monthly_credits_used": used,
        "topup_credits_balance": topup,
    }


@pytest.mark.asyncio
async def test_apply_mints_remaining_and_zeros_v2() -> None:
    store = FakeStore([_row()])
    wallet = FakeWallet()
    service = WebLedgerConversionService(store=store, credit_repo=wallet)
    rows = await service.apply(confirm=True)
    assert rows[0]["status"] == "applied"
    assert rows[0]["credits_to_mint"] == 850
    assert wallet.txs[0]["reason"] == "v3_web_remaining"
    assert wallet.balance == credits_to_units(850)
    assert store.lots[0]["tag"] == "quota_conversion"
    assert store.zeroed == [USER_ID]


@pytest.mark.asyncio
async def test_apply_is_idempotent_and_ignores_desktop_conversion() -> None:
    store = FakeStore([_row()], refs={web_remaining_ref_id(USER_ID)})
    wallet = FakeWallet(credits_to_units(850))
    service = WebLedgerConversionService(store=store, credit_repo=wallet)
    assert await store.get_applied_conversion(USER_ID) is not None
    rows = await service.apply(confirm=True)
    assert rows[0]["status"] == "already_applied"
    assert rows[0]["credits_to_mint"] == 0
    assert wallet.txs == []
    assert store.lots == []


@pytest.mark.asyncio
async def test_skip_zero_and_require_confirm() -> None:
    store = FakeStore([_row(granted=100, used=100, topup=0), _row(user_id=OTHER_ID, granted=0, used=0, topup=0)])
    service = WebLedgerConversionService(store=store, credit_repo=FakeWallet())
    with pytest.raises(ValidationError):
        await service.apply(confirm=False)
    rows = await service.apply(confirm=True)
    assert all(row["status"] == "skipped" for row in rows)
    assert store.lots == []
