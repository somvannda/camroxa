"""Refunds must never push a wallet lot above what it was granted.

Production hit ``credit_wallet_lots_remaining_check`` because the refund path
added straight onto ``remaining_units``: a full pack lot went to
``remaining_units > amount_units``. The split below caps the refill and sends
the overflow to a fresh lot.

The overflow lot also used to be minted with ``expires_at = NULL``, so refunds
created credits that could never expire (102 in production, 60 on one account).
It now gets the normal 30-day life, and the refund walks every lot with room
instead of only the newest one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from platform_api.repositories.credit_repo import CreditRepository

CASES = [
    # (amount, remaining, capacity, into_lot, overflow)
    (100, 1_000, 1_000, 0, 100),      # lot already full -> all overflow
    (100, 950, 1_000, 50, 50),        # partial room
    (100, 900, 1_000, 100, 0),        # fits exactly
    (100, 0, 1_000, 100, 0),          # empty lot
    (100, 0, 0, 0, 100),              # zero-capacity lot
    (100, 1_200, 1_000, 0, 100),      # corrupt lot (over capacity) stays safe
]


@pytest.mark.parametrize(("amount", "remaining", "capacity", "into_lot", "overflow"), CASES)
def test_restore_split_never_exceeds_capacity(
    amount: int, remaining: int, capacity: int, into_lot: int, overflow: int
) -> None:
    got_into, got_overflow = CreditRepository._restore_split(amount, remaining, capacity)

    assert (got_into, got_overflow) == (into_lot, overflow)
    # A lot already above capacity (corrupt data) must not grow further.
    assert remaining + got_into <= max(remaining, capacity)
    assert got_into + got_overflow == amount


class FakeConn:
    """Records the writes ``_restore_lots`` makes inside a transaction."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.fetched_sql = ""
        self.updates: list[tuple] = []
        self.inserts: list[tuple] = []

    async def fetch(self, sql: str, *args):
        self.fetched_sql = sql
        return self.rows

    async def execute(self, sql: str, *args):
        if "INSERT INTO credit_wallet_lots" in sql:
            self.inserts.append(args)
        else:
            self.updates.append(args)
        return "OK"


@pytest.mark.asyncio
async def test_restore_fills_every_lot_with_room_before_minting() -> None:
    conn = FakeConn(
        [
            {"id": uuid4(), "amount_units": 1_000, "remaining_units": 950},
            {"id": uuid4(), "amount_units": 1_000, "remaining_units": 0},
        ]
    )
    repo = CreditRepository(pool=None)

    await repo._restore_lots(conn, uuid4(), 100)

    assert [args[1] for args in conn.updates] == [50, 50]
    assert conn.inserts == []


@pytest.mark.asyncio
async def test_restore_overflow_gets_a_30_day_expiry() -> None:
    conn = FakeConn([])  # every lot is full
    repo = CreditRepository(pool=None)

    await repo._restore_lots(conn, uuid4(), 100)

    assert conn.updates == []
    (args,) = conn.inserts
    expires_at = args[3]
    assert expires_at is not None
    remaining = expires_at - datetime.now(timezone.utc)
    assert timedelta(days=29) < remaining <= timedelta(days=31)


@pytest.mark.asyncio
async def test_restore_query_skips_full_and_expired_lots() -> None:
    conn = FakeConn([])
    repo = CreditRepository(pool=None)

    await repo._restore_lots(conn, uuid4(), 100)

    sql = conn.fetched_sql
    assert "remaining_units < amount_units" in sql
    assert "expires_at IS NULL OR expires_at > NOW()" in sql
    assert "LIMIT 1" not in sql
