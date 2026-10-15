"""Packs-only billing: pack credits expire 30 days from purchase.

Covers the two halves of the rule:

* a pack purchase stamps its own lot and re-stamps every other live lot to one
  shared expiry date (``now + 30 days``), while Free daily credits keep their own
  midnight reset; and
* a lapsed pack lot is clawed back from the wallet like a grant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from platform_api.services.credit_units import credits_to_units
from platform_api.services.v3.period_grant_service import PeriodGrantService
from platform_api.services.v3.store import V3BillingStore
from platform_api.services.v3.wallet_sync import PACK_CREDIT_VALIDITY, WalletSyncService

USER_ID = uuid4()


class FakeCreditRepo:
    def __init__(self, balance_units: int = 0) -> None:
        self.balance_units = balance_units
        self.grants: list[dict] = []
        self.deducts: list[dict] = []

    async def get_balance(self, user_id) -> int:
        return self.balance_units

    async def add_credits(self, user_id, amount, reason, ref_id=None, **kwargs) -> int:
        self.balance_units += amount
        self.grants.append({"reason": reason, "amount": amount, "ref_id": ref_id})
        return self.balance_units

    async def atomic_deduct(self, user_id, amount, reason, ref_id=None, metadata=None) -> bool:
        if self.balance_units < amount:
            return False
        self.balance_units -= amount
        self.deducts.append({"reason": reason, "amount": amount, "ref_id": ref_id})
        return True


class FakeStore:
    """Mirrors the tag/guard behaviour of the real SQL in ``V3BillingStore``."""

    def __init__(self) -> None:
        self.lots: list[dict] = []
        self.restamped: list[tuple[UUID, datetime]] = []
        self.zeroed: list[UUID] = []
        self.expired: list[dict] = []
        self.minted_refs: set[str] = set()

    async def has_transaction_ref(self, ref_id: str) -> bool:
        return ref_id in self.minted_refs

    async def insert_lot(self, **kwargs) -> dict:
        lot = {"id": uuid4(), **kwargs}
        self.lots.append(lot)
        return lot

    async def restamp_live_lots(self, user_id: UUID, expires_at: datetime) -> int:
        self.restamped.append((user_id, expires_at))
        moved = 0
        for lot in self.lots:
            if lot["tag"] not in ("grant", "pack", "admin", "quota_conversion"):
                continue
            current = lot.get("expires_at")
            if current is None or current < expires_at:
                lot["expires_at"] = expires_at
                moved += 1
        return moved

    async def subtract_web_topup(self, user_id, credits: int) -> None:
        return None

    async def expired_lots(self, user_id: UUID | None = None) -> list[dict]:
        return list(self.expired)

    async def zero_lot_remaining(self, lot_id: UUID) -> None:
        self.zeroed.append(lot_id)


def _wallet_sync(store: FakeStore, repo: FakeCreditRepo) -> WalletSyncService:
    # `grant` is unused by after_topup_fulfill.
    return WalletSyncService(grant=None, store=store, credit_repo=repo)


@pytest.mark.asyncio
async def test_topup_stamps_pack_lot_30_days() -> None:
    store = FakeStore()
    repo = FakeCreditRepo()
    sync = _wallet_sync(store, repo)

    before = datetime.now(timezone.utc)
    result = await sync.after_topup_fulfill(USER_ID, 1000, topup_id="tp1")

    assert result["minted"] is True
    pack_lot = store.lots[0]
    assert pack_lot["tag"] == "pack"
    assert pack_lot["amount_units"] == credits_to_units(1000)

    expiry = pack_lot["expires_at"]
    assert expiry is not None
    assert before + PACK_CREDIT_VALIDITY <= expiry
    assert expiry <= datetime.now(timezone.utc) + PACK_CREDIT_VALIDITY + timedelta(seconds=5)
    assert result["expires_at"] == expiry.isoformat()
    # The purchase also sets the wallet's one shared expiry date.
    assert store.restamped == [(USER_ID, expiry)]


@pytest.mark.asyncio
async def test_topup_restamps_older_packs_and_grants_but_not_daily() -> None:
    store = FakeStore()
    repo = FakeCreditRepo()
    older = datetime.now(timezone.utc) + timedelta(days=3)
    store.lots.append({"id": uuid4(), "tag": "pack", "expires_at": older})
    store.lots.append({"id": uuid4(), "tag": "grant", "expires_at": older})
    daily = {"id": uuid4(), "tag": "daily_grant", "expires_at": older}
    store.lots.append(daily)

    await _wallet_sync(store, repo).after_topup_fulfill(USER_ID, 500, topup_id="tp2")

    new_expiry = store.lots[-1]["expires_at"]  # the lot just minted
    assert store.lots[0]["expires_at"] == new_expiry  # older pack moves forward
    assert store.lots[1]["expires_at"] == new_expiry  # leftover grant does too
    assert daily["expires_at"] == older  # Free daily keeps its own midnight reset


@pytest.mark.asyncio
async def test_topup_does_not_shorten_a_later_expiry() -> None:
    store = FakeStore()
    repo = FakeCreditRepo()
    prepaid = datetime.now(timezone.utc) + timedelta(days=200)
    store.lots.append({"id": uuid4(), "tag": "grant", "expires_at": prepaid})

    await _wallet_sync(store, repo).after_topup_fulfill(USER_ID, 500, topup_id="tp5")

    # A prepaid yearly term is never shortened by buying a pack.
    assert store.lots[0]["expires_at"] == prepaid


@pytest.mark.asyncio
async def test_topup_fulfill_is_idempotent() -> None:
    store = FakeStore()
    repo = FakeCreditRepo()
    sync = _wallet_sync(store, repo)

    await sync.after_topup_fulfill(USER_ID, 1000, topup_id="tp3")
    balance_after_first = repo.balance_units
    store.minted_refs.add("v3_pack:tp3")

    second = await sync.after_topup_fulfill(USER_ID, 1000, topup_id="tp3")

    assert second["minted"] is False
    assert second["reason"] == "already_minted"
    assert repo.balance_units == balance_after_first
    assert len(store.lots) == 1


@pytest.mark.asyncio
async def test_expire_claws_back_a_lapsed_pack_lot() -> None:
    store = FakeStore()
    repo = FakeCreditRepo(balance_units=credits_to_units(300))
    lapsed_id = uuid4()
    store.expired = [
        {"id": lapsed_id, "user_id": USER_ID, "remaining_units": credits_to_units(300)}
    ]

    service = PeriodGrantService(store=store, credit_repo=repo, plan_repo=None)
    touched = await service.expire_lapsed_lots(USER_ID)

    assert touched == 1
    assert repo.balance_units == 0
    assert repo.deducts and repo.deducts[0]["reason"] == "v3_grant_expire"
    assert store.zeroed == [lapsed_id]


@pytest.mark.asyncio
async def test_expire_never_overdraws_a_spent_wallet() -> None:
    store = FakeStore()
    repo = FakeCreditRepo(balance_units=credits_to_units(100))
    store.expired = [{"id": uuid4(), "user_id": USER_ID, "remaining_units": credits_to_units(300)}]

    service = PeriodGrantService(store=store, credit_repo=repo, plan_repo=None)
    await service.expire_lapsed_lots(USER_ID)

    # Claw back only what is really there; the balance never goes negative.
    assert repo.balance_units == 0


class RecordingPool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    async def fetch(self, sql: str, *args):
        self.calls.append((sql, args))
        return []


@pytest.mark.asyncio
async def test_restamp_sql_guards_are_intact() -> None:
    """The shared-date contract lives in SQL, so pin the two guards."""
    pool = RecordingPool()
    store = V3BillingStore(pool)

    await store.restamp_live_lots(USER_ID, datetime.now(timezone.utc))

    sql, _args = pool.calls[0]
    # Free daily credits are excluded, so their midnight reset still works.
    assert "tag IN ('grant', 'pack', 'admin', 'quota_conversion')" in sql
    assert "daily_grant" not in sql
    # The update only ever extends an existing expiry.
    assert "expires_at IS NULL OR expires_at < $2" in sql


@pytest.mark.asyncio
async def test_expired_lots_sql_includes_packs() -> None:
    pool = RecordingPool()
    store = V3BillingStore(pool)

    await store.expired_lots(USER_ID)

    sql, _args = pool.calls[0]
    assert "'pack'" in sql
