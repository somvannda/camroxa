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
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    LicenseExpiredError,
    QuotaExceededError,
)
from platform_api.models.domain import Plan
from platform_api.services.billing_mode_service import (
    counts_toward_draft_quota,
    counts_toward_image_quota,
    counts_toward_merge_quota,
    counts_toward_product_quota,
    counts_toward_video_quota,
    is_subscription_plan,
    quota_operation_type,
    subscription_covers_operation,
    usage_storage_type,
    uses_account_daily_quota,
    video_usage_counter_types,
)
from platform_api.services.billing_calendar import billing_today, next_billing_midnight
from platform_api.services import credit_progress_log as credit_log
from platform_api.services.billing_period_service import (
    ActiveSubscriptionContext,
    period_end_for_subscription,
    period_start_for_subscription,
)
from platform_api.services.subscription_entitlement_service import (
    effective_daily_limit_for_operation,
    effective_monthly_limit_for_operation,
    effective_profile_allowance,
)
from platform_api.services.credit_pricing_service import lookup_pricing_entry

logger = logging.getLogger(__name__)

# TTL for daily usage cache keys: 25 hours (ensures expiry after day rolls over)
DAILY_CACHE_TTL_SECONDS = 25 * 60 * 60
_ABSORB_BUDGET_PREFIX = "fail_absorb:"
_ABSORB_BUDGET_TTL_SECONDS = 25 * 60 * 60
# Admin Settings → Fail/Retry Absorb; overrides PLATFORM_DAILY_FAIL_ABSORB_BUDGET.
DAILY_FAIL_ABSORB_BUDGET_SETTING_KEY = "daily_fail_absorb_budget"


@dataclass(frozen=True)
class OperationHold:
    """Wallet hold state after reserve-before-provider (soft overage escrow)."""

    held_units: int
    plan_covered: bool


def _absorb_budget_key(user_id: UUID, usage_date: date | None = None) -> str:
    day = usage_date or billing_today()
    return f"{_ABSORB_BUDGET_PREFIX}{user_id}:{day.isoformat()}"


def _daily_fail_absorb_budget() -> int:
    """Env/default budget (used when no admin system_settings override)."""
    try:
        from platform_api.config import get_settings

        return max(0, int(get_settings().daily_fail_absorb_budget))
    except Exception:
        return 25


def _parse_fail_absorb_budget(raw: Any) -> int | None:
    """Parse a system_settings value into a non-negative budget, or None if unset/invalid."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return max(0, int(raw))
    text = str(raw).strip()
    if not text:
        return None
    try:
        return max(0, int(float(text)))
    except (TypeError, ValueError):
        return None


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
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Atomically deduct credits. Returns True on success, False if insufficient."""
        ...

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
        """Write a usage-ledger row (amount may be 0 for plan allowance)."""
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

    async def decrement_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        *,
        count: int = 1,
    ) -> None:
        """Reverse a prior usage increment."""
        ...

    async def try_increment_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        period_start: date,
        *,
        daily_limit: int,
        monthly_limit: int | None,
        allow_monthly_overage: bool,
        count: int = 1,
    ) -> bool:
        """Increment only when daily/monthly limits allow it."""
        ...


class PlanRepositoryProtocol(Protocol):
    """Protocol for plan repository operations needed by enforcement."""

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None:
        """Get the plan associated with the user's active license."""
        ...

    async def get_user_active_subscription_context(
        self, user_id: UUID
    ) -> ActiveSubscriptionContext | None:
        """Get active license + plan context for billing-period quota math."""
        ...

    async def sync_songs_used_for_period(
        self,
        user_id: UUID,
        license_id: UUID,
        period_start: date,
        period_end: date,
        songs_used: int,
    ) -> None:
        """Optional plan_usage sync for admin reporting (PlanRepository)."""
        ...


class CreditPricingRepositoryProtocol(Protocol):
    """Protocol for credit pricing repository operations needed by enforcement."""

    async def get_by_service_and_operation(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        """Return a pricing entry for an ai_service/operation/model combination."""
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
        license_repo: Any | None = None,
        daily_quota_bank_service: Any | None = None,
        quota_topup_service: Any | None = None,
        settings_repo: Any | None = None,
    ) -> None:
        """Build the enforcement service."""
        self._credit_repo = credit_repo
        self._usage_repo = usage_repo
        self._plan_repo = plan_repo
        self._pricing_repo = pricing_repo
        self._redis = redis
        self._license_repo = license_repo
        self._daily_quota_bank_service = daily_quota_bank_service
        self._quota_topup_service = quota_topup_service
        self._settings_repo = settings_repo

    async def resolve_daily_fail_absorb_budget(self) -> int:
        """Return per-user daily fail/retry absorb max (admin setting > env)."""
        repo = self._settings_repo
        if repo is not None:
            getter = getattr(repo, "get_system_setting", None)
            if getter is not None:
                try:
                    raw = await getter(DAILY_FAIL_ABSORB_BUDGET_SETTING_KEY)
                except Exception:
                    logger.debug(
                        "fail_absorb budget setting lookup failed; using env default",
                        exc_info=True,
                    )
                else:
                    parsed = _parse_fail_absorb_budget(raw)
                    if parsed is not None:
                        return parsed
        return _daily_fail_absorb_budget()

    async def check_and_deduct(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
        *,
        sub_model: str | None = None,
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
        pricing_entry = await lookup_pricing_entry(
            self._pricing_repo, ai_service, operation_type, sub_model
        )
        if pricing_entry is None and str(operation_type).strip().lower() == "video_manual":
            pricing_entry = await lookup_pricing_entry(
                self._pricing_repo, ai_service, "video", sub_model
            )
        if pricing_entry is None:
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}'. This operation is not yet available.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": sub_model,
                },
            )
        credits_per_operation: int = pricing_entry["credits_per_operation"]

        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        today = billing_today()
        period_start = self._period_start(ctx, today)
        wallet_daily_overage = False

        # Step 3–5: Daily/monthly plan quotas (all users with a plan)
        if plan is not None:
            await self._enforce_plan_quotas(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
                wallet_bypass_credits=credits_per_operation,
            )
            wallet_daily_overage = await self._is_wallet_daily_overage(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
            )

        # Subscription quota-first: no wallet charge while plan allowance remains
        if (
            plan is not None
            and not wallet_daily_overage
            and await subscription_covers_operation(
                plan=plan,
                user_id=user_id,
                operation_type=operation_type,
                usage_repo=self._usage_repo,
                period_start=period_start,
                addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0),
            )
        ):
            await self._increment_usage_counters(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                today=today,
                period_start=period_start,
                subscription_context=ctx,
            )
            await self._record_plan_allowance_ledger(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
                list_credit_units=credits_per_operation,
                sub_model=sub_model,
            )
            credit_log.log_subscription_quota(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
            )
            logger.debug(
                "Subscription quota consumed: user=%s, op=%s, service=%s",
                user_id,
                operation_type,
                ai_service,
            )
            return 0

        # Wallet billing (lifetime, overage, or users without subscription coverage)
        await self._enforce_wallet_subscription_gate(user_id)
        current_balance = await self._credit_repo.get_balance(user_id)
        if current_balance < credits_per_operation:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": current_balance,
                },
            )

        reason = f"{operation_type} via {ai_service}"
        usage_metadata = self._wallet_usage_metadata(
            operation_type=operation_type,
            ai_service=ai_service,
            sub_model=sub_model,
            list_credit_units=credits_per_operation,
            charged_credit_units=credits_per_operation,
            purpose=reason,
            wallet_daily_overage=wallet_daily_overage,
        )
        deduction_success = await self._credit_repo.atomic_deduct(
            user_id, credits_per_operation, reason, metadata=usage_metadata
        )
        if not deduction_success:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation (concurrent deduction).",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": 0,
                },
            )

        await self._increment_usage_counters(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            today=today,
            period_start=period_start,
            subscription_context=ctx,
        )

        logger.debug(
            "Enforcement passed: user=%s, op=%s, service=%s, credits_deducted=%d",
            user_id,
            operation_type,
            ai_service,
            credits_per_operation,
        )
        return credits_per_operation

    async def resolve_max_credits(
        self,
        operation_type: str,
        provider_models: list[tuple[str, str | None]],
    ) -> int:
        """Return the highest configured credit price across provider/model pairs."""
        max_price = 0
        missing: list[str] = []
        for ai_service, sub_model in provider_models:
            pricing_entry = await lookup_pricing_entry(
                self._pricing_repo, ai_service, operation_type, sub_model
            )
            if pricing_entry is None:
                label = f"{ai_service}:{sub_model or 'default'}"
                missing.append(label)
                continue
            max_price = max(max_price, int(pricing_entry["credits_per_operation"]))
        if max_price <= 0:
            raise ExternalServiceError(
                f"No pricing configured for operation '{operation_type}' "
                f"across providers: {', '.join(missing) or 'none'}.",
                details={
                    "operation_type": operation_type,
                    "provider_models": provider_models,
                },
            )
        return max_price

    async def preflight_quotas_and_balance(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        min_credits: int,
    ) -> None:
        """Check balance and quotas before generation without deducting credits."""
        await self.enforce_fail_absorb_budget(user_id)
        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        period_start = self._period_start(ctx, billing_today())
        wallet_daily_overage = False

        if plan is not None:
            await self._enforce_plan_quotas(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
                wallet_bypass_credits=min_credits,
            )
            wallet_daily_overage = await self._is_wallet_daily_overage(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
            )

        if (
            plan is not None
            and not wallet_daily_overage
            and await subscription_covers_operation(
                plan=plan,
                user_id=user_id,
                operation_type=operation_type,
                usage_repo=self._usage_repo,
                period_start=period_start,
                addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0),
            )
        ):
            return

        await self._enforce_wallet_subscription_gate(user_id)
        current_balance = await self._credit_repo.get_balance(user_id)
        if current_balance < min_credits:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": min_credits,
                    "current_balance": current_balance,
                },
            )

    async def enforce_fail_absorb_budget(self, user_id: UUID) -> None:
        """Block further AI work after too many platform-absorbed failures today (H2)."""
        budget = await self.resolve_daily_fail_absorb_budget()
        if budget <= 0:
            return
        used = await self.get_fail_absorb_count(user_id)
        if used >= budget:
            raise QuotaExceededError(
                "Daily fail/retry budget exceeded. Try again tomorrow.",
                details={
                    "error_code": "FAIL_BUDGET_EXCEEDED",
                    "fail_absorb_used": used,
                    "fail_absorb_budget": budget,
                },
            )

    async def get_fail_absorb_count(self, user_id: UUID) -> int:
        raw = await self._redis.get(_absorb_budget_key(user_id))
        if raw is None:
            return 0
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    async def reset_fail_absorb(self, user_id: UUID) -> int:
        """Clear today's fail-absorb counter; return previous used count."""
        key = _absorb_budget_key(user_id)
        previous = await self.get_fail_absorb_count(user_id)
        delete = getattr(self._redis, "delete", None)
        if delete is not None:
            await delete(key)
        else:
            await self._redis.set(key, "0", ex=1)
        return previous

    async def fail_absorb_status(
        self, user_id: UUID, *, used: int | None = None
    ) -> dict[str, Any]:
        """Build admin UI payload for today's fail/retry absorb counter."""
        budget = await self.resolve_daily_fail_absorb_budget()
        count = int(used) if used is not None else None
        # Caller may pass used after async fetch; None means unknown here.
        day = billing_today()
        key = _absorb_budget_key(user_id, day)
        if count is None:
            count = 0
        remaining = None if budget <= 0 else max(0, budget - count)
        blocked = bool(budget > 0 and count >= budget)
        return {
            "user_id": str(user_id),
            "usage_date": day.isoformat(),
            "fail_absorb_used": count,
            "fail_absorb_budget": budget,
            "remaining": remaining,
            "blocked": blocked,
            "redis_key": key,
        }

    async def record_fail_absorb(self, user_id: UUID) -> int:
        """Increment today's platform_absorb counter; return new count."""
        key = _absorb_budget_key(user_id)
        incr = getattr(self._redis, "incr", None)
        if incr is not None:
            count = int(await incr(key))
        else:
            count = (await self.get_fail_absorb_count(user_id)) + 1
            await self._redis.set(key, str(count), ex=_ABSORB_BUDGET_TTL_SECONDS)
            await self._maybe_alert_absorb(user_id, count)
            return count
        expire = getattr(self._redis, "expire", None)
        if expire is not None:
            await expire(key, _ABSORB_BUDGET_TTL_SECONDS)
        await self._maybe_alert_absorb(user_id, count)
        return count

    async def _maybe_alert_absorb(self, user_id: UUID, count: int) -> None:
        from platform_api.services.abuse_alert_service import maybe_note_absorb

        await maybe_note_absorb(
            user_id=str(user_id),
            count=count,
            budget=await self.resolve_daily_fail_absorb_budget(),
        )

    async def preflight_batch_cost(
        self,
        user_id: UUID,
        *,
        song_count: int,
        total_wallet_cost: int,
        image_jobs: int = 0,
        draft_ops: int | None = None,
        ok_profile_id: UUID | None = None,
        alt_profile_id: UUID | None = None,
    ) -> None:
        """Allow batch creation when subscription quota covers it or wallet is sufficient."""
        from platform_api.services.billing_mode_service import subscription_covers_batch

        await self.enforce_fail_absorb_budget(user_id)
        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        period_start = self._period_start(ctx, billing_today())

        estimated_drafts = (
            draft_ops if draft_ops is not None else max(0, song_count * 2 + 1)
        )
        profile_ids = self._unique_profile_ids(ok_profile_id, alt_profile_id)
        if plan is not None and profile_ids:
            await self._enforce_batch_daily_quotas(
                user_id=user_id,
                profile_ids=profile_ids,
                song_count=song_count,
                image_jobs=image_jobs,
                draft_ops=estimated_drafts,
                subscription_context=ctx,
            )

        if plan is not None and await subscription_covers_batch(
            plan=plan,
            user_id=user_id,
            song_count=song_count,
            usage_repo=self._usage_repo,
            period_start=period_start,
            image_jobs=image_jobs,
            draft_ops=estimated_drafts,
            addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0) if ctx else 0,
        ):
            credit_log.log_subscription_quota(
                user_id=user_id,
                operation_type="batch_generation",
                ai_service="batch",
            )
            return

        current_balance = await self._credit_repo.get_balance(user_id)
        if current_balance < total_wallet_cost:
            raise InsufficientCreditsError(
                f"Insufficient credits for batch of {song_count} songs.",
                details={
                    "required": total_wallet_cost,
                    "available": current_balance,
                    "song_count": song_count,
                },
            )

    async def record_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
    ) -> None:
        """Increment usage counters without charging wallet."""
        await self.reserve_operation_quota(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
        )

    async def reserve_operation_quota(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        count: int = 1,
    ) -> None:
        """Atomically reserve daily/monthly quota before generation starts."""
        await self.enforce_fail_absorb_budget(user_id)
        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        today = billing_today()
        period_start = self._period_start(ctx, today)

        # Lyric/title/album burn the draft pool — they do not
        # reserve or burn song counters (Suno ``music`` does).
        if not counts_toward_product_quota(operation_type):
            if plan is not None:
                await self._enforce_plan_quotas(
                    user_id=user_id,
                    channel_profile_id=channel_profile_id,
                    operation_type=operation_type,
                    subscription_context=ctx,
                    additional_count=count,
                )
            return

        quota_op = self._pool_operation_type(operation_type)

        if plan is None:
            await self._usage_repo.increment_usage(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=quota_op,
                usage_date=today,
                period_start=period_start,
            )
            return

        daily_limit, banked_units, daily_count_before = await self._resolve_daily_bank_state(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            plan=plan,
            today=today,
            addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0) if ctx else 0,
        )
        effective_daily = daily_limit + banked_units
        account_daily = uses_account_daily_quota(quota_op)
        bank_profile_id = None if account_daily else channel_profile_id
        addon_slots = int(getattr(ctx, "profile_addon_slots", 0) or 0) if ctx else 0
        monthly_limit = await self._monthly_limit_with_topup(
            user_id=user_id,
            plan=plan,
            addon_slots=addon_slots,
            quota_op=quota_op,
            period_start=period_start,
            subscription_context=ctx,
        )
        allow_monthly_overage = is_subscription_plan(plan)
        try_increment = getattr(self._usage_repo, "try_increment_usage", None)
        if try_increment is None:
            await self._enforce_plan_quotas(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
                additional_count=count,
            )
            await self._usage_repo.increment_usage(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=quota_op,
                usage_date=today,
                period_start=period_start,
            )
        else:
            reserved = await try_increment(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=quota_op,
                usage_date=today,
                period_start=period_start,
                daily_limit=effective_daily,
                monthly_limit=monthly_limit,
                allow_monthly_overage=allow_monthly_overage,
                count=count,
                account_daily=account_daily,
            )
            if not reserved:
                if (
                    allow_monthly_overage
                    and daily_count_before + count > effective_daily
                ):
                    await self._usage_repo.increment_usage(
                        user_id=user_id,
                        channel_profile_id=channel_profile_id,
                        operation_type=quota_op,
                        usage_date=today,
                        period_start=period_start,
                    )
                else:
                    raise QuotaExceededError(
                        "Generation quota exceeded.",
                        details={
                            "error_code": "QUOTA_EXCEEDED",
                            "operation_type": operation_type,
                        },
                    )
            elif self._daily_quota_bank_service is not None:
                await self._daily_quota_bank_service.consume_bank_for_usage(
                    user_id,
                    bank_profile_id,
                    quota_op,
                    daily_count_before=daily_count_before,
                    count=count,
                    daily_limit=daily_limit,
                )

        cache_key = self._daily_cache_key(
            user_id, channel_profile_id, quota_op, today
        )
        await self._redis.incr(cache_key)
        await self._redis.expire(cache_key, DAILY_CACHE_TTL_SECONDS)
        await self._sync_plan_usage_reporting(
            user_id=user_id,
            subscription_context=ctx,
            operation_type=quota_op,
            period_start=period_start,
        )

    async def attribute_secondary_daily_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID,
        operation_type: str,
        *,
        count: int = 1,
    ) -> None:
        """Attribute per-channel daily usage without burning monthly packages.

        Dual-channel batches bill Primary for the shared package/slots (monthly +
        daily) but deliver to Secondary as well. Preflight reserves Secondary
        daily capacity; this records that daily use so both channels show usage
        for songs and draft slots.
        """
        if count <= 0 or not counts_toward_product_quota(operation_type):
            return
        today = billing_today()
        ctx = await self._resolve_subscription_context(user_id)
        period_start = self._period_start(ctx, today)
        quota_op = self._pool_operation_type(operation_type)
        await self._usage_repo.increment_usage(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=quota_op,
            usage_date=today,
            period_start=period_start,
            count=count,
            include_monthly=False,
        )
        cache_key = self._daily_cache_key(
            user_id, channel_profile_id, quota_op, today
        )
        for _ in range(count):
            await self._redis.incr(cache_key)
        await self._redis.expire(cache_key, DAILY_CACHE_TTL_SECONDS)

    async def release_operation_quota(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        count: int = 1,
    ) -> None:
        """Release a prior quota reservation after a failed generation."""
        if not counts_toward_product_quota(operation_type):
            return
        today = billing_today()
        quota_op = self._pool_operation_type(operation_type)
        decrement = getattr(self._usage_repo, "decrement_usage", None)
        if decrement is None:
            return
        await decrement(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=quota_op,
            usage_date=today,
            count=count,
        )
        cache_key = self._daily_cache_key(
            user_id, channel_profile_id, quota_op, today
        )
        cached = await self._redis.get(cache_key)
        if cached is not None and int(cached) > 0:
            await self._redis.set(
                cache_key,
                max(0, int(cached) - count),
                ex=DAILY_CACHE_TTL_SECONDS,
            )
        ctx = await self._resolve_subscription_context(user_id)
        await self._sync_plan_usage_reporting(
            user_id=user_id,
            subscription_context=ctx,
            operation_type=quota_op,
            period_start=self._period_start(ctx, today),
        )


    _CHARGE_KEY_PREFIX = "gen_charge:"
    _CHARGE_TTL_SECONDS = 14 * 24 * 60 * 60

    async def stash_operation_charge(self, token: str, amount: int) -> None:
        """Remember wallet/plan charge so async failure paths can refund accurately."""
        key = f"{self._CHARGE_KEY_PREFIX}{token}"
        await self._redis.set(key, str(int(amount)), ex=self._CHARGE_TTL_SECONDS)

    async def pop_operation_charge(self, token: str) -> int | None:
        """Return and clear a previously stashed charge amount."""
        key = f"{self._CHARGE_KEY_PREFIX}{token}"
        raw = await self._redis.get(key)
        if raw is None:
            return None
        delete = getattr(self._redis, "delete", None)
        if delete is not None:
            await delete(key)
        else:
            await self._redis.set(key, "", ex=1)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    async def refund_failed_operation(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
        *,
        charged_credit_units: int = 0,
        sub_model: str | None = None,
        reason: str,
        ref_id: str | None = None,
        list_credit_units: int | None = None,
        prior_ledger_recorded: bool = True,
        count: int = 1,
        routed_provider: str | None = None,
        routed_model: str | None = None,
        executed_provider: str | None = None,
        executed_model: str | None = None,
    ) -> None:
        """Undo customer billing after a failed generation; keep COGS-visible ledger.

        - Releases song/image product quota when the op burns those counters.
        - Refunds any wallet debit (``charged_credit_units``).
        - Never deletes prior debit/plan_allowance rows (owner COGS stays visible).
        - Adds a failure ledger row: wallet refund, or amount=0 with
          ``billing=platform_absorb`` / ``outcome=failed`` so Usage/Finance
          still show provider cost when the customer is not charged.
        """
        if counts_toward_product_quota(operation_type):
            await self.release_operation_quota(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                count=count,
            )

        display_provider = str(executed_provider or ai_service or "").strip() or ai_service
        display_model = executed_model if executed_provider else sub_model
        resolved_list = list_credit_units
        if resolved_list is None:
            pricing_entry = await lookup_pricing_entry(
                self._pricing_repo, display_provider, operation_type, display_model
            )
            if pricing_entry is None and display_provider != ai_service:
                pricing_entry = await lookup_pricing_entry(
                    self._pricing_repo, ai_service, operation_type, sub_model
                )
            resolved_list = (
                int(pricing_entry["credits_per_operation"])
                if pricing_entry is not None
                else 0
            )

        coverage = (
            "image_allowance"
            if counts_toward_image_quota(operation_type)
            else "draft_allowance"
            if counts_toward_draft_quota(operation_type)
            else "video_allowance"
            if counts_toward_video_quota(operation_type)
            else "merge_allowance"
            if counts_toward_merge_quota(operation_type)
            else "song_package"
        )
        failure_metadata: dict[str, Any] = {
            "category": "generation",
            "operation": operation_type,
            "operation_type": operation_type,
            # Backward-compatible primary fields: prefer executed when known.
            "provider": display_provider,
            "model": display_model,
            "routed_provider": routed_provider or ai_service,
            "routed_model": routed_model if routed_model is not None else sub_model,
            "executed_provider": executed_provider,
            "executed_model": executed_model,
            "purpose": reason,
            "outcome": "failed",
            "failed": True,
            "platform_absorbed_cost": True,
            "list_credit_units": int(resolved_list or 0),
            "charged_credit_units": 0,
            "coverage": coverage,
        }

        if charged_credit_units > 0:
            failure_metadata["billing"] = "wallet"
            refund = getattr(self._credit_repo, "refund", None)
            if refund is not None:
                await refund(
                    user_id,
                    int(charged_credit_units),
                    reason,
                    ref_id=ref_id,
                    metadata=failure_metadata,
                )
            else:
                await self._record_failure_ledger(
                    user_id=user_id,
                    amount=int(charged_credit_units),
                    direction="refund",
                    reason=reason,
                    ref_id=ref_id,
                    metadata=failure_metadata,
                )
            credit_log.log_refunded(
                user_id=user_id,
                amount_units=int(charged_credit_units),
                reason=reason,
                ref_id=ref_id,
            )
            return

        failure_metadata["billing"] = "platform_absorb"
        try:
            await self.record_fail_absorb(user_id)
        except Exception:
            logger.warning(
                "Failed to increment fail absorb budget for user %s",
                user_id,
                exc_info=True,
            )
        if prior_ledger_recorded:
            # Prior plan_allowance/wallet debit already shows COGS; add a
            # zero-amount refund so failure + platform absorb are explicit.
            await self._record_failure_ledger(
                user_id=user_id,
                amount=0,
                direction="refund",
                reason=reason,
                ref_id=ref_id,
                metadata=failure_metadata,
            )
        else:
            # Reserve-then-generate paths (e.g. images) write ledger only after
            # success — on provider failure emit a COGS debit with absorb flag.
            await self._record_failure_ledger(
                user_id=user_id,
                amount=0,
                direction="debit",
                reason=reason,
                ref_id=ref_id,
                metadata=failure_metadata,
            )

    async def _record_failure_ledger(
        self,
        *,
        user_id: UUID,
        amount: int,
        direction: str,
        reason: str,
        ref_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        record = getattr(self._credit_repo, "record_ledger_entry", None)
        if record is None:
            return
        await record(
            user_id,
            amount,
            direction,
            reason,
            ref_id=ref_id,
            metadata=metadata,
        )

    async def deduct_wallet_for_operation(
        self,
        user_id: UUID,
        operation_type: str,
        ai_service: str,
        *,
        sub_model: str | None = None,
    ) -> int:
        """Charge wallet only — usage counters must already be reserved."""
        pricing_entry = await lookup_pricing_entry(
            self._pricing_repo, ai_service, operation_type, sub_model
        )
        if pricing_entry is None:
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": sub_model,
                },
            )
        credits_per_operation = int(pricing_entry["credits_per_operation"])
        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        period_start = self._period_start(ctx, billing_today())

        if plan is not None and await subscription_covers_operation(
            plan=plan,
            user_id=user_id,
            operation_type=operation_type,
            usage_repo=self._usage_repo,
            period_start=period_start,
            after_reservation=True,
            addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0),
        ):
            await self._record_plan_allowance_ledger(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
                list_credit_units=credits_per_operation,
                sub_model=sub_model,
            )
            credit_log.log_subscription_quota(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
            )
            return 0

        await self._enforce_wallet_subscription_gate(user_id)
        wallet_daily_overage = await self._is_wallet_daily_overage(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            subscription_context=ctx,
            additional_count=1,
        )
        current_balance = await self._credit_repo.get_balance(user_id)
        if current_balance < credits_per_operation:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": current_balance,
                },
            )

        reason = f"{operation_type} via {ai_service}"
        usage_metadata = self._wallet_usage_metadata(
            operation_type=operation_type,
            ai_service=ai_service,
            sub_model=sub_model,
            list_credit_units=credits_per_operation,
            charged_credit_units=credits_per_operation,
            purpose=reason,
            wallet_daily_overage=wallet_daily_overage,
        )
        deduction_success = await self._credit_repo.atomic_deduct(
            user_id, credits_per_operation, reason, metadata=usage_metadata
        )
        if not deduction_success:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation (concurrent deduction).",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": 0,
                },
            )
        return credits_per_operation

    async def reserve_and_hold_before_provider(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        hold_credit_units: int,
        ai_service: str,
        sub_model: str | None = None,
    ) -> OperationHold:
        """Reserve product quota and escrow wallet before calling the provider.

        Soft overage (past monthly meter) holds ``hold_credit_units`` atomically
        so an empty wallet cannot race after provider COGS (H1). Plan-covered
        ops hold 0 wallet and only reserve the meter.
        """
        await self.reserve_operation_quota(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
        )

        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        period_start = self._period_start(ctx, billing_today())

        if plan is not None and await subscription_covers_operation(
            plan=plan,
            user_id=user_id,
            operation_type=operation_type,
            usage_repo=self._usage_repo,
            period_start=period_start,
            after_reservation=True,
            addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0),
        ):
            return OperationHold(held_units=0, plan_covered=True)

        hold_units = max(0, int(hold_credit_units or 0))
        if hold_units <= 0:
            return OperationHold(held_units=0, plan_covered=False)

        reason = f"{operation_type} via {ai_service}"
        usage_metadata = self._wallet_usage_metadata(
            operation_type=operation_type,
            ai_service=ai_service,
            sub_model=sub_model,
            list_credit_units=hold_units,
            charged_credit_units=hold_units,
            purpose=reason,
        )
        usage_metadata["hold"] = True
        deduction_success = await self._credit_repo.atomic_deduct(
            user_id, hold_units, reason, metadata=usage_metadata
        )
        if not deduction_success:
            await self.release_operation_quota(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
            )
            current_balance = await self._credit_repo.get_balance(user_id)
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": hold_units,
                    "current_balance": current_balance,
                },
            )
        return OperationHold(held_units=hold_units, plan_covered=False)

    async def finalize_held_operation(
        self,
        user_id: UUID,
        operation_type: str,
        ai_service: str,
        *,
        sub_model: str | None = None,
        hold: OperationHold,
        routed_provider: str | None = None,
        routed_model: str | None = None,
        executed_provider: str | None = None,
        executed_model: str | None = None,
    ) -> int:
        """After a successful provider call: write plan ledger or settle wallet hold."""
        pricing_entry = await lookup_pricing_entry(
            self._pricing_repo, ai_service, operation_type, sub_model
        )
        if pricing_entry is None:
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": sub_model,
                },
            )
        actual_units = int(pricing_entry["credits_per_operation"])
        route_kwargs = {
            "routed_provider": routed_provider or ai_service,
            "routed_model": routed_model if routed_model is not None else sub_model,
            "executed_provider": executed_provider or ai_service,
            "executed_model": executed_model if executed_model is not None else sub_model,
        }

        if hold.plan_covered:
            await self._record_plan_allowance_ledger(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
                list_credit_units=actual_units,
                sub_model=sub_model,
                **route_kwargs,
            )
            credit_log.log_subscription_quota(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
            )
            return 0

        held = int(hold.held_units or 0)
        if held > actual_units:
            settle_meta = self._wallet_usage_metadata(
                operation_type=operation_type,
                ai_service=ai_service,
                sub_model=sub_model,
                list_credit_units=actual_units,
                charged_credit_units=actual_units,
                purpose=f"{operation_type}_hold_settle",
                **route_kwargs,
            )
            settle_meta["hold_settle"] = True
            refund = getattr(self._credit_repo, "refund", None)
            if refund is not None:
                await refund(
                    user_id,
                    held - actual_units,
                    f"{operation_type}_hold_settle",
                    metadata=settle_meta,
                )
            return actual_units

        if held < actual_units:
            delta = actual_units - held
            reason = f"{operation_type} via {ai_service}"
            usage_metadata = self._wallet_usage_metadata(
                operation_type=operation_type,
                ai_service=ai_service,
                sub_model=sub_model,
                list_credit_units=actual_units,
                charged_credit_units=actual_units,
                purpose=reason,
                **route_kwargs,
            )
            ok = await self._credit_repo.atomic_deduct(
                user_id, delta, reason, metadata=usage_metadata
            )
            if not ok:
                raise InsufficientCreditsError(
                    "Insufficient credits to settle operation hold.",
                    details={
                        "required_credits": actual_units,
                        "held_credits": held,
                    },
                )
            return actual_units

        return held

    async def deduct_for_operation(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
        *,
        sub_model: str | None = None,
    ) -> int:
        """Deduct credits and increment usage for the provider that actually served the request."""
        pricing_entry = await lookup_pricing_entry(
            self._pricing_repo, ai_service, operation_type, sub_model
        )
        if pricing_entry is None:
            raise ExternalServiceError(
                f"No pricing configured for ai_service '{ai_service}' "
                f"operation '{operation_type}'.",
                details={
                    "ai_service": ai_service,
                    "operation_type": operation_type,
                    "sub_model": sub_model,
                },
            )
        credits_per_operation = int(pricing_entry["credits_per_operation"])
        ctx = await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        today = billing_today()
        period_start = self._period_start(ctx, today)
        wallet_daily_overage = False

        if plan is not None:
            await self._enforce_plan_quotas(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
                wallet_bypass_credits=credits_per_operation,
            )
            wallet_daily_overage = await self._is_wallet_daily_overage(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                subscription_context=ctx,
            )

        if (
            plan is not None
            and not wallet_daily_overage
            and await subscription_covers_operation(
                plan=plan,
                user_id=user_id,
                operation_type=operation_type,
                usage_repo=self._usage_repo,
                period_start=period_start,
                addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0),
            )
        ):
            await self._increment_usage_counters(
                user_id=user_id,
                channel_profile_id=channel_profile_id,
                operation_type=operation_type,
                today=today,
                period_start=period_start,
                subscription_context=ctx,
            )
            await self._record_plan_allowance_ledger(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
                list_credit_units=credits_per_operation,
                sub_model=sub_model,
            )
            credit_log.log_subscription_quota(
                user_id=user_id,
                operation_type=operation_type,
                ai_service=ai_service,
            )
            return 0

        await self._enforce_wallet_subscription_gate(user_id)
        current_balance = await self._credit_repo.get_balance(user_id)
        if current_balance < credits_per_operation:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": current_balance,
                },
            )

        reason = f"{operation_type} via {ai_service}"
        usage_metadata = self._wallet_usage_metadata(
            operation_type=operation_type,
            ai_service=ai_service,
            sub_model=sub_model,
            list_credit_units=credits_per_operation,
            charged_credit_units=credits_per_operation,
            purpose=reason,
            wallet_daily_overage=wallet_daily_overage,
        )
        deduction_success = await self._credit_repo.atomic_deduct(
            user_id, credits_per_operation, reason, metadata=usage_metadata
        )
        if not deduction_success:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation (concurrent deduction).",
                details={
                    "required_credits": credits_per_operation,
                    "current_balance": 0,
                },
            )

        await self._increment_usage_counters(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            today=today,
            period_start=period_start,
            subscription_context=ctx,
        )

        logger.debug(
            "Credits deducted after generation: user=%s, op=%s, service=%s, credits=%d",
            user_id,
            operation_type,
            ai_service,
            credits_per_operation,
        )
        return credits_per_operation

    async def _increment_usage_counters(
        self,
        *,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        today: date,
        period_start: date,
        subscription_context: ActiveSubscriptionContext | None = None,
    ) -> None:
        # Draft / song / image meters each +1 via counts_toward_product_quota.
        if not counts_toward_product_quota(operation_type):
            return

        quota_op = self._pool_operation_type(operation_type)
        await self._usage_repo.increment_usage(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=quota_op,
            usage_date=today,
            period_start=period_start,
        )
        cache_key = self._daily_cache_key(
            user_id, channel_profile_id, quota_op, today
        )
        await self._redis.incr(cache_key)
        await self._redis.expire(cache_key, DAILY_CACHE_TTL_SECONDS)
        await self._sync_plan_usage_reporting(
            user_id=user_id,
            subscription_context=subscription_context,
            operation_type=quota_op,
            period_start=period_start,
        )

    async def _record_plan_allowance_ledger(
        self,
        *,
        user_id: UUID,
        operation_type: str,
        ai_service: str,
        list_credit_units: int,
        sub_model: str | None = None,
        ref_id: str | None = None,
        routed_provider: str | None = None,
        routed_model: str | None = None,
        executed_provider: str | None = None,
        executed_model: str | None = None,
    ) -> None:
        """Always write amount=0 debit for plan-covered billable ops."""
        record = getattr(self._credit_repo, "record_ledger_entry", None)
        if record is None:
            return
        reason = f"{operation_type} via {ai_service}"
        if counts_toward_image_quota(operation_type):
            coverage = "image_allowance"
        elif counts_toward_draft_quota(operation_type):
            coverage = "draft_allowance"
        elif counts_toward_video_quota(operation_type):
            coverage = "video_allowance"
        elif counts_toward_merge_quota(operation_type):
            coverage = "merge_allowance"
        else:
            coverage = "song_package"
        metadata = {
            "category": "generation",
            "operation": operation_type,
            "operation_type": operation_type,
            "provider": ai_service,
            "model": sub_model,
            "routed_provider": routed_provider or ai_service,
            "routed_model": routed_model if routed_model is not None else sub_model,
            "executed_provider": executed_provider or ai_service,
            "executed_model": executed_model if executed_model is not None else sub_model,
            "purpose": reason,
            "billing": "plan_allowance",
            "list_credit_units": list_credit_units,
            "charged_credit_units": 0,
            "coverage": coverage,
        }
        await record(
            user_id,
            0,
            "debit",
            reason,
            ref_id=ref_id,
            metadata=metadata,
        )

    @staticmethod
    def _wallet_usage_metadata(
        *,
        operation_type: str,
        ai_service: str,
        sub_model: str | None,
        list_credit_units: int,
        charged_credit_units: int,
        purpose: str,
        wallet_daily_overage: bool = False,
        routed_provider: str | None = None,
        routed_model: str | None = None,
        executed_provider: str | None = None,
        executed_model: str | None = None,
    ) -> dict[str, Any]:
        if counts_toward_image_quota(operation_type):
            coverage = "image_allowance"
        elif counts_toward_draft_quota(operation_type):
            coverage = "draft_allowance"
        elif counts_toward_video_quota(operation_type):
            coverage = "video_allowance"
        elif counts_toward_merge_quota(operation_type):
            coverage = "merge_allowance"
        else:
            coverage = "song_package"
        metadata = {
            "category": "generation",
            "operation": operation_type,
            "operation_type": operation_type,
            "provider": ai_service,
            "model": sub_model,
            "routed_provider": routed_provider or ai_service,
            "routed_model": routed_model if routed_model is not None else sub_model,
            "executed_provider": executed_provider or ai_service,
            "executed_model": executed_model if executed_model is not None else sub_model,
            "purpose": purpose,
            "billing": "wallet",
            "list_credit_units": list_credit_units,
            "charged_credit_units": charged_credit_units,
            "coverage": coverage,
        }
        if wallet_daily_overage:
            metadata["wallet_daily_overage"] = True
        return metadata

    @staticmethod
    def _pool_operation_type(operation_type: str) -> str:
        """Counter key for product pools (lyric/title/album → draft; video_manual stays split)."""
        return usage_storage_type(operation_type)

    async def _sum_usage_counters(
        self,
        *,
        user_id: UUID,
        counter_types: tuple[str, ...],
        period_start: date | None = None,
        usage_date: date | None = None,
        account_daily: bool = False,
        channel_profile_id: UUID | None = None,
    ) -> int:
        total = 0
        for counter in counter_types:
            if usage_date is not None:
                if account_daily:
                    getter = getattr(self._usage_repo, "get_account_daily_count", None)
                    if getter is not None:
                        total += int(await getter(user_id, counter, usage_date) or 0)
                    else:
                        total += await self._get_daily_count_cached(
                            user_id, channel_profile_id, counter, usage_date
                        )
                else:
                    total += await self._get_daily_count_cached(
                        user_id, channel_profile_id, counter, usage_date
                    )
            elif period_start is not None:
                total += int(
                    await self._usage_repo.get_monthly_count(user_id, counter, period_start) or 0
                )
        return total

    async def _sync_plan_usage_reporting(
        self,
        *,
        user_id: UUID,
        subscription_context: ActiveSubscriptionContext | None,
        operation_type: str,
        period_start: date,
    ) -> None:
        if subscription_context is None:
            return
        if quota_operation_type(operation_type) != "music":
            return
        sync = getattr(self._plan_repo, "sync_songs_used_for_period", None)
        if sync is None:
            return
        license_id = subscription_context.license_id
        if license_id is None or license_id.int == 0:
            return
        songs_used = await self._usage_repo.get_monthly_count(
            user_id, "music", period_start
        )
        period_end = period_end_for_subscription(
            plan=subscription_context.plan,
            period_start=period_start,
        )
        await sync(
            user_id=user_id,
            license_id=license_id,
            period_start=period_start,
            period_end=period_end,
            songs_used=songs_used,
        )

    async def _enforce_wallet_subscription_gate(self, user_id: UUID) -> None:
        """Block wallet spend for expired monthly/yearly subscribers."""
        repo = self._license_repo
        if repo is None:
            return
        requires = getattr(repo, "requires_active_license_for_wallet", None)
        if requires is None:
            return
        if not await requires(user_id):
            return
        has_active = getattr(repo, "has_active_license", None)
        if has_active is None:
            return
        if not await has_active(str(user_id)):
            raise LicenseExpiredError()

    async def _resolve_daily_bank_state(
        self,
        *,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        plan: Plan,
        today: date,
        addon_slots: int = 0,
    ) -> tuple[int, int, int]:
        """Return (daily_limit, banked_units, daily_count) after accrual."""
        storage_op = self._pool_operation_type(operation_type)
        quota_op = quota_operation_type(operation_type)
        daily_limit = self._get_daily_limit(plan, quota_op, addon_slots=addon_slots)
        account_daily = uses_account_daily_quota(quota_op)
        bank_profile_id = None if account_daily else channel_profile_id

        banked_units = 0
        bank_service = self._daily_quota_bank_service
        if bank_service is not None and daily_limit > 0:
            banked_units = await bank_service.accrue_and_get_banked_units(
                user_id,
                bank_profile_id,
                quota_op,
                daily_limit=daily_limit,
                usage_date=today,
                account_daily=account_daily,
            )

        if account_daily:
            if counts_toward_video_quota(operation_type):
                daily_count = await self._sum_usage_counters(
                    user_id=user_id,
                    counter_types=video_usage_counter_types(),
                    usage_date=today,
                    account_daily=True,
                    channel_profile_id=channel_profile_id,
                )
            else:
                getter = getattr(self._usage_repo, "get_account_daily_count", None)
                if getter is not None:
                    daily_count = await getter(user_id, quota_op, today)
                else:
                    daily_count = await self._get_daily_count_cached(
                        user_id, channel_profile_id, quota_op, today
                    )
        else:
            daily_count = await self._get_daily_count_cached(
                user_id, channel_profile_id, storage_op, today
            )
        return daily_limit, banked_units, daily_count

    async def _can_wallet_daily_bypass(
        self,
        *,
        user_id: UUID,
        plan: Plan,
        subscription_context: ActiveSubscriptionContext | None,
        wallet_bypass_credits: int | None,
    ) -> bool:
        if wallet_bypass_credits is None or wallet_bypass_credits <= 0:
            return False
        if subscription_context is None or not is_subscription_plan(plan):
            return False
        balance = await self._credit_repo.get_balance(user_id)
        return balance >= wallet_bypass_credits

    async def _is_wallet_daily_overage(
        self,
        *,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        subscription_context: ActiveSubscriptionContext | None,
        additional_count: int = 1,
    ) -> bool:
        ctx = subscription_context
        plan = ctx.plan if ctx else None
        if plan is None or not is_subscription_plan(plan):
            return False
        today = billing_today()
        daily_limit, banked_units, daily_count = await self._resolve_daily_bank_state(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            plan=plan,
            today=today,
            addon_slots=int(getattr(subscription_context, "profile_addon_slots", 0) or 0)
            if subscription_context
            else 0,
        )
        effective_daily = daily_limit + banked_units
        return daily_count + max(1, additional_count) > effective_daily

    async def _enforce_plan_quotas(
        self,
        *,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        subscription_context: ActiveSubscriptionContext | None = None,
        additional_count: int = 1,
        wallet_bypass_credits: int | None = None,
    ) -> None:
        ctx = subscription_context or await self._resolve_subscription_context(user_id)
        plan = ctx.plan if ctx else None
        if plan is None:
            return

        quota_op = self._pool_operation_type(operation_type)
        today = billing_today()
        daily_limit, banked_units, daily_count = await self._resolve_daily_bank_state(
            user_id=user_id,
            channel_profile_id=channel_profile_id,
            operation_type=operation_type,
            plan=plan,
            today=today,
            addon_slots=int(getattr(ctx, "profile_addon_slots", 0) or 0),
        )
        effective_daily = daily_limit + banked_units
        requested = max(1, additional_count)
        if daily_count + requested > effective_daily:
            if await self._can_wallet_daily_bypass(
                user_id=user_id,
                plan=plan,
                subscription_context=ctx,
                wallet_bypass_credits=wallet_bypass_credits,
            ):
                return
            reset_time = next_billing_midnight(from_date=today)
            raise QuotaExceededError(
                "Daily generation quota exceeded.",
                details={
                    "error_code": "DAILY_QUOTA_EXCEEDED",
                    "limit": daily_limit,
                    "banked_units": banked_units,
                    "effective_daily_limit": effective_daily,
                    "current_usage": daily_count,
                    "requested": additional_count,
                    "reset_time": reset_time.isoformat(),
                    "operation_type": operation_type,
                },
            )

        addon_slots = int(getattr(ctx, "profile_addon_slots", 0) or 0) if ctx else 0
        period_start = self._period_start(ctx, today)
        monthly_limit = await self._monthly_limit_with_topup(
            user_id=user_id,
            plan=plan,
            addon_slots=addon_slots,
            quota_op=quota_op,
            period_start=period_start,
            subscription_context=ctx,
        )
        if monthly_limit is not None:
            if monthly_limit == 0:
                raise QuotaExceededError(
                    "This operation type is not available on your current plan.",
                    details={
                        "error_code": "PLAN_LIMIT_ZERO",
                        "operation_type": operation_type,
                        "plan_name": plan.name,
                    },
                )
            if counts_toward_video_quota(operation_type):
                monthly_count = await self._sum_usage_counters(
                    user_id=user_id,
                    counter_types=video_usage_counter_types(),
                    period_start=period_start,
                )
            else:
                monthly_count = await self._usage_repo.get_monthly_count(
                    user_id, quota_op, period_start
                )
            if quota_op == "background_image":
                monthly_count += await self._usage_repo.get_monthly_count(
                    user_id, "thumbnail_image", period_start
                )
            if monthly_count + max(1, additional_count) > monthly_limit:
                # Subscription plans allow wallet overage once included quota is consumed.
                if is_subscription_plan(plan):
                    return
                period_end_date = period_end_for_subscription(
                    plan=plan,
                    period_start=period_start,
                )
                raise QuotaExceededError(
                    "Monthly generation quota exceeded.",
                    details={
                        "error_code": "MONTHLY_QUOTA_EXCEEDED",
                        "limit": monthly_limit,
                        "current_usage": monthly_count,
                        "requested": additional_count,
                        "period_end_date": period_end_date.isoformat(),
                        "operation_type": operation_type,
                    },
                )

    async def _enforce_batch_daily_quotas(
        self,
        *,
        user_id: UUID,
        profile_ids: list[UUID],
        song_count: int,
        image_jobs: int,
        subscription_context: ActiveSubscriptionContext | None,
        draft_ops: int = 0,
    ) -> None:
        # Drafts and songs: reserve the same daily amount on every channel in the
        # batch (Primary + Secondary). Monthly package burn stays Primary-only
        # at deduct time; Secondary daily is attributed separately.
        if draft_ops > 0:
            for profile_id in profile_ids:
                await self._enforce_plan_quotas(
                    user_id=user_id,
                    channel_profile_id=profile_id,
                    operation_type="draft",
                    subscription_context=subscription_context,
                    additional_count=draft_ops,
                )

        if song_count > 0:
            for profile_id in profile_ids:
                await self._enforce_plan_quotas(
                    user_id=user_id,
                    channel_profile_id=profile_id,
                    operation_type="music",
                    subscription_context=subscription_context,
                    additional_count=song_count,
                )

        if image_jobs <= 0 or not profile_ids:
            return

        per_profile = image_jobs // len(profile_ids)
        remainder = image_jobs % len(profile_ids)
        for index, profile_id in enumerate(profile_ids):
            profile_image_jobs = per_profile + (1 if index < remainder else 0)
            if profile_image_jobs <= 0:
                continue
            await self._enforce_plan_quotas(
                user_id=user_id,
                channel_profile_id=profile_id,
                operation_type="background_image",
                subscription_context=subscription_context,
                additional_count=profile_image_jobs,
            )

    @staticmethod
    def _unique_profile_ids(
        ok_profile_id: UUID | None,
        alt_profile_id: UUID | None,
    ) -> list[UUID]:
        profile_ids: list[UUID] = []
        seen: set[UUID] = set()
        for profile_id in (ok_profile_id, alt_profile_id):
            if profile_id is None or profile_id in seen:
                continue
            seen.add(profile_id)
            profile_ids.append(profile_id)
        return profile_ids

    # -----------------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_daily_limit(plan: Plan, operation_type: str, addon_slots: int = 0) -> int:
        """Map operation_type to the plan's daily limit field.

        Account-wide video/merge limits scale with active profile add-on slots.
        Per-channel song/image/draft limits are unchanged (capacity grows via channels).
        """
        return effective_daily_limit_for_operation(plan, addon_slots, operation_type)

    async def _monthly_limit_with_topup(
        self,
        *,
        user_id: UUID,
        plan: Plan,
        addon_slots: int,
        quota_op: str,
        period_start: date,
        subscription_context: ActiveSubscriptionContext | None,
    ) -> int | None:
        """Plan monthly limit plus any admin period top-up for this billing period."""
        del subscription_context
        if self._quota_topup_service is not None:
            return await self._quota_topup_service.effective_monthly_limit_with_topup(
                user_id=user_id,
                plan=plan,
                addon_slots=addon_slots,
                operation_type=quota_op,
                period_start=period_start,
            )
        return effective_monthly_limit_for_operation(plan, addon_slots, quota_op)

    @staticmethod
    def _get_monthly_limit(plan: Plan, operation_type: str) -> int | None:
        """Map operation_type to the plan's monthly limit field."""
        if operation_type in ("text_generation",):
            return None
        if operation_type in (
            "image_generation",
            "background_image",
            "thumbnail_image",
            "channel_setup",
        ):
            return plan.monthly_image_limit
        if operation_type in ("draft", "lyric", "title", "album", "lyrics"):
            return getattr(plan, "monthly_draft_limit", None)
        if operation_type in ("video", "video_generation", "video_export", "video_manual"):
            return getattr(plan, "monthly_video_limit", None)
        if operation_type in ("video_merge", "merge", "auto_merge"):
            return getattr(plan, "monthly_merge_limit", None)
        return plan.monthly_song_limit

    async def _resolve_subscription_context(
        self, user_id: UUID
    ) -> ActiveSubscriptionContext | None:
        getter = getattr(self._plan_repo, "get_user_active_subscription_context", None)
        if getter is not None:
            ctx = await getter(user_id)
            if ctx is not None:
                return ctx

        plan = await self._plan_repo.get_user_active_plan(user_id)
        if plan is None:
            return None
        return ActiveSubscriptionContext(
            plan=plan,
            license_id=UUID(int=0),
            activated_at=None,
        )

    @staticmethod
    def _period_start(
        ctx: ActiveSubscriptionContext | None,
        reference_date: date,
    ) -> date:
        if ctx is None:
            return reference_date.replace(day=1)
        return period_start_for_subscription(
            plan=ctx.plan,
            activated_at=ctx.activated_at,
            reference_date=reference_date,
        )

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
