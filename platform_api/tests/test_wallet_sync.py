"""CutLuy fulfill writes period grants and pack lots on the shared wallet.

The settlement path is idempotent end to end: the credit grant dedupes on
``(user, reason, ref)`` (``credit_grant_claims``) and the pack lot dedupes on the
purchase reference (``uq_credit_wallet_lots_pack_ref``). The payment webhook and
the client's status poll race in production, so both layers are exercised here.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.wallet_sync import WalletSyncService, pack_ref_id


USER_ID = uuid4()
TOPUP_ID = str(uuid4())


class FakeWallet:
    """Mirrors ``credit_grant_claims``: one credit per (reason, ref)."""

    def __init__(self) -> None:
        self.balance = 0
        self.txs: list[dict] = []
        self.claims: set[tuple[str, str]] = set()

    async def get_balance(self, user_id: UUID | str) -> int:
        return self.balance

    async def add_credits(self, user_id, amount: int, reason: str, ref_id=None, **kwargs) -> int:
        key = (reason, str(ref_id))
        if ref_id is not None and key in self.claims:
            return self.balance
        self.claims.add(key)
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
    """Mirrors the unique index on (user_id, ref_id) for pack lots."""

    def __init__(self) -> None:
        self.refs: set[str] = set()
        self.lots: list[dict] = []
        self.restamped: list[tuple[UUID, object]] = []

    async def has_transaction_ref(self, ref_id: str) -> bool:
        return ref_id in self.refs

    async def insert_pack_lot_if_absent(
        self, *, user_id: UUID, amount_units: int, expires_at: object, ref_id: str
    ) -> dict:
        for lot in self.lots:
            if lot.get("ref_id") == ref_id:
                return lot
        lot = {
            "id": uuid4(),
            "user_id": user_id,
            "tag": "pack",
            "amount_units": amount_units,
            "remaining_units": amount_units,
            "expires_at": expires_at,
            "period_start": None,
            "ref_id": ref_id,
        }
        self.lots.append(lot)
        return lot

    async def restamp_live_lots(self, user_id: UUID, expires_at: object) -> int:
        self.restamped.append((user_id, expires_at))
        return 0


@pytest.mark.asyncio
async def test_subscribe_grant_returns_the_grant_result() -> None:
    store = FakeStore()
    grant = FakeGrant({"granted": True, "reason": None})
    sync = WalletSyncService(grant=grant, store=store, credit_repo=FakeWallet())

    result = await sync.after_subscription_fulfill(USER_ID)

    assert result["granted"] is True
    assert grant.calls == 1


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


@pytest.mark.asyncio
async def test_concurrent_settlement_mints_one_lot() -> None:
    """Webhook + status poll both enter the mint: one credit, one lot.

    ``has_transaction_ref`` runs outside the grant transaction, so both callers
    pass it before either commits. Production logged three settlements for one
    top-up; before the unique index that meant three pack lots for one purchase.
    """
    store = FakeStore()
    wallet = FakeWallet()
    sync = WalletSyncService(grant=FakeGrant({}), store=store, credit_repo=wallet)

    first = await sync.after_topup_fulfill(USER_ID, 200, topup_id=TOPUP_ID)
    second = await sync.after_topup_fulfill(USER_ID, 200, topup_id=TOPUP_ID)

    assert first["minted"] is True
    assert second["minted"] is True
    assert wallet.balance == credits_to_units(200)
    assert len(store.lots) == 1
    assert first["lot_id"] == second["lot_id"]
