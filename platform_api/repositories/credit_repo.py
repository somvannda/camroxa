"""Credit wallet repository with atomic deduction and transaction recording.

Provides atomic balance operations using PostgreSQL's conditional UPDATE pattern,
credit addition with max-balance enforcement, refund processing, balance queries,
and paginated transaction history.

Requirements: 6.3, 6.4, 6.5, 6.7, 6.8, 6.10
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Protocol
from uuid import UUID, uuid4

import asyncpg

from platform_api.exceptions import DuplicateError, InsufficientCreditsError, ValidationError
from platform_api.services.credit_units import MAX_CREDIT_UNITS, format_credit_log_amount
from platform_api.services import credit_progress_log as credit_log

logger = logging.getLogger(__name__)

MAX_WALLET_BALANCE = MAX_CREDIT_UNITS
DEFAULT_PAGE_SIZE = 50

# Normalize v3 reasons (v3_music / v3_refund_lyric) onto the same op as desktop.
_ADMIN_OPERATION_SQL = """
COALESCE(
    NULLIF(t.metadata->>'operation', ''),
    NULLIF(t.metadata->>'op', ''),
    CASE
        WHEN t.reason LIKE 'v3_refund_%' THEN substring(t.reason from 11)
        WHEN t.reason LIKE 'v3_%' THEN substring(t.reason from 4)
        ELSE NULL
    END,
    NULLIF(split_part(t.reason, ' via ', 1), ''),
    t.reason,
    'unknown'
)
"""

# usage_tracking.operation_type values rolled into User Spent meter chips.
USER_SPEND_METER_OPS = (
    "music",
    "draft",
    "background_image",
    "thumbnail_image",
    "video",
    "video_manual",
    "video_merge",
)


def meter_bucket_for_operation(operation_type: str) -> str:
    """Map usage_tracking keys onto User Spent meter chips (song/draft/image/video/merge)."""
    op = str(operation_type or "").strip().lower()
    if op == "music":
        return "song"
    if op in ("background_image", "thumbnail_image"):
        return "image"
    if op == "video_merge":
        return "merge"
    if op == "video_manual":
        return "video"
    return op


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

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        """Yield a connection, borrowing from a pool or reusing an injected one.

        Callers normally pass an ``asyncpg`` pool. Billing fulfillment acquires a
        connection up front and passes that ``Connection`` so wallet writes join
        its transaction; a connection has no ``acquire()`` (and is already inside
        a transaction), so reuse it as-is instead of opening another one.
        """
        acquire = getattr(self._pool, "acquire", None)
        if not callable(acquire):
            yield self._pool
            return
        async with acquire() as conn:
            yield conn

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
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

        async with self._connection() as conn:
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
                        (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
                    VALUES ($1, $2, $3, 'debit', $4, $5, $6::jsonb, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                    json.dumps(metadata) if metadata else None,
                )
                credit_log.log_deducted(
                    user_id=user_id,
                    amount_units=amount,
                    reason=reason,
                    ref_id=ref_id,
                    new_balance_units=int(row["balance"]),
                )
                logger.debug(
                    "Deducted %s from user %s (reason=%s, ref=%s). New balance: %s",
                    format_credit_log_amount(amount),
                    user_id,
                    reason,
                    ref_id,
                    format_credit_log_amount(int(row["balance"])),
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
        *,
        metadata: dict[str, Any] | None = None,
        idempotent: bool = True,
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

        async with self._connection() as conn:
            async with conn.transaction():
                # Single-source idempotency: a grant with a stable ref_id is
                # credited at most once per (user, reason, ref_id). The claim and
                # the wallet update share this transaction, so a max-balance
                # failure rolls the claim back too.
                if idempotent and ref_id:
                    claimed = await conn.fetchval(
                        """
                        INSERT INTO credit_grant_claims (user_id, reason, ref_id, created_at)
                        VALUES ($1, $2, $3, NOW())
                        ON CONFLICT (user_id, reason, ref_id) DO NOTHING
                        RETURNING 1
                        """,
                        user_id,
                        reason,
                        ref_id,
                    )
                    if claimed is None:
                        logger.debug(
                            "add_credits no-op (already granted) user=%s reason=%s ref=%s",
                            user_id,
                            reason,
                            ref_id,
                        )
                        return int(
                            await conn.fetchval(
                                "SELECT balance FROM credit_wallets WHERE user_id = $1",
                                user_id,
                            )
                            or 0
                        )

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
                         payment_ref, metadata, created_at)
                    VALUES ($1, $2, $3, 'credit', $4, $5, $6, $7, $8::jsonb, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                    pack_id,
                    payment_ref,
                    json.dumps(metadata) if metadata else None,
                )
                credit_log.log_added(
                    user_id=user_id,
                    amount_units=amount,
                    reason=reason,
                    ref_id=ref_id,
                    new_balance_units=new_balance,
                )
                logger.debug(
                    "Added %s to user %s (reason=%s). New balance: %s",
                    format_credit_log_amount(amount),
                    user_id,
                    reason,
                    format_credit_log_amount(new_balance),
                )
                return new_balance

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
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

        async with self._connection() as conn:
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
                        (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
                    VALUES ($1, $2, $3, 'refund', $4, $5, $6::jsonb, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                    json.dumps(metadata) if metadata else None,
                )
                credit_log.log_refunded(
                    user_id=user_id,
                    amount_units=amount,
                    reason=reason,
                    ref_id=ref_id,
                    new_balance_units=new_balance,
                )
                logger.debug(
                    "Refunded %s to user %s (reason=%s, ref=%s). New balance: %s",
                    format_credit_log_amount(amount),
                    user_id,
                    reason,
                    ref_id,
                    format_credit_log_amount(new_balance),
                )
                return new_balance

    async def refund_once(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Refund credits at most once per ``(user_id, reason, ref_id)``.

        Retried operations (a worker re-attempting a failed Suno submit, a
        process restart) must not refund the same charge twice. The wallet row
        is locked first, which serializes concurrent refunds for the same user:
        the loser re-reads after the winner commits, sees the refund row and
        no-ops. A missing ``ref_id`` has nothing stable to key on, so it falls
        back to a plain :meth:`refund`.

        Returns:
            True when this call performed the refund, False when an identical
            refund already existed.

        Raises:
            ValidationError: If amount is not a positive integer.
            InsufficientCreditsError: If the balance cap would be exceeded.
        """
        if amount <= 0:
            raise ValidationError(
                "Refund amount must be a positive integer.",
                details={"amount": amount},
            )
        if not ref_id:
            await self.refund(user_id, amount, reason, ref_id, metadata)
            return True

        async with self._connection() as conn:
            async with conn.transaction():
                # Lock first so the existence check below cannot race a
                # concurrent refund for the same reference.
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

                existing = await conn.fetchval(
                    """
                    SELECT 1
                    FROM credit_transactions
                    WHERE user_id = $1
                      AND direction = 'refund'
                      AND reason = $2
                      AND ref_id = $3
                    LIMIT 1
                    """,
                    user_id,
                    reason,
                    ref_id,
                )
                if existing:
                    return False

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
                await conn.execute(
                    """
                    INSERT INTO credit_transactions
                        (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
                    VALUES ($1, $2, $3, 'refund', $4, $5, $6::jsonb, NOW())
                    """,
                    uuid4(),
                    user_id,
                    amount,
                    reason,
                    ref_id,
                    json.dumps(metadata) if metadata else None,
                )
                credit_log.log_refunded(
                    user_id=user_id,
                    amount_units=amount,
                    reason=reason,
                    ref_id=ref_id,
                    new_balance_units=new_balance,
                )
                logger.debug(
                    "Refund-once %s to user %s (reason=%s, ref=%s). New balance: %s",
                    format_credit_log_amount(amount),
                    user_id,
                    reason,
                    ref_id,
                    format_credit_log_amount(new_balance),
                )
                return True

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
                   pack_id, payment_ref, metadata, created_at
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
                "metadata": row.get("metadata"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

        return transactions, total or 0

    async def list_admin_usage(
        self,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        user_id: UUID | None = None,
        provider: str | None = None,
        operation: str | None = None,
        direction: str | None = None,
        reason: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        """Return paginated credit usage rows for the admin Usage page."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = DEFAULT_PAGE_SIZE

        filters: list[str] = []
        args: list[Any] = []
        arg_idx = 1

        def _add_filter(clause: str, value: Any) -> None:
            nonlocal arg_idx
            filters.append(clause.format(idx=arg_idx))
            args.append(value)
            arg_idx += 1

        if user_id is not None:
            _add_filter("t.user_id = ${idx}", user_id)
        if provider:
            _add_filter(
                "(t.metadata->>'provider' = ${idx} OR t.reason ILIKE '% via ' || ${idx})",
                provider,
            )
        if operation:
            if operation in {"song_draft", "llm_draft"}:
                filters.append(
                    f"(t.metadata->>'operation' IN ('song_draft', 'llm_draft') "
                    f"OR t.reason = 'llm_draft' "
                    f"OR t.reason IN ('draft_generation_failed', 'draft_generation_error'))"
                )
            else:
                _add_filter(
                    "(t.metadata->>'operation' = ${idx} OR t.reason = ${idx} "
                    "OR t.reason ILIKE ${idx} || ' via %')",
                    operation,
                )
        if direction:
            _add_filter("t.direction = ${idx}", direction)
        if reason:
            _add_filter("t.reason ILIKE '%' || ${idx} || '%'", reason)
        if from_date is not None:
            _add_filter("t.created_at >= ${idx}", from_date)
        if to_date is not None:
            _add_filter("t.created_at <= ${idx}", to_date)

        where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""

        total = await self._pool.fetchval(
            f"""
            SELECT COUNT(*)
            FROM credit_transactions t
            JOIN users u ON u.id = t.user_id
            {where_sql}
            """,
            *args,
        )

        offset = (page - 1) * page_size
        list_args = [*args, page_size, offset]
        rows = await self._pool.fetch(
            f"""
            SELECT
                t.id,
                t.user_id,
                u.email AS user_email,
                u.display_name AS user_display_name,
                t.amount,
                t.direction,
                t.reason,
                t.ref_id,
                t.metadata,
                t.created_at
            FROM credit_transactions t
            JOIN users u ON u.id = t.user_id
            {where_sql}
            ORDER BY t.created_at DESC
            LIMIT ${arg_idx} OFFSET ${arg_idx + 1}
            """,
            *list_args,
        )

        summary_row = await self._pool.fetchrow(
            f"""
            SELECT
                COUNT(*) FILTER (WHERE t.direction = 'debit') AS billable_events,
                COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'debit'), 0)::bigint AS debit_units,
                COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'refund'), 0)::bigint AS refund_units,
                COUNT(*) FILTER (WHERE t.direction = 'refund') AS refund_events,
                COALESCE(SUM(t.amount) FILTER (
                    WHERE t.direction = 'debit'
                      AND (
                        t.metadata->>'billing' = 'wallet'
                        OR (
                          COALESCE(t.metadata->>'billing', '') = ''
                          AND t.amount > 0
                        )
                      )
                ), 0)::bigint AS wallet_charged_units,
                COALESCE(SUM(
                    CASE
                        WHEN t.direction = 'debit'
                         AND t.metadata->>'billing' = 'plan_allowance'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS plan_included_list_units,
                COUNT(*) FILTER (
                    WHERE t.direction = 'debit'
                      AND t.metadata->>'billing' = 'plan_allowance'
                ) AS plan_allowance_events,
                COALESCE(SUM(
                    CASE
                        WHEN t.direction = 'debit'
                         AND t.metadata->>'billing' = 'plan_allowance'
                         AND t.metadata->>'coverage' = 'draft_allowance'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS plan_draft_list_units,
                COALESCE(SUM(
                    CASE
                        WHEN t.direction = 'debit'
                         AND t.metadata->>'billing' = 'plan_allowance'
                         AND t.metadata->>'coverage' = 'song_package'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS plan_song_list_units,
                COALESCE(SUM(
                    CASE
                        WHEN t.direction = 'debit'
                         AND t.metadata->>'billing' = 'plan_allowance'
                         AND t.metadata->>'coverage' = 'image_allowance'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS plan_image_list_units,
                COUNT(*) FILTER (
                    WHERE t.metadata->>'billing' = 'platform_absorb'
                ) AS platform_absorb_events,
                COALESCE(SUM(
                    CASE
                        WHEN t.metadata->>'billing' = 'platform_absorb'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS platform_absorb_list_units,
                COALESCE(SUM(t.amount) FILTER (
                    WHERE t.direction = 'credit'
                      AND t.reason IN ('v3_period_grant', 'v3_daily_grant')
                ), 0)::bigint AS grant_issued_units,
                COUNT(*) FILTER (
                    WHERE t.direction = 'credit'
                      AND t.reason IN ('v3_period_grant', 'v3_daily_grant')
                ) AS grant_issued_events
            FROM credit_transactions t
            JOIN users u ON u.id = t.user_id
            {where_sql}
            """,
            *args,
        )

        by_op_rows = await self._pool.fetch(
            f"""
            SELECT
                {_ADMIN_OPERATION_SQL} AS operation,
                COALESCE(
                    NULLIF(t.metadata->>'provider', ''),
                    NULLIF(split_part(t.reason, ' via ', 2), ''),
                    ''
                ) AS provider,
                COALESCE(
                    NULLIF(t.metadata->>'sub_model', ''),
                    NULLIF(t.metadata->>'model', ''),
                    ''
                ) AS model,
                COUNT(*) FILTER (WHERE t.direction = 'debit') AS events,
                COALESCE(SUM(t.amount) FILTER (
                    WHERE t.direction = 'debit'
                      AND (
                        t.metadata->>'billing' = 'wallet'
                        OR (
                          COALESCE(t.metadata->>'billing', '') = ''
                          AND t.amount > 0
                        )
                      )
                ), 0)::bigint AS wallet_charged_units,
                COALESCE(SUM(
                    CASE
                        WHEN t.direction = 'debit'
                         AND t.metadata->>'billing' = 'plan_allowance'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS plan_included_list_units
            FROM credit_transactions t
            JOIN users u ON u.id = t.user_id
            {where_sql}
            GROUP BY 1, 2, 3
            ORDER BY events DESC, operation ASC, provider ASC, model ASC
            LIMIT 75
            """,
            *args,
        )

        items = [
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "user_email": row["user_email"],
                "user_display_name": row["user_display_name"],
                "amount": row["amount"],
                "direction": row["direction"],
                "reason": row["reason"],
                "ref_id": row["ref_id"],
                "metadata": row.get("metadata"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        summary = {
            "billable_events": int(summary_row["billable_events"] or 0) if summary_row else 0,
            "debit_units": int(summary_row["debit_units"] or 0) if summary_row else 0,
            "refund_units": int(summary_row["refund_units"] or 0) if summary_row else 0,
            "refund_events": int(summary_row["refund_events"] or 0) if summary_row else 0,
            "wallet_charged_units": (
                int(summary_row["wallet_charged_units"] or 0) if summary_row else 0
            ),
            "plan_included_list_units": (
                int(summary_row["plan_included_list_units"] or 0) if summary_row else 0
            ),
            "plan_allowance_events": (
                int(summary_row["plan_allowance_events"] or 0) if summary_row else 0
            ),
            "plan_draft_list_units": (
                int(summary_row["plan_draft_list_units"] or 0) if summary_row else 0
            ),
            "plan_song_list_units": (
                int(summary_row["plan_song_list_units"] or 0) if summary_row else 0
            ),
            "plan_image_list_units": (
                int(summary_row["plan_image_list_units"] or 0) if summary_row else 0
            ),
            "platform_absorb_events": (
                int(summary_row["platform_absorb_events"] or 0) if summary_row else 0
            ),
            "platform_absorb_list_units": (
                int(summary_row["platform_absorb_list_units"] or 0) if summary_row else 0
            ),
            "grant_issued_units": (
                int((summary_row.get("grant_issued_units") if summary_row else 0) or 0)
            ),
            "grant_issued_events": (
                int((summary_row.get("grant_issued_events") if summary_row else 0) or 0)
            ),
            "by_operation": [
                {
                    "operation": str(row["operation"] or "unknown"),
                    "provider": str(row["provider"] or ""),
                    "model": str(row["model"] or ""),
                    "events": int(row["events"] or 0),
                    "wallet_charged_units": int(row["wallet_charged_units"] or 0),
                    "plan_included_list_units": int(row["plan_included_list_units"] or 0),
                }
                for row in by_op_rows
            ],
        }
        return items, int(total or 0), summary

    async def list_user_spend_cog_rows(
        self,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        q: str | None = None,
        provider: str | None = None,
        operation: str | None = None,
        plan_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate ledger spend by user × provider × operation × model.

        Used by the admin User Spent page. Includes soft-overage event counts
        (wallet debits that still carry plan coverage metadata).
        """
        filters: list[str] = ["t.direction = 'debit'"]
        args: list[Any] = []
        arg_idx = 1

        def _add_filter(clause: str, value: Any) -> None:
            nonlocal arg_idx
            filters.append(clause.format(idx=arg_idx))
            args.append(value)
            arg_idx += 1

        if from_date is not None:
            _add_filter("t.created_at >= ${idx}", from_date)
        if to_date is not None:
            _add_filter("t.created_at <= ${idx}", to_date)
        if q:
            q_stripped = q.strip()
            try:
                q_uuid = UUID(q_stripped)
                _add_filter("t.user_id = ${idx}", q_uuid)
            except ValueError:
                _add_filter("u.email ILIKE '%' || ${idx} || '%'", q_stripped)
        if provider:
            _add_filter(
                "(t.metadata->>'provider' = ${idx} OR t.reason ILIKE '% via ' || ${idx})",
                provider,
            )
        if operation:
            if operation in {"song_draft", "llm_draft"}:
                filters.append(
                    "(t.metadata->>'operation' IN ('song_draft', 'llm_draft') "
                    "OR t.reason = 'llm_draft' "
                    "OR t.reason IN ('draft_generation_failed', 'draft_generation_error'))"
                )
            else:
                _add_filter(
                    "(t.metadata->>'operation' = ${idx} OR t.reason = ${idx} "
                    "OR t.reason ILIKE ${idx} || ' via %')",
                    operation,
                )
        if plan_id is not None:
            filters.append(
                f"""EXISTS (
                    SELECT 1 FROM licenses l
                    WHERE l.user_id = t.user_id
                      AND l.plan_id = ${arg_idx}
                      AND l.status = 'active'
                      AND (l.expires_at IS NULL OR l.expires_at > NOW())
                    UNION ALL
                    SELECT 1 FROM web_subscriptions ws
                    WHERE ws.user_id = t.user_id
                      AND ws.plan_id = ${arg_idx}
                      AND ws.status = 'active'
                      AND ws.current_period_end > NOW()
                )"""
            )
            args.append(plan_id)
            arg_idx += 1

        where_sql = f"WHERE {' AND '.join(filters)}"

        rows = await self._pool.fetch(
            f"""
            SELECT
                t.user_id,
                u.email AS user_email,
                u.display_name AS user_display_name,
                {_ADMIN_OPERATION_SQL} AS operation,
                COALESCE(
                    NULLIF(t.metadata->>'provider', ''),
                    NULLIF(split_part(t.reason, ' via ', 2), ''),
                    ''
                ) AS provider,
                COALESCE(
                    NULLIF(t.metadata->>'sub_model', ''),
                    NULLIF(t.metadata->>'model', ''),
                    ''
                ) AS model,
                COUNT(*)::bigint AS events,
                COALESCE(SUM(t.amount) FILTER (
                    WHERE t.metadata->>'billing' = 'wallet'
                       OR (
                         COALESCE(t.metadata->>'billing', '') = ''
                         AND t.amount > 0
                       )
                ), 0)::bigint AS wallet_charged_units,
                COALESCE(SUM(
                    CASE
                        WHEN t.metadata->>'billing' = 'plan_allowance'
                        THEN COALESCE((t.metadata->>'list_credit_units')::bigint, 0)
                        ELSE 0
                    END
                ), 0)::bigint AS plan_included_list_units,
                COUNT(*) FILTER (
                    WHERE t.metadata->>'billing' = 'wallet'
                      AND t.amount > 0
                      AND COALESCE(t.metadata->>'coverage', '') IN (
                        'song_package',
                        'draft_allowance',
                        'image_allowance',
                        'video_allowance',
                        'merge_allowance'
                      )
                )::bigint AS soft_overage_events
            FROM credit_transactions t
            JOIN users u ON u.id = t.user_id
            {where_sql}
            GROUP BY 1, 2, 3, 4, 5, 6
            ORDER BY t.user_id, events DESC
            """,
            *args,
        )
        return [
            {
                "user_id": row["user_id"],
                "user_email": row["user_email"],
                "user_display_name": row["user_display_name"],
                "operation": str(row["operation"] or "unknown"),
                "provider": str(row["provider"] or ""),
                "model": str(row["model"] or ""),
                "events": int(row["events"] or 0),
                "wallet_charged_units": int(row["wallet_charged_units"] or 0),
                "plan_included_list_units": int(row["plan_included_list_units"] or 0),
                "soft_overage_events": int(row["soft_overage_events"] or 0),
            }
            for row in rows
        ]

    async def list_active_plans_for_users(
        self,
        user_ids: list[UUID],
    ) -> dict[UUID, dict[str, Any]]:
        """Return active plan + addon slots keyed by user_id."""
        if not user_ids:
            return {}
        rows = await self._pool.fetch(
            """
            SELECT DISTINCT ON (l.user_id)
                l.user_id,
                p.id AS plan_id,
                p.name AS plan_name,
                p.price_cents,
                p.billing_cycle_days,
                p.monthly_song_limit,
                p.monthly_draft_limit,
                p.monthly_image_limit,
                p.monthly_video_limit,
                p.monthly_merge_limit,
                p.profile_allowance,
                COALESCE(l.profile_addon_slots, 0) AS profile_addon_slots,
                l.activated_at
            FROM licenses l
            INNER JOIN plans p ON p.id = l.plan_id
            WHERE l.user_id = ANY($1::uuid[])
              AND l.status = 'active'
              AND (l.expires_at IS NULL OR l.expires_at > NOW())
            ORDER BY l.user_id, l.activated_at DESC
            """,
            user_ids,
        )
        out: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            out[row["user_id"]] = dict(row)
        missing = [uid for uid in user_ids if uid not in out]
        if missing:
            web_rows = await self._pool.fetch(
                """
                SELECT DISTINCT ON (ws.user_id)
                    ws.user_id,
                    p.id AS plan_id,
                    p.name AS plan_name,
                    p.price_cents,
                    p.billing_cycle_days,
                    p.monthly_song_limit,
                    p.monthly_draft_limit,
                    p.monthly_image_limit,
                    p.monthly_video_limit,
                    p.monthly_merge_limit,
                    p.profile_allowance,
                    0 AS profile_addon_slots,
                    ws.current_period_start AS activated_at
                FROM web_subscriptions ws
                INNER JOIN plans p ON p.id = ws.plan_id
                WHERE ws.user_id = ANY($1::uuid[])
                  AND ws.status = 'active'
                  AND ws.current_period_end > NOW()
                ORDER BY ws.user_id, ws.current_period_end DESC
                """,
                missing,
            )
            for row in web_rows:
                out[row["user_id"]] = dict(row)
        return out

    async def list_monthly_meters_for_users(
        self,
        user_ids: list[UUID],
        *,
        period_start: Any,
    ) -> dict[UUID, dict[str, int]]:
        """Sum monthly_count per user for music/draft/image/video/merge meters."""
        if not user_ids:
            return {}
        rows = await self._pool.fetch(
            """
            SELECT
                user_id,
                operation_type,
                COALESCE(SUM(monthly_count), 0)::bigint AS used
            FROM usage_tracking
            WHERE user_id = ANY($1::uuid[])
              AND period_start_date = $2
              AND operation_type = ANY($3::text[])
            GROUP BY user_id, operation_type
            """,
            user_ids,
            period_start,
            list(USER_SPEND_METER_OPS),
        )
        out: dict[UUID, dict[str, int]] = {uid: {} for uid in user_ids}
        for row in rows:
            uid = row["user_id"]
            used = int(row["used"] or 0)
            key = meter_bucket_for_operation(str(row["operation_type"]))
            bucket = out.setdefault(uid, {})
            bucket[key] = int(bucket.get(key) or 0) + used
        return out

    async def sum_fulfilled_subscription_revenue(
        self,
        *,
        user_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, int]:
        """Sum paid+fulfilled checkout cash from billing_payments (cents).

        Also returns credit-pack cash separately (metadata.product_type).
        ``subscription_revenue_cents`` stays total paid+fulfilled (legacy).
        """
        filters: list[str] = [
            "bp.status = 'paid'",
            "bp.fulfilled_at IS NOT NULL",
        ]
        args: list[Any] = []
        arg_idx = 1

        if user_id is not None:
            filters.append(f"bp.user_id = ${arg_idx}")
            args.append(user_id)
            arg_idx += 1
        if from_date is not None:
            filters.append(f"bp.fulfilled_at >= ${arg_idx}")
            args.append(from_date)
            arg_idx += 1
        if to_date is not None:
            filters.append(f"bp.fulfilled_at <= ${arg_idx}")
            args.append(to_date)
            arg_idx += 1

        where_sql = f"WHERE {' AND '.join(filters)}"
        row = await self._pool.fetchrow(
            f"""
            SELECT
                COALESCE(SUM(bp.amount_cents), 0)::bigint AS subscription_revenue_cents,
                COUNT(*)::bigint AS subscription_payment_count,
                COALESCE(
                    SUM(
                        CASE
                            WHEN COALESCE(bp.metadata->>'product_type', 'plan') = 'credit_pack'
                            THEN bp.amount_cents
                            ELSE 0
                        END
                    ),
                    0
                )::bigint AS credit_pack_revenue_cents,
                COALESCE(
                    SUM(
                        CASE
                            WHEN COALESCE(bp.metadata->>'product_type', 'plan') = 'credit_pack'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                )::bigint AS credit_pack_payment_count
            FROM billing_payments bp
            {where_sql}
            """,
            *args,
        )
        return {
            "subscription_revenue_cents": (
                int(row["subscription_revenue_cents"] or 0) if row else 0
            ),
            "subscription_payment_count": (
                int(row["subscription_payment_count"] or 0) if row else 0
            ),
            "credit_pack_revenue_cents": (
                int(row["credit_pack_revenue_cents"] or 0) if row else 0
            ),
            "credit_pack_payment_count": (
                int(row["credit_pack_payment_count"] or 0) if row else 0
            ),
        }

    async def get_usage_filter_options(self) -> dict[str, list[str]]:
        """Return distinct providers and operations for admin usage filters."""
        provider_rows = await self._pool.fetch(
            """
            SELECT DISTINCT value FROM (
                SELECT metadata->>'provider' AS value
                FROM credit_transactions
                WHERE metadata->>'provider' IS NOT NULL
                  AND metadata->>'provider' <> ''
                UNION
                SELECT ai_service AS value FROM credit_pricing
                UNION
                SELECT DISTINCT split_part(reason, ' via ', 2) AS value
                FROM credit_transactions
                WHERE reason LIKE '% via %'
            ) providers
            WHERE value IS NOT NULL AND value <> ''
            ORDER BY value
            """
        )
        operation_rows = await self._pool.fetch(
            """
            SELECT DISTINCT value FROM (
                SELECT metadata->>'operation' AS value
                FROM credit_transactions
                WHERE metadata->>'operation' IS NOT NULL
                  AND metadata->>'operation' <> ''
                UNION
                SELECT operation_type AS value FROM credit_pricing
                UNION
                SELECT DISTINCT split_part(reason, ' via ', 1) AS value
                FROM credit_transactions
                WHERE reason LIKE '% via %'
                UNION
                SELECT DISTINCT reason AS value
                FROM credit_transactions
                WHERE reason IN (
                    'llm_draft', 'suno_generation', 'image_generation',
                    'draft_generation_failed', 'credit_pack_purchase'
                )
            ) operations
            WHERE value IS NOT NULL AND value <> ''
            ORDER BY value
            """
        )
        return {
            "providers": [str(row["value"]) for row in provider_rows],
            "operations": [str(row["value"]) for row in operation_rows],
        }

    async def patch_transaction_metadata(
        self,
        user_id: UUID,
        ref_id: str,
        patch: dict[str, Any],
    ) -> bool:
        """Merge fields into an existing transaction's metadata JSON."""
        if not patch:
            return False
        result = await self._pool.execute(
            """
            UPDATE credit_transactions
            SET metadata = COALESCE(metadata, '{}'::jsonb) || $3::jsonb
            WHERE id = (
                SELECT id
                FROM credit_transactions
                WHERE user_id = $1
                  AND ref_id = $2
                  AND direction = 'debit'
                ORDER BY created_at DESC
                LIMIT 1
            )
            """,
            user_id,
            ref_id,
            json.dumps(patch),
        )
        return result.endswith("1")

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

    async def record_ledger_entry(
        self,
        user_id: UUID,
        amount: int,
        direction: str,
        reason: str,
        *,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        """Insert a usage-ledger row without changing wallet balance.

        Unlike ``atomic_deduct`` / ``record_transaction``, ``amount`` may be 0
        (plan-covered song/image package ops that still need audit rows).

        Args:
            user_id: Wallet owner.
            amount: Non-negative micro-credit units (0 allowed).
            direction: One of 'credit', 'debit', or 'refund'.
            reason: Human-readable reason.
            ref_id: Optional reference (batch/task/song).
            metadata: Full usage metadata (billing, list price, coverage, …).

        Returns:
            New transaction UUID.

        Raises:
            ValidationError: Invalid direction or negative amount.
        """
        valid_directions = {"credit", "debit", "refund"}
        if direction not in valid_directions:
            raise ValidationError(
                f"Invalid transaction direction '{direction}'. "
                f"Must be one of: {', '.join(sorted(valid_directions))}.",
                details={"direction": direction},
            )
        if amount < 0:
            raise ValidationError(
                "Ledger amount must be a non-negative integer.",
                details={"amount": amount},
            )

        txn_id = uuid4()
        await self._pool.execute(
            """
            INSERT INTO credit_transactions
                (id, user_id, amount, direction, reason, ref_id, metadata, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, NOW())
            """,
            txn_id,
            user_id,
            amount,
            direction,
            reason,
            ref_id,
            json.dumps(metadata) if metadata else None,
        )
        logger.debug(
            "Ledger %s amount=%s user=%s reason=%s",
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
            SELECT id, ai_service, operation_type, sub_model, credits_per_operation,
                   external_cost_cents, needs_review, created_at, updated_at
            FROM credit_pricing
            ORDER BY ai_service, operation_type, sub_model
            """
        )
        return [dict(r) for r in rows]

    async def get_by_service_and_operation(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        """Return a pricing entry for an ai_service/operation/model combination."""
        row = await self._pool.fetchrow(
            """
            SELECT id, ai_service, operation_type, sub_model, credits_per_operation,
                   external_cost_cents, needs_review, created_at, updated_at
            FROM credit_pricing
            WHERE ai_service = $1 AND operation_type = $2 AND sub_model = $3
            """,
            ai_service,
            operation_type,
            sub_model,
        )
        return dict(row) if row else None

    async def create(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
        needs_review: bool = False,
    ) -> dict[str, Any]:
        """Create a new pricing entry.

        Raises:
            DuplicateError: If a pricing entry already exists for the
                (ai_service, operation_type, sub_model) combination.
        """
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO credit_pricing (id, ai_service, operation_type, sub_model,
                                            credits_per_operation, external_cost_cents,
                                            needs_review, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, NOW(), NOW())
                RETURNING id, ai_service, operation_type, sub_model, credits_per_operation,
                          external_cost_cents, needs_review, created_at, updated_at
                """,
                ai_service,
                operation_type,
                sub_model,
                credits_per_operation,
                external_cost_cents,
                needs_review,
            )
        except asyncpg.UniqueViolationError:
            raise DuplicateError(
                f"Pricing already exists for ai_service '{ai_service}' "
                f"operation '{operation_type}' model '{sub_model or 'default'}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": sub_model,
                },
            )
        return dict(row)

    async def update(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        """Update an existing pricing entry. Returns None if not found."""
        row = await self._pool.fetchrow(
            """
            UPDATE credit_pricing
            SET credits_per_operation = $4,
                external_cost_cents = $5,
                needs_review = FALSE,
                updated_at = NOW()
            WHERE ai_service = $1 AND operation_type = $2 AND sub_model = $3
            RETURNING id, ai_service, operation_type, sub_model, credits_per_operation,
                      external_cost_cents, needs_review, created_at, updated_at
            """,
            ai_service,
            operation_type,
            sub_model,
            credits_per_operation,
            external_cost_cents,
        )
        return dict(row) if row else None

    async def delete(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str = "",
    ) -> bool:
        """Delete a pricing entry. Returns True if deleted."""
        result = await self._pool.execute(
            """
            DELETE FROM credit_pricing
            WHERE ai_service = $1 AND operation_type = $2 AND sub_model = $3
            """,
            ai_service,
            operation_type,
            sub_model,
        )
        return "DELETE 1" in result

    async def delete_all(self, *, ai_service: str | None = None) -> int:
        """Delete all pricing entries, optionally scoped to one provider."""
        if ai_service:
            result = await self._pool.execute(
                "DELETE FROM credit_pricing WHERE ai_service = $1",
                ai_service,
            )
        else:
            result = await self._pool.execute("DELETE FROM credit_pricing")
        return int(result.split()[-1]) if result else 0

    async def approve(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        """Mark a pricing row as reviewed (clears needs_review)."""
        row = await self._pool.fetchrow(
            """
            UPDATE credit_pricing
            SET needs_review = FALSE, updated_at = NOW()
            WHERE ai_service = $1 AND operation_type = $2 AND sub_model = $3
            RETURNING id, ai_service, operation_type, sub_model, credits_per_operation,
                      external_cost_cents, needs_review, created_at, updated_at
            """,
            ai_service,
            operation_type,
            sub_model,
        )
        return dict(row) if row else None

    async def approve_many(
        self, pairs: list[tuple[str, str, str]]
    ) -> int:
        """Approve multiple pricing rows. Returns count updated."""
        if not pairs:
            return 0
        ai_services = [p[0] for p in pairs]
        operation_types = [p[1] for p in pairs]
        sub_models = [p[2] for p in pairs]
        result = await self._pool.execute(
            """
            UPDATE credit_pricing AS cp
            SET needs_review = FALSE, updated_at = NOW()
            FROM unnest($1::text[], $2::text[], $3::text[])
                AS batch(ai_service, operation_type, sub_model)
            WHERE cp.ai_service = batch.ai_service
              AND cp.operation_type = batch.operation_type
              AND cp.sub_model = batch.sub_model
              AND cp.needs_review = TRUE
            """,
            ai_services,
            operation_types,
            sub_models,
        )
        # asyncpg returns "UPDATE N"
        try:
            return int(str(result).split()[-1])
        except (ValueError, IndexError):
            return 0

    # -----------------------------------------------------------------------
    # Credit Packs queries
    # -----------------------------------------------------------------------

    async def get_all_packs(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        """Return credit packs for admin or storefront listing."""
        if include_inactive:
            rows = await self._pool.fetch(
                """
                SELECT id, name, price_cents, song_credits, request_count,
                       is_active, created_at, updated_at
                FROM credit_packs
                ORDER BY price_cents, name
                """
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id, name, price_cents, song_credits, request_count,
                       is_active, created_at, updated_at
                FROM credit_packs
                WHERE is_active = true
                ORDER BY price_cents, name
                """
            )
        return [dict(r) for r in rows]

    async def get_active_packs(self) -> list[dict[str, Any]]:
        """Return all active credit packs."""
        return await self.get_all_packs(include_inactive=False)

    async def create_pack(
        self,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int,
        is_active: bool,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO credit_packs (
                id, name, price_cents, song_credits, request_count,
                is_active, created_at, updated_at
            )
            VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, NOW(), NOW())
            RETURNING id, name, price_cents, song_credits, request_count,
                      is_active, created_at, updated_at
            """,
            name,
            price_cents,
            song_credits,
            request_count,
            is_active,
        )
        return dict(row)

    async def update_pack(
        self,
        pack_id: UUID,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int,
        is_active: bool,
    ) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            UPDATE credit_packs
            SET name = $2,
                price_cents = $3,
                song_credits = $4,
                request_count = $5,
                is_active = $6,
                updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, price_cents, song_credits, request_count,
                      is_active, created_at, updated_at
            """,
            pack_id,
            name,
            price_cents,
            song_credits,
            request_count,
            is_active,
        )
        return dict(row) if row else None

    async def delete_pack(self, pack_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM credit_packs WHERE id = $1",
            pack_id,
        )
        return "DELETE 1" in result

    async def get_packs_by_type(
        self,
        pack_type: str,
        *,
        include_inactive: bool = True,
    ) -> list[dict[str, Any]]:
        """Return credit packs for a given pack_type."""
        if include_inactive:
            rows = await self._pool.fetch(
                """
                SELECT id, slug, name, pack_type, total_credits, price_cents,
                       song_credits, request_count, display_order, is_active,
                       created_at, updated_at
                FROM credit_packs
                WHERE pack_type = $1
                ORDER BY display_order ASC, price_cents ASC
                """,
                pack_type,
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id, slug, name, pack_type, total_credits, price_cents,
                       song_credits, request_count, display_order, is_active,
                       created_at, updated_at
                FROM credit_packs
                WHERE pack_type = $1 AND is_active = true
                ORDER BY display_order ASC, price_cents ASC
                """,
                pack_type,
            )
        return [dict(r) for r in rows]

    async def create_web_music_pack(
        self,
        *,
        slug: str,
        name: str,
        total_credits: int,
        price_cents: int,
        display_order: int,
        is_active: bool,
    ) -> dict[str, Any]:
        songs = max(1, total_credits // 10)
        row = await self._pool.fetchrow(
            """
            INSERT INTO credit_packs (
                slug, name, pack_type, total_credits, price_cents,
                song_credits, request_count, display_order, is_active,
                created_at, updated_at
            )
            VALUES ($1, $2, 'web_music', $3, $4, $5, $5, $6, $7, NOW(), NOW())
            RETURNING id, slug, name, pack_type, total_credits, price_cents,
                      song_credits, request_count, display_order, is_active,
                      created_at, updated_at
            """,
            slug,
            name,
            total_credits,
            price_cents,
            songs,
            display_order,
            is_active,
        )
        return dict(row)

    async def update_web_music_pack(
        self,
        pack_id: UUID,
        *,
        slug: str | None = None,
        name: str | None = None,
        total_credits: int | None = None,
        price_cents: int | None = None,
        display_order: int | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any] | None:
        from datetime import datetime, timezone

        fields: dict[str, Any] = {}
        if slug is not None:
            fields["slug"] = slug
        if name is not None:
            fields["name"] = name
        if total_credits is not None:
            fields["total_credits"] = total_credits
            fields["song_credits"] = max(1, total_credits // 10)
            fields["request_count"] = max(1, total_credits // 10)
        if price_cents is not None:
            fields["price_cents"] = price_cents
        if display_order is not None:
            fields["display_order"] = display_order
        if is_active is not None:
            fields["is_active"] = is_active
        if not fields:
            row = await self._pool.fetchrow(
                """
                SELECT id, slug, name, pack_type, total_credits, price_cents,
                       song_credits, request_count, display_order, is_active,
                       created_at, updated_at
                FROM credit_packs
                WHERE id = $1 AND pack_type = 'web_music'
                """,
                pack_id,
            )
            return dict(row) if row else None

        set_parts: list[str] = []
        values: list[Any] = []
        param_idx = 1
        for col, val in fields.items():
            set_parts.append(f"{col} = ${param_idx}")
            values.append(val)
            param_idx += 1
        set_parts.append(f"updated_at = ${param_idx}")
        values.append(datetime.now(timezone.utc))
        param_idx += 1
        values.append(pack_id)

        row = await self._pool.fetchrow(
            f"""
            UPDATE credit_packs
            SET {', '.join(set_parts)}
            WHERE id = ${param_idx} AND pack_type = 'web_music'
            RETURNING id, slug, name, pack_type, total_credits, price_cents,
                      song_credits, request_count, display_order, is_active,
                      created_at, updated_at
            """,
            *values,
        )
        return dict(row) if row else None

    async def delete_web_music_pack(self, pack_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM credit_packs WHERE id = $1 AND pack_type = 'web_music'",
            pack_id,
        )
        return "DELETE 1" in result

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
