"""Credit wallet repository with atomic deduction and transaction recording.

Provides atomic balance operations using PostgreSQL's conditional UPDATE pattern,
credit addition with max-balance enforcement, refund processing, balance queries,
and paginated transaction history.

Requirements: 6.3, 6.4, 6.5, 6.7, 6.8, 6.10
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

import asyncpg

from platform_api.exceptions import DuplicateError, InsufficientCreditsError, ValidationError
from platform_api.services.credit_units import MAX_CREDIT_UNITS, format_credit_log_amount
from platform_api.services import credit_progress_log as credit_log

logger = logging.getLogger(__name__)

MAX_WALLET_BALANCE = MAX_CREDIT_UNITS
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
                ), 0)::bigint AS platform_absorb_list_units
            FROM credit_transactions t
            JOIN users u ON u.id = t.user_id
            {where_sql}
            """,
            *args,
        )

        by_op_rows = await self._pool.fetch(
            f"""
            SELECT
                COALESCE(
                    NULLIF(t.metadata->>'operation', ''),
                    NULLIF(split_part(t.reason, ' via ', 1), ''),
                    t.reason,
                    'unknown'
                ) AS operation,
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

    async def sum_fulfilled_subscription_revenue(
        self,
        *,
        user_id: UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, int]:
        """Sum paid+fulfilled plan checkout cash from billing_payments (cents)."""
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
                COUNT(*)::bigint AS subscription_payment_count
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
