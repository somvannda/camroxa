"""The monthly Free grant must leave the ledger equal to the wallet.

It used to move `credit_wallets.balance` for both the reset and the new grant
without writing `credit_transactions`, so every cycle added wallet/ledger drift
that reconciliation could not explain.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from platform_api.services.free_monthly_grant import ensure_free_monthly_grant


class _Tx:
    async def __aenter__(self) -> "_Tx":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Conn:
    def __init__(self, balance: int, free_remaining: int) -> None:
        self.balance = balance
        self.free_remaining = free_remaining
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> _Tx:
        return _Tx()

    async def fetchval(self, sql: str, *args: Any) -> Any:
        text = " ".join(sql.split()).lower()
        if "from credit_wallet_lots" in text and "tag = 'pack'" in text:
            return False  # not a pack user
        if "from credit_wallet_lots" in text:
            return None  # this period not granted yet
        if "from credit_wallets" in text:
            return self.balance
        return None

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        if self.free_remaining:
            return [{"id": uuid4(), "remaining_units": self.free_remaining}]
        return []

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((" ".join(sql.split()), args))
        return "OK"


class _Acquire:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _Conn:
        return self._conn

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


@pytest.mark.asyncio
async def test_reset_and_grant_both_write_a_ledger_row() -> None:
    conn = _Conn(balance=300_000, free_remaining=300_000)  # 30 credits left

    result = await ensure_free_monthly_grant(_Pool(conn), uuid4())

    assert result["granted"] is True

    ledger = [
        (sql, a)
        for sql, a in conn.executed
        if "insert into credit_transactions" in sql.lower()
    ]
    assert len(ledger) == 2, conn.executed

    text = " ".join(sql.lower() for sql, _ in ledger)
    assert "'debit', 'v3_grant_expire'" in text
    assert "'credit', 'free_monthly_grant'" in text

    # The reset row must mirror exactly what was taken off the wallet.
    reset_args = next(a for sql, a in ledger if "v3_grant_expire" in sql)
    assert int(reset_args[2]) == 300_000


@pytest.mark.asyncio
async def test_above_cap_grant_writes_no_ledger_row() -> None:
    conn = _Conn(balance=2_000_000, free_remaining=0)  # 200 credits already

    result = await ensure_free_monthly_grant(_Pool(conn), uuid4())

    assert result["granted"] is False
    assert not [
        sql for sql, _ in conn.executed if "insert into credit_transactions" in sql.lower()
    ]
