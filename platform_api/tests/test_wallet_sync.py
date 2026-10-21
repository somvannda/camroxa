"""CutLuy fulfill writes period grants and pack lots on the shared wallet."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.wallet_sync import WalletSyncService, pack_ref_id


USER_ID = uuid4()
TOPUP_ID = str(uuid4())


class FakeWallet:
    def __init__(self) -> None:
        self.balance = 0
        self.txs: list[dict] = []

    async def get_balance(self, user_id: UUID | str) -> int:
        return self.balance

    async def add_credits(self, user_id, amount: int, reason: str, ref_id=None, **kwargs) -> int:
        self.balance += amount
        self.txs.append({"reason": reason, "amount": amount, "ref_id": ref_id})
        return self.balance


class FakeGrant:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls = 0

    async def ensure_period_grant(self, user_id: UUID) -> dict:
        self.calls += 1
        return self.result


class FakeStore:
    def __init__(self) -> None:
        self.refs: set[str] = set()
        self.lots: list[dict] = []
        self.zeroed: list[UUID] = []
        self.topup_subtracted: list[tuple[UUID, int]] = []
        self.restamped: list[tuple[UUID, object]] = []

    async def has_transaction_ref(self, ref_id: str) -> bool:
        return ref_id in self.refs

    async def insert_lot(self, **kwargs) -> dict:
        lot = {"id": uuid4(), **kwargs}
        self.lots.append(lot)
        return lot

    async def restamp_live_lots(self, user_id: UUID, expires_at: object) -> int:
        self.restamped.append((user_id, expires_at))
        return 0

    async def zero_web_monthly_remaining(self, user_id: UUID) -> None:
        self.zeroed.append(user_id)

    async def subtract_web_topup(self, user_id: UUID, credits: int) -> None:
        self.topup_subtracted.append((user_id, credits))


@pytest.mark.asyncio
async def test_subscribe_grant_zeros_v2_monthly() -> None:
    store = FakeStore()
    grant = FakeGrant({"granted": True, "reason": None})
    sync = WalletSyncService(grant=grant, store=store, credit_repo=FakeWallet())
    result = await sync.after_subscription_fulfill(USER_ID)
    assert result["granted"] is True
    assert store.zeroed == [USER_ID]


@pytest.mark.asyncio
async def test_subscribe_does_not_zero_when_no_plan() -> None:
    store = FakeStore()
    grant = FakeGrant({"granted": False, "reason": "no_active_plan"})
    sync = WalletSyncService(grant=grant, store=store, credit_repo=FakeWallet())
    await sync.after_subscription_fulfill(USER_ID)
    assert store.zeroed == []


@pytest.mark.asyncio
async def test_topup_mints_pack_once() -> None:
    store = FakeStore()
    wallet = FakeWallet()
    sync = WalletSyncService(grant=FakeGrant({}), store=store, credit_repo=wallet)
    first = await sync.after_topup_fulfill(USER_ID, 200, topup_id=TOPUP_ID)
    assert first["minted"] is True
    assert first["credits"] == 200
    assert wallet.balance == credits_to_units(200)
    assert store.lots[0]["tag"] == "pack"
    assert store.topup_subtracted == [(USER_ID, 200)]
    # A pack is no longer immortal: it is stamped 30 days out, and the purchase
    # sets the wallet's one shared expiry date to the same moment.
    assert store.lots[0]["expires_at"] is not None
    assert store.restamped == [(USER_ID, store.lots[0]["expires_at"])]
    store.refs.add(pack_ref_id(TOPUP_ID))

    second = await sync.after_topup_fulfill(USER_ID, 200, topup_id=TOPUP_ID)
    assert second["minted"] is False
    assert second["reason"] == "already_minted"
    assert wallet.balance == credits_to_units(200)
    assert len(store.lots) == 1
