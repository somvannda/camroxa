"""Usage enforcement service for credit balance and quota checks.

Orchestrates the enforcement check order before any AI generation request:
1. Verify pricing exists for the requested operation
2. Check credit balance is sufficient
3. Check daily limit per channel has not been reached
4. Check monthly limit has not been reached
5. Atomically deduct credits and increment usage counters

Uses Redis for fast daily usage caching with a 25-hour TTL.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 1.5
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    QuotaExceededError,
)
from platform_api.models.domain import Plan

logger = logging.getLogger(__name__)

# TTL for daily usage cache keys: 25 hours (ensures expiry after day rolls over)
DAILY_CACHE_TTL_SECONDS = 25 * 60 * 60


# ---------------------------------------------------------------------------
# Protocol interfaces for dependency injection
# ---------------------------------------------------------------------------


class CreditRepositoryProtocol(Protocol):
    """Protocol for credit repository operations needed by enforcement."""

    async def get_balance(self, user_id: UUID | str) -> int:
        """Return the current credit balance for a user."""
        ...

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> bool:
        """Atomically deduct credits. Returns True on success, False if insufficient."""
        ...


class UsageTrackingRepositoryProtocol(Protocol):
    """Protocol for usage tracking repository operations."""

    async def get_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int:
        """Return the daily usage count for a specific partition."""
        ...

    async def get_monthly_count(
        self,
        user_id: UUID,
        operation_type: str,
        period_start: date,
    ) -> int:
        """Return the total monthly usage count."""
        ...

    async def increment_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        period_start: date,
    ) -> None:
        """Atomically increment daily and monthly usage counters."""
        ...


class PlanRepositoryProtocol(Protocol):
    """Protocol for plan repository operations needed by enforcement."""

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None:
        """Get the plan associated with the user's active license."""
        ...


class CreditPricingRepositoryProtocol(Protocol):
    """Protocol for credit pricing repository operations needed by enforcement."""

    async def get_by_service_and_operation(
        self, ai_service: str, operation_type: str
    ) -> dict[str, Any] | None:
        """Return a pricing entry for an ai_service/operation combination."""
        ...


class RedisProtocol(Protocol):
    """Protocol for Redis connection operations needed by enforcement."""

    async def get(self, key: str) -> bytes | str | None:
        """Get a value by key."""
        ...

    async def incr(self, key: str) -> int:
        """Increment a key's integer value."""
        ...

    async def expire(self, key: str, seconds: int) -> bool:
        """Set a TTL on a key."""
        ...

    async def set(
        self, key: str, value: Any, ex: int | None = None
    ) -> bool | None:
        """Set a key with optional expiry."""
        ...


# ---------------------------------------------------------------------------
# Usage Enforcement Service
# ---------------------------------------------------------------------------


class UsageEnforcementService:
    """Enforces credit balance, daily limits, and monthly limits.

    Check order (Requirement 6.1):
    1. Get pricing for the operation (credits_per_operation)
    2. Credit balance >= credits_per_operation
    3. Daily limit for operation type per channel not reached
    4. Monthly limit for operation type not reached

    After all checks pass: atomic deduction + usage increment.

    Args:
        credit_repo: Repository for credit wallet operations.
        usage_repo: Repository for usage tracking operations.
        plan_repo: Repository for plan/license lookups.
        pricing_repo: Repository for credit pricing lookups.
        redis: Redis connection for daily usage caching.
    """

    def __init__(
        self,
        credit_repo: CreditRepositoryProtocol,
        usage_repo: UsageTrackingRepositoryProtocol,
        plan_repo: PlanRepositoryProtocol,
        pricing_repo: CreditPricingRepositoryProtocol,
        redis: RedisProtocol,
    ) -> None:
        self._credit_repo = credit_repo
        self._usage_repo = usage_repo
        self._plan_repo = plan_repo
        self._pricing_repo = pricing_repo
        self._redis = redis

    async def check_and_deduct(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
    ) -> int:
        """Enforce all checks and deduct credits for a generation request.

        Enforcement check order (Requirement 6.1):
        1. Get pricing configuration for the service/operation
        2. Check credit balance is sufficient
        3. Get user's active plan (skip daily/monthly if no plan)
        4. Check daily limit per channel
        5. Check monthly limit
        6. Atomic credit deduction
        7. Increment usage counters (DB + Redis cache)

        Args:
            user_id: The UUID of the user making the request.
            channel_profile_id: The UUID of the channel profile, or None.
            operation_type: The type of operation (e.g. "music_generation").
            ai_service: The AI service identifier (e.g. "suno").

        Returns:
            The number of credits deducted (credits_per_operation).

        Raises:
            ExternalServiceError: If no pricing is configured for the operation.
            InsufficientCreditsError: If credit balance is too low.
            QuotaExceededError: If daily or monthly quota is exceeded.
        """
        # Step 1: Get pricing
        pricing_entry = await self._pricing_repo.get_by_service_and_operation(
            ai_service, operation_type
        )
        if pricing_entry is None:
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}'. This operation is not yet available.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                },
            )
        credits_per_operation: int = pricing_entry["credits_per_operation"]

        # Step 2: Check credit balance
        current_balance = await self._credit_repo.get_balance(user_id)
        if current_balance < credits_per_operation:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": current_balance,
                },
            )

        # Step 3: Get user's active plan
        plan = await self._plan_repo.get_user_active_plan(user_id)

        today = date.today()

        # If no plan, skip daily/monthly checks (allow credit-only usage)
        if plan is not None:
            # Step 4: Check daily limit
            daily_limit = self._get_daily_limit(plan, operation_type)
            daily_count = await self._get_daily_count_cached(
                user_id, channel_profile_id, operation_type, today
            )
            if daily_count >= daily_limit:
                # Calculate reset time (next midnight UTC)
                reset_time = datetime(
                    today.year, today.month, today.day, tzinfo=timezone.utc
                ) + timedelta(days=1)

                raise QuotaExceededError(
                    "Daily generation quota exceeded.",
                    details={
                        "error_code": "DAILY_QUOTA_EXCEEDED",
                        "limit": daily_limit,
                        "current_usage": daily_count,
                        "reset_time": reset_time.isoformat(),
                        "operation_type": operation_type,
                    },
                )

            # Step 5: Check monthly limit
            monthly_limit = self._get_monthly_limit(plan, operation_type)
            if monthly_limit is not None:
                if monthly_limit == 0:
                    # Plan has limit set to 0 — operation type unavailable
                    raise QuotaExceededError(
                        "This operation type is not available on your current plan.",
                        details={
                            "error_code": "PLAN_LIMIT_ZERO",
                            "operation_type": operation_type,
                            "plan_name": plan.name,
                        },
                    )

                period_start = self._get_period_start(plan)
                monthly_count = await self._usage_repo.get_monthly_count(
                    user_id, operation_type, period_start
                )
                if monthly_count >= monthly_limit:
                    # Calculate period end
                    period_end_date = self._get_period_end(plan, period_start)
                    raise QuotaExceededError(
                        "Monthly generation quota exceeded.",
                        details={
                            "error_code": "MONTHLY_QUOTA_EXCEEDED",
                            "limit": monthly_limit,
                            "current_usage": monthly_count,
                            "period_end_date": period_end_date.isoformat(),
                            "operation_type": operation_type,
                        },
                    )

        # Step 6: Atomic credit deduction
        reason = f"{operation_type} via {ai_service}"
        deduction_success = await self._credit_repo.atomic_deduct(
            user_id, credits_per_operation, reason
        )
        if not deduction_success:
            # Race condition: balance dropped between check and deduction
            raise InsufficientCreditsError(
                "Insufficient credits for this operation (concurrent deduction).",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": 0,
                },
            )

        # Step 7: Increment usage counters
        period_start = self._get_period_start(plan) if plan else today.replace(day=1)
        await self._usage_repo.increment_usage(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            usage_date=today,
            period_start=period_start,
        )

        # Increment Redis daily cache
        cache_key = self._daily_cache_key(
            user_id, channel_profile_id, operation_type, today
        )
        await self._redis.incr(cache_key)
        await self._redis.expire(cache_key, DAILY_CACHE_TTL_SECONDS)

        logger.info(
            "Enforcement passed: user=%s, op=%s, service=%s, credits_deducted=%d",
            user_id,
            operation_type,
            ai_service,
            credits_per_operation,
        )
        return credits_per_operation

    # -----------------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_daily_limit(plan: Plan, operation_type: str) -> int:
        """Map operation_type to the plan's daily limit field.

        Mapping:
        - "music_generation" → plan.daily_song_limit_per_channel
        - "image_generation" / "channel_setup" → plan.daily_image_limit_per_channel
        - others → plan.daily_song_limit_per_channel (default)

        Args:
            plan: The user's active Plan.
            operation_type: The type of operation being performed.

        Returns:
            The daily limit for this operation type.
        """
        if operation_type in ("image_generation", "channel_setup"):
            return plan.daily_image_limit_per_channel
        # music_generation, text_generation, and others default to song limit
        return plan.daily_song_limit_per_channel

    @staticmethod
    def _get_monthly_limit(plan: Plan, operation_type: str) -> int | None:
        """Map operation_type to the plan's monthly limit field.

        Mapping:
        - "music_generation" → plan.monthly_song_limit
        - "image_generation" / "channel_setup" → plan.monthly_image_limit
        - "text_generation" → None (no monthly limit for text)
        - others → plan.monthly_song_limit (default)

        Returns None for unlimited (null monthly limits / Lifetime plans).

        Args:
            plan: The user's active Plan.
            operation_type: The type of operation being performed.

        Returns:
            The monthly limit, or None if unlimited.
        """
        if operation_type == "text_generation":
            return None
        if operation_type in ("image_generation", "channel_setup"):
            return plan.monthly_image_limit
        # music_generation and others default to song limit
        return plan.monthly_song_limit

    @staticmethod
    def _get_period_start(plan: Plan | None) -> date:
        """Compute billing period start from plan configuration.

        For simplicity, uses the first day of the current month.

        Args:
            plan: The user's active Plan (or None).

        Returns:
            The start date of the current billing period.
        """
        today = date.today()
        return today.replace(day=1)

    @staticmethod
    def _get_period_end(plan: Plan, period_start: date) -> date:
        """Compute the billing period end date.

        Uses billing_cycle_days if available, otherwise end of current month.

        Args:
            plan: The user's active Plan.
            period_start: The start date of the current billing period.

        Returns:
            The end date of the billing period.
        """
        if plan.billing_cycle_days is not None:
            return period_start + timedelta(days=plan.billing_cycle_days)
        # Lifetime plans or no cycle: use end of current month
        if period_start.month == 12:
            return period_start.replace(year=period_start.year + 1, month=1, day=1)
        return period_start.replace(month=period_start.month + 1, day=1)

    async def _get_daily_count_cached(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int:
        """Get daily usage count, checking Redis cache first.

        Falls back to the database if the cache key doesn't exist, and
        populates the cache on miss.

        Args:
            user_id: The UUID of the user.
            channel_profile_id: The UUID of the channel profile, or None.
            operation_type: The type of operation.
            usage_date: The date to check.

        Returns:
            The current daily usage count.
        """
        cache_key = self._daily_cache_key(
            user_id, channel_profile_id, operation_type, usage_date
        )

        # Try Redis first
        cached = await self._redis.get(cache_key)
        if cached is not None:
            return int(cached)

        # Cache miss — query database
        count = await self._usage_repo.get_daily_count(
            user_id, channel_profile_id, operation_type, usage_date
        )

        # Populate cache with TTL
        await self._redis.set(cache_key, str(count), ex=DAILY_CACHE_TTL_SECONDS)

        return count

    @staticmethod
    def _daily_cache_key(
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> str:
        """Build the Redis key for daily usage caching.

        Key pattern: daily_usage:{user_id}:{channel_profile_id or 'none'}:{operation_type}:{YYYY-MM-DD}

        Args:
            user_id: The UUID of the user.
            channel_profile_id: The UUID of the channel profile, or None.
            operation_type: The type of operation.
            usage_date: The date for the cache key.

        Returns:
            The Redis key string.
        """
        channel_part = str(channel_profile_id) if channel_profile_id else "none"
        date_str = usage_date.isoformat()
        return f"daily_usage:{user_id}:{channel_part}:{operation_type}:{date_str}"
