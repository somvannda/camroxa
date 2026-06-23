"""Credit wallet repository with atomic deduction and transaction recording.

Provides atomic balance operations using PostgreSQL's conditional UPDATE pattern,
credit addition with max-balance enforcement, refund processing, balance queries,
and paginated transaction history.

Requirements: 6.3, 6.4, 6.5, 6.7, 6.8, 6.10
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

import asyncpg

from platform_api.exceptions import DuplicateError, InsufficientCreditsError, ValidationError

logger = logging.getLogger(__name__)

MAX_WALLET_BALANCE = 10_000_000
DEFAULT_PAGE_SIZE = 50


class AsyncPGPool(Protocol):
    """Minimal protocol for an asyncpg connection pool."""

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        ...

    async def fetchrow(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single row."""
        ...

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        """Execute a query and return all rows."""
        ...

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        ...

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        ...


class CreditRepository:
    """Repository for credit wallet operations using asyncpg.

    Implements atomic credit deduction, addition, refunds, balance queries,
    and paginated transaction history. All balance-modifying operations run
    within database transactions to ensure consistency.

    The atomic deduction pattern uses a single UPDATE with a WHERE clause
    on the balance to prevent overdrawing under concurrent access.

    Args:
        pool: An asyncpg connection pool instance.
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> bool:
        """Atomically deduct credits from a user's wallet.

        Uses a conditional UPDATE that only succeeds if the current balance
        is sufficient. This prevents overdrawing under concurrent requests
        without requiring explicit row locks.

        Args:
            user_id: The UUID of the user whose wallet to deduct from.
            amount: The number of credits to deduct (must be positive).
            reason: A description of why credits are being deducted.
            ref_id: Optional reference identifier (e.g. batch_id, task_id).

        Returns:
            True if the deduction succeeded, False if the balance was
            insufficient.

        Raises:
            ValidationError: If amount is not a positive integer.
        """
        if amount <= 0:
            raise ValidationError(
                "Deduction amount must be a positive integer.",
                details={"amount": amount},
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    UPDATE credit_wallets
                    SET balance = balance - $2, updated_at = NOW()
                    WHERE user_id = $1 AND balance >= $2
                    RETURNING balance
                    """,
                    user_id,
                    amount,
                )
                if row is None:
                    return False

                # Record the debit transaction
                await conn.execute(
                    """
                    INSERT INTO credit_transactions
                        (id, user_id, amount, direction, reason, ref_id, created_at)
                    VALUES ($1, $2, $3, 'debit', $4, $5, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                )
                logger.info(
                    "Deducted %d credits from user %s (reason=%s, ref=%s). New balance: %d",
                    amount,
                    user_id,
                    reason,
                    ref_id,
                    row["balance"],
                )
                return True

    async def add_credits(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        pack_id: UUID | None = None,
        payment_ref: str | None = None,
    ) -> int:
        """Add credits to a user's wallet, enforcing the maximum balance.

        Args:
            user_id: The UUID of the user whose wallet to credit.
            amount: The number of credits to add (must be positive).
            reason: A description of why credits are being added.
            ref_id: Optional reference identifier.
            pack_id: Optional credit pack UUID if this is a pack purchase.
            payment_ref: Optional payment reference string.

        Returns:
            The new wallet balance after the addition.

        Raises:
            ValidationError: If amount is not a positive integer.
            InsufficientCreditsError: If the addition would exceed the
                maximum wallet balance of 10,000,000.
        """
        if amount <= 0:
            raise ValidationError(
                "Credit amount must be a positive integer.",
                details={"amount": amount},
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Check current balance first
                current_balance = await conn.fetchval(
                    "SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE",
                    user_id,
                )
                if current_balance is None:
                    # Wallet doesn't exist — create one
                    current_balance = 0
                    await conn.execute(
                        """
                        INSERT INTO credit_wallets (user_id, balance, updated_at)
                        VALUES ($1, 0, NOW())
                        """,
                        user_id,
                    )

                new_balance = current_balance + amount
                if new_balance > MAX_WALLET_BALANCE:
                    raise InsufficientCreditsError(
                        f"Adding {amount} credits would exceed the maximum wallet "
                        f"balance of {MAX_WALLET_BALANCE:,}. Current balance: {current_balance:,}.",
                        details={
                            "current_balance": current_balance,
                            "amount": amount,
                            "max_balance": MAX_WALLET_BALANCE,
                        },
                    )

                # Update the wallet balance
                await conn.execute(
                    """
                    UPDATE credit_wallets
                    SET balance = $2, updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                    new_balance,
                )

                # Record the credit transaction
                await conn.execute(
                    """
                    INSERT INTO credit_transactions
                        (id, user_id, amount, direction, reason, ref_id, pack_id,
                         payment_ref, created_at)
                    VALUES ($1, $2, $3, 'credit', $4, $5, $6, $7, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                    pack_id,
                    payment_ref,
                )
                logger.info(
                    "Added %d credits to user %s (reason=%s). New balance: %d",
                    amount,
                    user_id,
                    reason,
                    new_balance,
                )
                return new_balance

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> int:
        """Refund credits back to a user's wallet.

        Similar to add_credits but records the transaction with 'refund'
        direction. Enforces the maximum balance cap.

        Args:
            user_id: The UUID of the user to refund.
            amount: The number of credits to refund (must be positive).
            reason: A description of why the refund is issued.
            ref_id: Optional reference identifier (e.g. failed task_id).

        Returns:
            The new wallet balance after the refund.

        Raises:
            ValidationError: If amount is not a positive integer.
            InsufficientCreditsError: If the refund would exceed the
                maximum wallet balance.
        """
        if amount <= 0:
            raise ValidationError(
                "Refund amount must be a positive integer.",
                details={"amount": amount},
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                current_balance = await conn.fetchval(
                    "SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE",
                    user_id,
                )
                if current_balance is None:
                    current_balance = 0
                    await conn.execute(
                        """
                        INSERT INTO credit_wallets (user_id, balance, updated_at)
                        VALUES ($1, 0, NOW())
                        """,
                        user_id,
                    )

                new_balance = current_balance + amount
                if new_balance > MAX_WALLET_BALANCE:
                    raise InsufficientCreditsError(
                        f"Refunding {amount} credits would exceed the maximum wallet "
                        f"balance of {MAX_WALLET_BALANCE:,}. Current balance: {current_balance:,}.",
                        details={
                            "current_balance": current_balance,
                            "amount": amount,
                            "max_balance": MAX_WALLET_BALANCE,
                        },
                    )

                await conn.execute(
                    """
                    UPDATE credit_wallets
                    SET balance = $2, updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                    new_balance,
                )

                # Record the refund transaction
                await conn.execute(
                    """
                    INSERT INTO credit_transactions
                        (id, user_id, amount, direction, reason, ref_id, created_at)
                    VALUES ($1, $2, $3, 'refund', $4, $5, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                )
                logger.info(
                    "Refunded %d credits to user %s (reason=%s, ref=%s). New balance: %d",
                    amount,
                    user_id,
                    reason,
                    ref_id,
                    new_balance,
                )
                return new_balance

    async def get_balance(self, user_id: UUID | str) -> int:
        """Return the current credit balance for a user.

        Args:
            user_id: The UUID (or string UUID) of the user.

        Returns:
            The current balance as an integer. Returns 0 if the wallet
            does not exist.
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        balance = await self._pool.fetchval(
            "SELECT balance FROM credit_wallets WHERE user_id = $1",
            user_id,
        )
        return balance if balance is not None else 0

    async def get_transactions(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return paginated transaction history for a user.

        Transactions are ordered by created_at descending (most recent first).

        Args:
            user_id: The UUID of the user whose transactions to retrieve.
            page: The 1-based page number (default 1).
            page_size: Number of records per page (default 50).

        Returns:
            A tuple of (list of transaction dicts, total transaction count).
            Each dict contains: id, amount, direction, reason, ref_id,
            pack_id, payment_ref, created_at.
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = DEFAULT_PAGE_SIZE

        # Get total count
        total = await self._pool.fetchval(
            "SELECT COUNT(*) FROM credit_transactions WHERE user_id = $1",
            user_id,
        )

        # Fetch the requested page
        offset = (page - 1) * page_size
        rows = await self._pool.fetch(
            """
            SELECT id, user_id, amount, direction, reason, ref_id,
                   pack_id, payment_ref, created_at
            FROM credit_transactions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            page_size,
            offset,
        )

        transactions = [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "amount": row["amount"],
                "direction": row["direction"],
                "reason": row["reason"],
                "ref_id": row["ref_id"],
                "pack_id": row["pack_id"],
                "payment_ref": row["payment_ref"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

        return transactions, total or 0

    async def record_transaction(
        self,
        user_id: UUID,
        amount: int,
        direction: str,
        reason: str,
        ref_id: str | None = None,
        pack_id: UUID | None = None,
        payment_ref: str | None = None,
    ) -> UUID:
        """Insert a credit transaction record without modifying the wallet balance.

        Use this for recording transactions that are managed externally
        (e.g., admin adjustments that bypass the normal add/deduct flow).

        Args:
            user_id: The UUID of the user this transaction belongs to.
            amount: The credit amount (positive integer).
            direction: One of 'credit', 'debit', or 'refund'.
            reason: A human-readable reason for the transaction.
            ref_id: Optional reference identifier.
            pack_id: Optional credit pack UUID.
            payment_ref: Optional payment reference string.

        Returns:
            The UUID of the newly created transaction record.

        Raises:
            ValidationError: If direction is invalid or amount is not positive.
        """
        valid_directions = {"credit", "debit", "refund"}
        if direction not in valid_directions:
            raise ValidationError(
                f"Invalid transaction direction '{direction}'. "
                f"Must be one of: {', '.join(sorted(valid_directions))}.",
                details={"direction": direction},
            )
        if amount <= 0:
            raise ValidationError(
                "Transaction amount must be a positive integer.",
                details={"amount": amount},
            )

        txn_id = uuid4()
        await self._pool.execute(
            """
            INSERT INTO credit_transactions
                (id, user_id, amount, direction, reason, ref_id, pack_id,
                 payment_ref, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """,
            txn_id,
            user_id,
            amount,
            direction,
            reason,
            ref_id,
            pack_id,
            payment_ref,
        )
        logger.info(
            "Recorded %s transaction of %d credits for user %s (reason=%s)",
            direction,
            amount,
            user_id,
            reason,
        )
        return txn_id

    # -----------------------------------------------------------------------
    # Credit Pricing queries (CreditPricingRepositoryProtocol)
    # -----------------------------------------------------------------------

    async def get_all(self) -> list[dict[str, Any]]:
        """Return all configured pricing entries from credit_pricing table."""
        rows = await self._pool.fetch(
            """
            SELECT id, ai_service, operation_type, credits_per_operation,
                   external_cost_cents, created_at, updated_at
            FROM credit_pricing
            ORDER BY ai_service, operation_type
            """
        )
        return [dict(r) for r in rows]

    async def get_by_service_and_operation(
        self, ai_service: str, operation_type: str
    ) -> dict[str, Any] | None:
        """Return a pricing entry for an ai_service/operation combination."""
        row = await self._pool.fetchrow(
            """
            SELECT id, ai_service, operation_type, credits_per_operation,
                   external_cost_cents, created_at, updated_at
            FROM credit_pricing
            WHERE ai_service = $1 AND operation_type = $2
            """,
            ai_service,
            operation_type,
        )
        return dict(row) if row else None

    async def create(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any]:
        """Create a new pricing entry.

        Raises:
            DuplicateError: If a pricing entry already exists for the
                (ai_service, operation_type) combination.
        """
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO credit_pricing (id, ai_service, operation_type,
                                            credits_per_operation, external_cost_cents,
                                            created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, NOW(), NOW())
                RETURNING id, ai_service, operation_type, credits_per_operation,
                          external_cost_cents, created_at, updated_at
                """,
                ai_service,
                operation_type,
                credits_per_operation,
                external_cost_cents,
            )
        except asyncpg.UniqueViolationError:
            raise DuplicateError(
                f"Pricing already exists for ai_service '{ai_service}' "
                f"operation '{operation_type}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                },
            )
        return dict(row)

    async def update(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any] | None:
        """Update an existing pricing entry. Returns None if not found."""
        row = await self._pool.fetchrow(
            """
            UPDATE credit_pricing
            SET credits_per_operation = $3, external_cost_cents = $4, updated_at = NOW()
            WHERE ai_service = $1 AND operation_type = $2
            RETURNING id, ai_service, operation_type, credits_per_operation,
                      external_cost_cents, created_at, updated_at
            """,
            ai_service,
            operation_type,
            credits_per_operation,
            external_cost_cents,
        )
        return dict(row) if row else None

    async def delete(
        self, ai_service: str, operation_type: str
    ) -> bool:
        """Delete a pricing entry. Returns True if deleted."""
        result = await self._pool.execute(
            """
            DELETE FROM credit_pricing
            WHERE ai_service = $1 AND operation_type = $2
            """,
            ai_service,
            operation_type,
        )
        return "DELETE 1" in result

    # -----------------------------------------------------------------------
    # Credit Packs queries
    # -----------------------------------------------------------------------

    async def get_active_packs(self) -> list[dict[str, Any]]:
        """Return all active credit packs."""
        rows = await self._pool.fetch(
            """
            SELECT id, name, price_cents, song_credits, request_count,
                   is_active, created_at, updated_at
            FROM credit_packs
            WHERE is_active = true
            ORDER BY price_cents
            """
        )
        return [dict(r) for r in rows]

    async def get_by_id(self, pack_id: UUID) -> dict[str, Any] | None:
        """Return a credit pack by ID."""
        row = await self._pool.fetchrow(
            """
            SELECT id, name, price_cents, song_credits, request_count,
                   is_active, created_at, updated_at
            FROM credit_packs
            WHERE id = $1
            """,
            pack_id,
        )
        return dict(row) if row else None
