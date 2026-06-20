"""Unit tests for CreditRepository.

Tests atomic deduction, credit addition, refunds, balance queries,
and paginated transaction history using an in-memory fake asyncpg pool.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import InsufficientCreditsError, ValidationError
from platform_api.repositories.credit_repo import (
    CreditRepository,
    DEFAULT_PAGE_SIZE,
    MAX_WALLET_BALANCE,
)


# ---------------------------------------------------------------------------
# Fake asyncpg primitives
# ---------------------------------------------------------------------------


class FakeRecord(dict):
    """Simulates an asyncpg Record that supports both dict-style and attr access."""

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class FakeConnection:
    """Simulates an asyncpg connection with transaction support."""

    def __init__(self, pool: "FakeAsyncPGPool") -> None:
        self._pool = pool

    async def fetchrow(self, query: str, *args: Any) -> FakeRecord | None:
        return await self._pool._handle_query(query, args, mode="fetchrow")

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._pool._handle_query(query, args, mode="fetchval")

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        return await self._pool._handle_query(query, args, mode="fetch")

    async def execute(self, query: str, *args: Any) -> str:
        return await self._pool._handle_query(query, args, mode="execute")

    def transaction(self) -> "FakeTransaction":
        return FakeTransaction()

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeTransaction:
    """No-op transaction context manager."""

    async def __aenter__(self) -> "FakeTransaction":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeAsyncPGPool:
    """In-memory asyncpg pool that simulates credit_wallets and credit_transactions.

    Stores wallets as {user_id: balance} and transactions as a list of dicts.
    Implements the query routing needed for CreditRepository's SQL patterns.
    """

    def __init__(self) -> None:
        self._wallets: dict[UUID, int] = {}
        self._transactions: list[dict[str, Any]] = []

    def seed_wallet(self, user_id: UUID, balance: int) -> None:
        """Seed a wallet for testing."""
        self._wallets[user_id] = balance

    def acquire(self) -> FakeConnection:
        return FakeConnection(self)

    async def fetchrow(self, query: str, *args: Any) -> FakeRecord | None:
        return await self._handle_query(query, args, mode="fetchrow")

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._handle_query(query, args, mode="fetchval")

    async def fetch(self, query: str, *args: Any) -> list[FakeRecord]:
        return await self._handle_query(query, args, mode="fetch")

    async def execute(self, query: str, *args: Any) -> str:
        return await self._handle_query(query, args, mode="execute")

    async def _handle_query(
        self, query: str, args: tuple, mode: str
    ) -> Any:
        q = query.strip().lower()

        # UPDATE credit_wallets SET balance = balance - $2 ... WHERE ... AND balance >= $2
        if "update credit_wallets" in q and "balance - $2" in q and "balance >= $2" in q:
            user_id = args[0]
            amount = args[1]
            current = self._wallets.get(user_id)
            if current is None or current < amount:
                return None if mode == "fetchrow" else "UPDATE 0"
            self._wallets[user_id] = current - amount
            if mode == "fetchrow":
                return FakeRecord({"balance": self._wallets[user_id]})
            return "UPDATE 1"

        # SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE
        if "select balance from credit_wallets" in q and "for update" in q:
            user_id = args[0]
            balance = self._wallets.get(user_id)
            if mode == "fetchval":
                return balance
            if balance is not None:
                return FakeRecord({"balance": balance})
            return None

        # SELECT balance FROM credit_wallets WHERE user_id = $1 (no FOR UPDATE)
        if "select balance from credit_wallets" in q:
            user_id = args[0]
            balance = self._wallets.get(user_id)
            if mode == "fetchval":
                return balance
            if balance is not None:
                return FakeRecord({"balance": balance})
            return None

        # INSERT INTO credit_wallets
        if "insert into credit_wallets" in q:
            user_id = args[0]
            self._wallets[user_id] = 0
            return "INSERT 0 1"

        # UPDATE credit_wallets SET balance = $2
        if "update credit_wallets" in q and "balance = $2" in q:
            user_id = args[0]
            new_balance = args[1]
            self._wallets[user_id] = new_balance
            return "UPDATE 1"

        # INSERT INTO credit_transactions
        if "insert into credit_transactions" in q:
            txn = {
                "id": args[0],
                "user_id": args[1],
                "amount": args[2],
                "direction": args[3] if len(args) > 3 and isinstance(args[3], str) and args[3] in ("credit", "debit", "refund") else "debit",
                "reason": args[3] if len(args) <= 7 else args[4],
                "ref_id": args[4] if len(args) <= 7 else args[5],
                "pack_id": args[5] if len(args) > 7 else None,
                "payment_ref": args[6] if len(args) > 7 else None,
                "created_at": datetime.now(timezone.utc),
            }
            # Parse direction from query if it's hardcoded
            if "'debit'" in q:
                txn["direction"] = "debit"
            elif "'credit'" in q:
                txn["direction"] = "credit"
            elif "'refund'" in q:
                txn["direction"] = "refund"
            elif len(args) > 3 and isinstance(args[3], str) and args[3] in ("credit", "debit", "refund"):
                txn["direction"] = args[3]
                txn["reason"] = args[4] if len(args) > 4 else ""
                txn["ref_id"] = args[5] if len(args) > 5 else None
                txn["pack_id"] = args[6] if len(args) > 6 else None
                txn["payment_ref"] = args[7] if len(args) > 7 else None

            self._transactions.append(txn)
            return "INSERT 0 1"

        # SELECT COUNT(*) FROM credit_transactions
        if "select count" in q and "credit_transactions" in q:
            user_id = args[0]
            count = sum(
                1 for t in self._transactions if t["user_id"] == user_id
            )
            if mode == "fetchval":
                return count
            return FakeRecord({"count": count})

        # SELECT ... FROM credit_transactions ... ORDER BY ... LIMIT ... OFFSET
        if "from credit_transactions" in q and "order by" in q:
            user_id = args[0]
            page_size = args[1]
            offset = args[2]
            user_txns = sorted(
                [t for t in self._transactions if t["user_id"] == user_id],
                key=lambda t: t["created_at"],
                reverse=True,
            )
            page = user_txns[offset : offset + page_size]
            return [FakeRecord(t) for t in page]

        # Default fallback
        if mode == "fetchrow":
            return None
        if mode == "fetchval":
            return None
        if mode == "fetch":
            return []
        return "UPDATE 0"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pool() -> FakeAsyncPGPool:
    return FakeAsyncPGPool()


@pytest.fixture
def repo(pool: FakeAsyncPGPool) -> CreditRepository:
    return CreditRepository(pool)


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Tests: get_balance
# ---------------------------------------------------------------------------


class TestGetBalance:
    """Tests for CreditRepository.get_balance."""

    async def test_returns_zero_for_nonexistent_wallet(
        self, repo: CreditRepository, user_id: UUID
    ) -> None:
        balance = await repo.get_balance(user_id)
        assert balance == 0

    async def test_returns_balance_for_existing_wallet(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 5000)
        balance = await repo.get_balance(user_id)
        assert balance == 5000

    async def test_accepts_string_user_id(
        self, repo: CreditRepository, pool: FakeAsyncPGPool
    ) -> None:
        uid = uuid4()
        pool.seed_wallet(uid, 100)
        balance = await repo.get_balance(str(uid))
        assert balance == 100


# ---------------------------------------------------------------------------
# Tests: atomic_deduct
# ---------------------------------------------------------------------------


class TestAtomicDeduct:
    """Tests for CreditRepository.atomic_deduct."""

    async def test_successful_deduction(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 1000)
        result = await repo.atomic_deduct(user_id, 300, "generation")
        assert result is True
        assert pool._wallets[user_id] == 700

    async def test_insufficient_balance_returns_false(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100)
        result = await repo.atomic_deduct(user_id, 200, "generation")
        assert result is False
        assert pool._wallets[user_id] == 100  # unchanged

    async def test_exact_balance_deduction(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 500)
        result = await repo.atomic_deduct(user_id, 500, "generation")
        assert result is True
        assert pool._wallets[user_id] == 0

    async def test_records_debit_transaction(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 1000)
        await repo.atomic_deduct(user_id, 50, "suno_generation", ref_id="batch_123")
        assert len(pool._transactions) == 1
        txn = pool._transactions[0]
        assert txn["user_id"] == user_id
        assert txn["amount"] == 50
        assert txn["direction"] == "debit"

    async def test_zero_amount_raises_validation_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 1000)
        with pytest.raises(ValidationError):
            await repo.atomic_deduct(user_id, 0, "generation")

    async def test_negative_amount_raises_validation_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 1000)
        with pytest.raises(ValidationError):
            await repo.atomic_deduct(user_id, -5, "generation")

    async def test_nonexistent_wallet_returns_false(
        self, repo: CreditRepository, user_id: UUID
    ) -> None:
        result = await repo.atomic_deduct(user_id, 10, "generation")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: add_credits
# ---------------------------------------------------------------------------


class TestAddCredits:
    """Tests for CreditRepository.add_credits."""

    async def test_adds_credits_to_existing_wallet(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 500)
        new_balance = await repo.add_credits(user_id, 200, "pack_purchase")
        assert new_balance == 700
        assert pool._wallets[user_id] == 700

    async def test_creates_wallet_if_not_exists(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        new_balance = await repo.add_credits(user_id, 100, "bonus")
        assert new_balance == 100
        assert pool._wallets[user_id] == 100

    async def test_exceeding_max_balance_raises_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, MAX_WALLET_BALANCE - 10)
        with pytest.raises(InsufficientCreditsError):
            await repo.add_credits(user_id, 11, "pack_purchase")

    async def test_exactly_at_max_balance_succeeds(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, MAX_WALLET_BALANCE - 100)
        new_balance = await repo.add_credits(user_id, 100, "pack_purchase")
        assert new_balance == MAX_WALLET_BALANCE

    async def test_records_credit_transaction(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 0)
        await repo.add_credits(user_id, 500, "pack_purchase", pack_id=uuid4())
        assert len(pool._transactions) == 1
        txn = pool._transactions[0]
        assert txn["direction"] == "credit"

    async def test_zero_amount_raises_validation_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100)
        with pytest.raises(ValidationError):
            await repo.add_credits(user_id, 0, "bonus")

    async def test_negative_amount_raises_validation_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100)
        with pytest.raises(ValidationError):
            await repo.add_credits(user_id, -50, "bonus")


# ---------------------------------------------------------------------------
# Tests: refund
# ---------------------------------------------------------------------------


class TestRefund:
    """Tests for CreditRepository.refund."""

    async def test_refund_adds_credits_back(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 200)
        new_balance = await repo.refund(user_id, 50, "failed_task", ref_id="task_abc")
        assert new_balance == 250
        assert pool._wallets[user_id] == 250

    async def test_refund_records_refund_transaction(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100)
        await repo.refund(user_id, 25, "timeout")
        assert len(pool._transactions) == 1
        txn = pool._transactions[0]
        assert txn["direction"] == "refund"

    async def test_refund_exceeding_max_raises_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, MAX_WALLET_BALANCE)
        with pytest.raises(InsufficientCreditsError):
            await repo.refund(user_id, 1, "refund_test")

    async def test_refund_zero_raises_validation_error(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100)
        with pytest.raises(ValidationError):
            await repo.refund(user_id, 0, "invalid")

    async def test_refund_creates_wallet_if_missing(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        new_balance = await repo.refund(user_id, 50, "retroactive_refund")
        assert new_balance == 50


# ---------------------------------------------------------------------------
# Tests: get_transactions
# ---------------------------------------------------------------------------


class TestGetTransactions:
    """Tests for CreditRepository.get_transactions."""

    async def test_empty_history(
        self, repo: CreditRepository, user_id: UUID
    ) -> None:
        txns, total = await repo.get_transactions(user_id)
        assert txns == []
        assert total == 0

    async def test_pagination_default_page_size(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100_000)
        # Create 60 transactions
        for i in range(60):
            await repo.atomic_deduct(user_id, 1, f"txn_{i}")

        txns, total = await repo.get_transactions(user_id)
        assert total == 60
        assert len(txns) == DEFAULT_PAGE_SIZE  # 50

    async def test_pagination_page_2(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 100_000)
        for i in range(60):
            await repo.atomic_deduct(user_id, 1, f"txn_{i}")

        txns, total = await repo.get_transactions(user_id, page=2)
        assert total == 60
        assert len(txns) == 10  # remaining 10

    async def test_custom_page_size(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 1000)
        for i in range(10):
            await repo.atomic_deduct(user_id, 1, f"txn_{i}")

        txns, total = await repo.get_transactions(user_id, page=1, page_size=5)
        assert total == 10
        assert len(txns) == 5


# ---------------------------------------------------------------------------
# Tests: record_transaction
# ---------------------------------------------------------------------------


class TestRecordTransaction:
    """Tests for CreditRepository.record_transaction."""

    async def test_records_transaction_without_modifying_balance(
        self, repo: CreditRepository, pool: FakeAsyncPGPool, user_id: UUID
    ) -> None:
        pool.seed_wallet(user_id, 500)
        txn_id = await repo.record_transaction(
            user_id, 100, "credit", "admin_bonus"
        )
        assert isinstance(txn_id, UUID)
        # Balance should NOT change — record_transaction only writes the txn row
        assert pool._wallets[user_id] == 500

    async def test_invalid_direction_raises_validation_error(
        self, repo: CreditRepository, user_id: UUID
    ) -> None:
        with pytest.raises(ValidationError, match="Invalid transaction direction"):
            await repo.record_transaction(user_id, 100, "invalid", "test")

    async def test_zero_amount_raises_validation_error(
        self, repo: CreditRepository, user_id: UUID
    ) -> None:
        with pytest.raises(ValidationError):
            await repo.record_transaction(user_id, 0, "credit", "test")

    async def test_negative_amount_raises_validation_error(
        self, repo: CreditRepository, user_id: UUID
    ) -> None:
        with pytest.raises(ValidationError):
            await repo.record_transaction(user_id, -10, "debit", "test")
