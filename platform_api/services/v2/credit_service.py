"""Credit service for web music credit management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

from platform_api.models.products import (
    MUSIC_WEB_FREE_RESET_PERIOD_DEFAULT,
    MUSIC_WEB_FREE_RESET_PERIOD_KEY,
    WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT,
    WEB_MUSIC_FREE_DAILY_CREDITS_KEY,
)
from platform_api.services.billing_calendar import (
    billing_month_start,
    billing_today,
    next_billing_midnight,
    next_billing_month_start,
)

logger = logging.getLogger(__name__)

_ACTIVE_SUBSCRIPTION_SQL = """
    user_id = $1
    AND status = 'active'
    AND current_period_end > NOW()
"""


@dataclass
class DetailedBalance:
    """Unified credit balance for web music."""

    has_subscription: bool
    monthly_granted: int
    monthly_used: int
    monthly_remaining: int
    topup_balance: int
    daily_free_limit: int
    daily_free_used: int
    daily_free_remaining: int
    total_available: int
    reset_at: datetime | None
    current_period_end: datetime | None = None
    free_reset_period: str = "daily"


@dataclass
class Transaction:
    """Credit transaction record."""

    id: str
    user_id: str
    amount: int
    direction: str  # 'credit' or 'debit'
    reason: str
    ref_id: Optional[str]
    created_at: datetime


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits."""

    pass


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


class CreditService:
    """Web music credits: subscription monthly/top-up, or daily free pool."""

    def __init__(self, db):
        self._db = db

    async def daily_free_limit(self) -> int:
        plan_row = await self._db.fetch_one(
            """
            SELECT daily_credits
            FROM plans
            WHERE lower(name) = 'free'
              AND is_active = true
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        if plan_row is not None:
            try:
                return max(0, int(_row_value(plan_row, "daily_credits") or 0))
            except (TypeError, ValueError):
                pass
        row = await self._db.fetch_one(
            "SELECT value FROM system_settings WHERE key = $1",
            WEB_MUSIC_FREE_DAILY_CREDITS_KEY,
        )
        raw = _row_value(row, "value")
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT
        return max(0, limit)

    async def free_reset_period(self) -> str:
        """Free music-web allowance refill cadence: 'daily' or 'monthly'.

        Reads system_settings ``music_web_free_reset_period`` (default 'daily').
        When 'monthly', the free pool refills once per billing month instead of
        every billing day, and unused credits expire at the month boundary.
        """
        row = await self._db.fetch_one(
            "SELECT value FROM system_settings WHERE key = $1",
            MUSIC_WEB_FREE_RESET_PERIOD_KEY,
        )
        raw = str(_row_value(row, "value") or "").strip().lower()
        return "monthly" if raw == "monthly" else MUSIC_WEB_FREE_RESET_PERIOD_DEFAULT

    async def _period_anchor_date(self) -> date:
        """Usage bucket key: billing day, or month start when cadence is monthly."""
        anchor = billing_today()
        if await self.free_reset_period() == "monthly":
            anchor = billing_month_start(anchor)
        return anchor

    async def _daily_credits_used(self, user_id: str) -> int:
        period = await self._period_anchor_date()
        used = await self._db.fetch_val(
            """
            SELECT COALESCE(credits_used, 0)::int
            FROM web_music_daily_usage
            WHERE user_id = $1 AND usage_date = $2
            """,
            user_id,
            period,
        )
        return int(used or 0)

    async def _refresh_subscription_state(self, user_id: str) -> None:
        """Expire or renew subscriptions whose billing period has ended."""
        from platform_api.services.v2.subscription_service import SubscriptionService

        try:
            await SubscriptionService(self._db).get_user_subscription(user_id)
        except Exception as exc:
            logger.warning("Subscription refresh failed for user %s: %s", user_id, exc)

    async def _refund_already_applied(
        self,
        user_id: str,
        reason: str,
        reference_id: Optional[str],
    ) -> bool:
        if not reference_id:
            return False
        existing = await self._db.fetch_val(
            """
            SELECT 1
            FROM credit_transactions
            WHERE user_id = $1
              AND ref_id = $2
              AND reason = $3
              AND direction = 'credit'
            LIMIT 1
            """,
            user_id,
            reference_id,
            reason,
        )
        return bool(existing)

    async def _lookup_debit_split(
        self,
        user_id: str,
        reference_id: Optional[str],
        source: str,
    ) -> tuple[int, int] | None:
        if not reference_id:
            return None
        row = await self._db.fetch_one(
            """
            SELECT metadata
            FROM credit_transactions
            WHERE user_id = $1
              AND ref_id = $2
              AND reason = $3
              AND direction = 'debit'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            reference_id,
            f"consumed_{source}",
        )
        if row is None:
            return None
        meta = row.get("metadata")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                return None
        if not isinstance(meta, dict):
            return None
        monthly = int(meta.get("monthly") or 0)
        topup = int(meta.get("topup") or 0)
        if monthly <= 0 and topup <= 0:
            return None
        return monthly, topup

    @staticmethod
    def _fallback_refund_split(
        amount: int,
        *,
        monthly_used: int,
        monthly_granted: int,
    ) -> tuple[int, int]:
        """Best-effort split when debit metadata is unavailable."""
        if monthly_used >= monthly_granted:
            return 0, amount
        restore_monthly = min(amount, monthly_used)
        return restore_monthly, amount - restore_monthly

    async def get_detailed_balance(self, user_id: str) -> DetailedBalance:
        """Return unified balance (subscription pools or daily free credits)."""
        await self._refresh_subscription_state(user_id)
        period = await self.free_reset_period()
        subscription = await self._db.fetch_one(
            f"""
            SELECT
                monthly_credits_granted,
                monthly_credits_used,
                topup_credits_balance,
                current_period_end,
                billing_cycle,
                last_credit_reset,
                current_period_start
            FROM web_subscriptions
            WHERE {_ACTIVE_SUBSCRIPTION_SQL}
            """,
            user_id,
        )

        daily_limit = await self.daily_free_limit()
        daily_used = await self._daily_credits_used(user_id)
        daily_remaining = max(0, daily_limit - daily_used)

        if subscription:
            monthly_remaining = max(
                0,
                int(subscription["monthly_credits_granted"] or 0)
                - int(subscription["monthly_credits_used"] or 0),
            )
            topup_balance = int(subscription["topup_credits_balance"] or 0)
            last_reset = (
                subscription.get("last_credit_reset")
                or subscription["current_period_start"]
            )
            from platform_api.services.v2.subscription_service import next_credit_reset_at

            return DetailedBalance(
                has_subscription=True,
                monthly_granted=int(subscription["monthly_credits_granted"] or 0),
                monthly_used=int(subscription["monthly_credits_used"] or 0),
                monthly_remaining=monthly_remaining,
                topup_balance=topup_balance,
                daily_free_limit=daily_limit,
                daily_free_used=daily_used,
                daily_free_remaining=0,
                total_available=monthly_remaining + topup_balance,
                reset_at=next_credit_reset_at(
                    billing_cycle=subscription["billing_cycle"],
                    current_period_end=subscription["current_period_end"],
                    last_credit_reset=last_reset,
                ),
                current_period_end=subscription["current_period_end"],
                free_reset_period=period,
            )

        return DetailedBalance(
            has_subscription=False,
            monthly_granted=0,
            monthly_used=0,
            monthly_remaining=0,
            topup_balance=0,
            daily_free_limit=daily_limit,
            daily_free_used=daily_used,
            daily_free_remaining=daily_remaining,
            total_available=daily_remaining,
            reset_at=(
                next_billing_month_start() if period == "monthly" else next_billing_midnight()
            ),
            current_period_end=None,
            free_reset_period=period,
        )

    async def get_total_balance(self, user_id: str) -> int:
        balance = await self.get_detailed_balance(user_id)
        return balance.total_available

    async def has_sufficient_credits(self, user_id: str, required: int) -> bool:
        total = await self.get_total_balance(user_id)
        return total >= required

    async def consume_credits(
        self,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
    ) -> bool:
        if amount <= 0:
            raise ValueError("Amount must be positive")

        await self._refresh_subscription_state(user_id)

        async with self._db.transaction():
            subscription = await self._db.fetch_one(
                f"""
                SELECT
                    id, monthly_credits_granted, monthly_credits_used,
                    topup_credits_balance
                FROM web_subscriptions
                WHERE {_ACTIVE_SUBSCRIPTION_SQL}
                FOR UPDATE
                """,
                user_id,
            )

            if subscription:
                return await self._consume_subscription_credits(
                    user_id=user_id,
                    amount=amount,
                    source=source,
                    reference_id=reference_id,
                    subscription=subscription,
                )

            return await self._consume_daily_free_credits(
                user_id=user_id,
                amount=amount,
                source=source,
                reference_id=reference_id,
            )

    async def _consume_subscription_credits(
        self,
        *,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str],
        subscription: Any,
    ) -> bool:
        monthly_remaining = max(
            0,
            int(subscription["monthly_credits_granted"] or 0)
            - int(subscription["monthly_credits_used"] or 0),
        )
        topup_balance = int(subscription["topup_credits_balance"] or 0)
        total_available = monthly_remaining + topup_balance

        if total_available < amount:
            songs_remaining = total_available // 10
            raise InsufficientCreditsError(
                f"Insufficient credits. Required: {amount}, Available: {total_available} "
                f"({songs_remaining} songs remaining)."
            )

        if amount <= monthly_remaining:
            await self._db.execute(
                """
                UPDATE web_subscriptions
                SET monthly_credits_used = monthly_credits_used + $1
                WHERE id = $2
                """,
                amount,
                subscription["id"],
            )
            consumed_monthly = amount
            consumed_topup = 0
        else:
            consumed_monthly = monthly_remaining
            consumed_topup = amount - monthly_remaining
            await self._db.execute(
                """
                UPDATE web_subscriptions
                SET monthly_credits_used = monthly_credits_granted,
                    topup_credits_balance = topup_credits_balance - $1
                WHERE id = $2
                """,
                consumed_topup,
                subscription["id"],
            )

        await self._log_debit(
            user_id,
            amount,
            source,
            reference_id,
            metadata={"monthly": consumed_monthly, "topup": consumed_topup},
        )
        logger.info(
            "Consumed %s subscription credits from user %s: monthly=%s topup=%s",
            amount,
            user_id,
            consumed_monthly,
            consumed_topup,
        )
        return True

    async def _consume_daily_free_credits(
        self,
        *,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str],
    ) -> bool:
        period = await self._period_anchor_date()
        monthly = await self.free_reset_period() == "monthly"
        daily_limit = await self.daily_free_limit()
        if daily_limit <= 0:
            raise InsufficientCreditsError("Subscribe to create songs.")

        row = await self._db.fetch_one(
            """
            INSERT INTO web_music_daily_usage (user_id, usage_date, credits_used, generation_count)
            SELECT $1, $2, $3, 1
            WHERE COALESCE(
                (SELECT credits_used FROM web_music_daily_usage WHERE user_id = $1 AND usage_date = $2),
                0
            ) + $3 <= $4
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET
                credits_used = web_music_daily_usage.credits_used + $3,
                generation_count = web_music_daily_usage.generation_count + 1
            WHERE web_music_daily_usage.credits_used + $3 <= $4
            RETURNING credits_used
            """,
            user_id,
            period,
            amount,
            daily_limit,
        )
        if row is None:
            used = await self._daily_credits_used(user_id)
            remaining = max(0, daily_limit - used)
            if monthly:
                raise InsufficientCreditsError(
                    f"Insufficient credits. You need {amount} credits per song. "
                    f"You have {remaining} free credits left this month ({remaining // 10} songs). "
                    f"Free credits reset at the end of the month."
                )
            raise InsufficientCreditsError(
                f"Insufficient credits. You need {amount} credits per song. "
                f"You have {remaining} free credits left today ({remaining // 10} songs). "
                f"Daily credits reset tomorrow."
            )

        await self._log_debit(user_id, amount, source, reference_id)
        logger.info(
            "Consumed %s free credits from user %s (%s/%s used %s)",
            amount,
            user_id,
            row["credits_used"],
            daily_limit,
            "this month" if monthly else "today",
        )
        return True

    async def refund_credits(
        self,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str] = None,
    ) -> bool:
        """Refund credits after a failed operation (idempotent when reference_id is set)."""
        if amount <= 0:
            return False

        reason = f"refunded_{source}"
        if await self._refund_already_applied(user_id, reason, reference_id):
            logger.info(
                "Skipping duplicate refund user=%s source=%s ref_id=%s",
                user_id,
                source,
                reference_id,
            )
            return True

        await self._refresh_subscription_state(user_id)

        subscription = await self._db.fetch_one(
            f"""
            SELECT id, monthly_credits_granted, monthly_credits_used, topup_credits_balance
            FROM web_subscriptions
            WHERE {_ACTIVE_SUBSCRIPTION_SQL}
            """,
            user_id,
        )
        if subscription:
            return await self._refund_subscription_credits(
                user_id=user_id,
                amount=amount,
                source=source,
                reference_id=reference_id,
                subscription=subscription,
            )

        async with self._db.transaction():
            if await self._refund_already_applied(user_id, reason, reference_id):
                return True

            day = await self._period_anchor_date()
            await self._db.execute(
                """
                UPDATE web_music_daily_usage
                SET credits_used = GREATEST(credits_used - $3, 0),
                    generation_count = GREATEST(generation_count - 1, 0)
                WHERE user_id = $1 AND usage_date = $2
                """,
                user_id,
                day,
                amount,
            )
            await self._log_credit(user_id, amount, reason, reference_id)
            logger.info("Refunded %s free credits to user %s", amount, user_id)
            return True

    async def _refund_subscription_credits(
        self,
        *,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str],
        subscription: Any,
    ) -> bool:
        reason = f"refunded_{source}"
        split = await self._lookup_debit_split(user_id, reference_id, source)
        monthly_used = int(subscription["monthly_credits_used"] or 0)
        monthly_granted = int(subscription["monthly_credits_granted"] or 0)
        if split:
            restore_monthly, restore_topup = split
        else:
            restore_monthly, restore_topup = self._fallback_refund_split(
                amount,
                monthly_used=monthly_used,
                monthly_granted=monthly_granted,
            )

        async with self._db.transaction():
            if await self._refund_already_applied(user_id, reason, reference_id):
                return True

            locked = await self._db.fetch_one(
                """
                SELECT id, monthly_credits_used, topup_credits_balance
                FROM web_subscriptions
                WHERE id = $1
                  AND user_id = $2
                  AND status = 'active'
                  AND current_period_end > NOW()
                FOR UPDATE
                """,
                subscription["id"],
                user_id,
            )
            if locked is None:
                return False

            if restore_monthly > 0:
                await self._db.execute(
                    """
                    UPDATE web_subscriptions
                    SET monthly_credits_used = GREATEST(monthly_credits_used - $1, 0)
                    WHERE id = $2
                    """,
                    restore_monthly,
                    subscription["id"],
                )
            if restore_topup > 0:
                await self._db.execute(
                    """
                    UPDATE web_subscriptions
                    SET topup_credits_balance = topup_credits_balance + $1
                    WHERE id = $2
                    """,
                    restore_topup,
                    subscription["id"],
                )

            await self._log_credit(
                user_id,
                amount,
                reason,
                reference_id,
                metadata={"monthly": restore_monthly, "topup": restore_topup},
            )
            logger.info(
                "Refunded %s subscription credits to user %s: monthly=%s topup=%s",
                amount,
                user_id,
                restore_monthly,
                restore_topup,
            )
            return True

    async def _log_debit(
        self,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str],
        *,
        metadata: Optional[dict[str, int]] = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO credit_transactions (
                user_id, amount, direction, reason, ref_id, metadata
            ) VALUES (
                $1, $2, 'debit', $3, $4, $5::jsonb
            )
            """,
            user_id,
            -amount,
            f"consumed_{source}",
            reference_id,
            json.dumps(metadata) if metadata else None,
        )

    async def _log_credit(
        self,
        user_id: str,
        amount: int,
        reason: str,
        reference_id: Optional[str],
        *,
        metadata: Optional[dict[str, int]] = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO credit_transactions (
                user_id, amount, direction, reason, ref_id, metadata
            ) VALUES (
                $1, $2, 'credit', $3, $4, $5::jsonb
            )
            """,
            user_id,
            amount,
            reason,
            reference_id,
            json.dumps(metadata) if metadata else None,
        )

    async def check_and_consume(
        self,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str] = None,
    ) -> None:
        await self.consume_credits(user_id, amount, source, reference_id)

    async def grant_credits(
        self,
        user_id: str,
        amount: int,
        source: str,
        reference_id: Optional[str] = None,
        credit_type: str = "topup",
    ) -> bool:
        if amount <= 0:
            raise ValueError("Amount must be positive")

        async with self._db.transaction():
            if credit_type == "topup":
                await self._db.execute(
                    """
                    UPDATE web_subscriptions
                    SET topup_credits_balance = topup_credits_balance + $1
                    WHERE user_id = $2 AND status = 'active'
                    """,
                    amount,
                    user_id,
                )
            elif credit_type == "monthly":
                await self._db.execute(
                    """
                    UPDATE web_subscriptions
                    SET monthly_credits_granted = monthly_credits_granted + $1
                    WHERE user_id = $2 AND status = 'active'
                    """,
                    amount,
                    user_id,
                )
            else:
                raise ValueError(f"Invalid credit_type: {credit_type}")

            await self._db.execute(
                """
                INSERT INTO credit_transactions (
                    user_id, amount, direction, reason, ref_id
                ) VALUES (
                    $1, $2, 'credit', $3, $4
                )
                """,
                user_id,
                amount,
                f"granted_{source}",
                reference_id,
            )

            logger.info("Granted %s %s credits to user %s", amount, credit_type, user_id)
            return True

    async def get_transaction_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        rows = await self._db.fetch_all(
            """
            SELECT
                id, user_id, amount, direction, reason,
                ref_id, created_at
            FROM credit_transactions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
        return [Transaction(**dict(row)) for row in rows]

    async def get_transaction_count(self, user_id: str) -> int:
        return await self._db.fetch_val(
            """
            SELECT COUNT(*)
            FROM credit_transactions
            WHERE user_id = $1
            """,
            user_id,
        )

    async def manual_credit_adjustment(
        self,
        user_id: str,
        amount: int,
        reason: str,
        admin_id: str,
    ) -> bool:
        if amount == 0:
            return False

        if amount > 0:
            await self.grant_credits(
                user_id=user_id,
                amount=amount,
                source="manual_adjustment",
                reference_id=admin_id,
                credit_type="topup",
            )
        else:
            await self.consume_credits(
                user_id=user_id,
                amount=abs(amount),
                source="manual_adjustment",
                reference_id=admin_id,
            )

        logger.warning(
            "Admin %s adjusted credits for user %s: %+d (%s)",
            admin_id,
            user_id,
            amount,
            reason,
        )
        return True


def get_credit_service(db) -> CreditService:
    return CreditService(db)
