"""Unit tests for UsageEnforcementService.

Tests the enforcement check ordering, daily/monthly limits, credit deduction,
Redis caching, and edge cases (no plan, plan-limit-zero, race conditions).

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 1.5
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    QuotaExceededError,
)
from platform_api.services.billing_calendar import billing_today
from platform_api.models.domain import Plan
from platform_api.services.usage_enforcement_service import (
    DAILY_CACHE_TTL_SECONDS,
    UsageEnforcementService,
)


# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


class FakeCreditRepo:
    """In-memory fake for CreditRepositoryProtocol."""

    def __init__(self, balance: int = 1000) -> None:
        self._balances: dict[UUID | str, int] = {}
        self._default_balance = balance
        self.deduct_calls: list[tuple[UUID, int, str]] = []
        self.refund_calls: list[dict[str, Any]] = []
        self.ledger_calls: list[dict[str, Any]] = []
        self.deduct_should_fail: bool = False

    def set_balance(self, user_id: UUID, balance: int) -> None:
        self._balances[user_id] = balance

    async def get_balance(self, user_id: UUID | str) -> int:
        return self._balances.get(user_id, self._default_balance)

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        **kwargs: Any,
    ) -> bool:
        self.deduct_calls.append((user_id, amount, reason))
        if self.deduct_should_fail:
            return False
        balance = self._balances.get(user_id, self._default_balance)
        if balance < amount:
            return False
        self._balances[user_id] = balance - amount
        return True

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        self.refund_calls.append(
            {
                "user_id": user_id,
                "amount": amount,
                "reason": reason,
                "ref_id": ref_id,
                "metadata": metadata,
            }
        )
        balance = self._balances.get(user_id, self._default_balance)
        self._balances[user_id] = balance + amount
        self.ledger_calls.append(
            {
                "user_id": user_id,
                "amount": amount,
                "direction": "refund",
                "reason": reason,
                "ref_id": ref_id,
                "metadata": metadata,
            }
        )
        return self._balances[user_id]

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
        self.ledger_calls.append(
            {
                "user_id": user_id,
                "amount": amount,
                "direction": direction,
                "reason": reason,
                "ref_id": ref_id,
                "metadata": metadata,
            }
        )
        return uuid4()


class FakeUsageRepo:
    """In-memory fake for UsageTrackingRepositoryProtocol."""

    def __init__(self) -> None:
        self._daily: dict[tuple[UUID, UUID | None, str, date], int] = {}
        self._monthly: dict[tuple[UUID, str, date], int] = {}
        self.increment_calls: list[dict[str, Any]] = []
        self.decrement_calls: list[dict[str, Any]] = []

    def set_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        count: int,
    ) -> None:
        self._daily[(user_id, channel_profile_id, operation_type, usage_date)] = count

    def set_monthly_count(
        self, user_id: UUID, operation_type: str, period_start: date, count: int
    ) -> None:
        self._monthly[(user_id, operation_type, period_start)] = count

    async def get_daily_count(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
    ) -> int:
        return self._daily.get(
            (user_id, channel_profile_id, operation_type, usage_date), 0
        )

    async def get_monthly_count(
        self, user_id: UUID, operation_type: str, period_start: date
    ) -> int:
        return self._monthly.get((user_id, operation_type, period_start), 0)

    async def increment_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        period_start: date,
        *,
        count: int = 1,
        include_monthly: bool = True,
    ) -> None:
        self.increment_calls.append(
            {
                "user_id": user_id,
                "channel_profile_id": channel_profile_id,
                "operation_type": operation_type,
                "usage_date": usage_date,
                "period_start": period_start,
                "count": count,
                "include_monthly": include_monthly,
            }
        )
        key_d = (user_id, channel_profile_id, operation_type, usage_date)
        self._daily[key_d] = self._daily.get(key_d, 0) + count
        if include_monthly:
            key_m = (user_id, operation_type, period_start)
            self._monthly[key_m] = self._monthly.get(key_m, 0) + count

    async def decrement_usage(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        usage_date: date,
        *,
        count: int = 1,
    ) -> None:
        self.decrement_calls.append(
            {
                "user_id": user_id,
                "channel_profile_id": channel_profile_id,
                "operation_type": operation_type,
                "usage_date": usage_date,
                "count": count,
            }
        )
        key_d = (user_id, channel_profile_id, operation_type, usage_date)
        self._daily[key_d] = max(0, self._daily.get(key_d, 0) - count)
        # Approximate monthly reverse using today's year-month start if known.
        for key_m in list(self._monthly.keys()):
            if key_m[0] == user_id and key_m[1] == operation_type:
                self._monthly[key_m] = max(0, self._monthly[key_m] - count)
                break


class FakePlanRepo:
    """In-memory fake for PlanRepositoryProtocol."""

    def __init__(
        self,
        plan: Plan | None = None,
        *,
        activated_at: datetime | None = None,
    ) -> None:
        self._plans: dict[UUID, Plan | None] = {}
        self._default_plan = plan
        self._activation: dict[UUID, datetime | None] = {}
        self._default_activation = activated_at

    def set_plan(
        self,
        user_id: UUID,
        plan: Plan | None,
        *,
        activated_at: datetime | None = None,
    ) -> None:
        self._plans[user_id] = plan
        if activated_at is not None:
            self._activation[user_id] = activated_at

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None:
        if user_id in self._plans:
            return self._plans[user_id]
        return self._default_plan

    async def get_user_active_subscription_context(self, user_id: UUID):
        from platform_api.services.billing_period_service import ActiveSubscriptionContext

        plan = await self.get_user_active_plan(user_id)
        if plan is None:
            return None
        activated_at = self._activation.get(user_id, self._default_activation)
        return ActiveSubscriptionContext(
            plan=plan,
            license_id=uuid4(),
            activated_at=activated_at,
        )


class FakePricingRepo:
    """In-memory fake for CreditPricingRepositoryProtocol."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], dict[str, Any]] = {}

    def seed(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        *,
        sub_model: str = "",
    ) -> None:
        self._entries[(ai_service, operation_type, sub_model)] = {
            "ai_service": ai_service,
            "operation_type": operation_type,
            "sub_model": sub_model,
            "credits_per_operation": credits_per_operation,
        }

    async def get_by_service_and_operation(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        return self._entries.get((ai_service, operation_type, sub_model))


class FakeRedis:
    """In-memory fake for RedisProtocol."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0"))
        new_val = current + 1
        self._store[key] = str(new_val)
        return new_val

    async def expire(self, key: str, seconds: int) -> bool:
        self._ttls[key] = seconds
        return True

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool | None:
        self._store[key] = str(value)
        if ex is not None:
            self._ttls[key] = ex
        return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_plan(
    daily_song: int = 7,
    daily_image: int = 7,
    daily_draft: int = 300,
    monthly_song: int | None = 300,
    monthly_image: int | None = 60,
    monthly_draft: int | None = 900,
    billing_cycle_days: int | None = 30,
    name: str = "monthly",
) -> Plan:
    return Plan(
        id=uuid4(),
        name=name,
        price_cents=7900,
        billing_cycle_days=billing_cycle_days,
        profile_allowance=2,
        monthly_song_limit=monthly_song,
        monthly_image_limit=monthly_image,
        monthly_draft_limit=monthly_draft,
        daily_song_limit_per_channel=daily_song,
        daily_image_limit_per_channel=daily_image,
        daily_draft_limit_per_channel=daily_draft,
        is_active=True,
        effective_from=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def credit_repo() -> FakeCreditRepo:
    return FakeCreditRepo(balance=1000)


@pytest.fixture
def usage_repo() -> FakeUsageRepo:
    return FakeUsageRepo()


@pytest.fixture
def plan_repo() -> FakePlanRepo:
    return FakePlanRepo(plan=_make_plan())


@pytest.fixture
def pricing_repo() -> FakePricingRepo:
    repo = FakePricingRepo()
    repo.seed("suno", "music_generation", 10)
    repo.seed("fal", "image_generation", 5)
    repo.seed("deepseek", "text_generation", 2)
    return repo


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def service(
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    plan_repo: FakePlanRepo,
    pricing_repo: FakePricingRepo,
    redis: FakeRedis,
) -> UsageEnforcementService:
    return UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=usage_repo,
        plan_repo=plan_repo,
        pricing_repo=pricing_repo,
        redis=redis,
    )


# ---------------------------------------------------------------------------
# Tests: Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_and_deduct_success(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    redis: FakeRedis,
) -> None:
    """Monthly subscribers consume plan quota without wallet deduction."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    result = await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    assert result == 0
    assert credit_repo.deduct_calls == []
    assert len(usage_repo.increment_calls) == 1
    assert usage_repo.increment_calls[0]["user_id"] == user_id
    assert usage_repo.increment_calls[0]["operation_type"] == "music"


@pytest.mark.asyncio
async def test_check_and_deduct_no_plan_allows_credit_only(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Users without an active plan can still use credit-only (skips quota checks)."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    plan_repo.set_plan(user_id, None)

    result = await service.check_and_deduct(
        user_id, None, "music_generation", "suno"
    )

    assert result == 10


# ---------------------------------------------------------------------------
# Tests: Pricing not configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_pricing_raises_external_service_error(
    service: UsageEnforcementService,
) -> None:
    """Missing pricing configuration raises ExternalServiceError."""
    user_id = uuid4()

    with pytest.raises(ExternalServiceError, match="No pricing configured"):
        await service.check_and_deduct(
            user_id, None, "unknown_operation", "unknown_service"
        )


# ---------------------------------------------------------------------------
# Tests: Insufficient credits (Requirement 6.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insufficient_credits_raises_402(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Balance below credits_per_operation raises InsufficientCreditsError."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 5)  # needs 10 for music
    plan_repo.set_plan(user_id, None)  # wallet billing only

    with pytest.raises(InsufficientCreditsError) as exc_info:
        await service.check_and_deduct(
            user_id, None, "music_generation", "suno"
        )

    assert exc_info.value.details["required_credits"] == 10
    assert exc_info.value.details["current_balance"] == 5


@pytest.mark.asyncio
async def test_race_condition_deduction_failure(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Race condition during atomic_deduct raises InsufficientCreditsError."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    credit_repo.deduct_should_fail = True
    plan_repo.set_plan(
        user_id,
        _make_plan(monthly_song=None, monthly_image=None, billing_cycle_days=None, name="lifetime"),
    )

    with pytest.raises(InsufficientCreditsError, match="concurrent"):
        await service.check_and_deduct(
            user_id, None, "music_generation", "suno"
        )


# ---------------------------------------------------------------------------
# Tests: Daily quota exceeded (Requirement 6.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_quota_exceeded_raises_429(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """Reaching daily limit raises QuotaExceededError with DAILY_QUOTA_EXCEEDED."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 0)
    today = billing_today()
    usage_repo.set_daily_count(user_id, channel_id, "music", today, 7)

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(
            user_id, channel_id, "music_generation", "suno"
        )

    assert exc_info.value.details["error_code"] == "DAILY_QUOTA_EXCEEDED"
    assert exc_info.value.details["limit"] == 7
    assert exc_info.value.details["current_usage"] == 7
    assert exc_info.value.details["operation_type"] == "music_generation"


@pytest.mark.asyncio
async def test_daily_image_limit_uses_image_field(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """Image generation uses daily_image_limit_per_channel from plan."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 0)
    today = billing_today()
    usage_repo.set_daily_count(user_id, channel_id, "background_image", today, 7)

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(
            user_id, channel_id, "image_generation", "fal"
        )

    assert exc_info.value.details["error_code"] == "DAILY_QUOTA_EXCEEDED"


# ---------------------------------------------------------------------------
# Tests: Monthly quota exceeded (Requirement 6.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monthly_quota_exceeded_uses_wallet_for_subscription(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """Subscription users at monthly limit can continue via wallet credits."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 5000)
    today = billing_today()
    period_start = today.replace(day=1)
    usage_repo.set_monthly_count(user_id, "music", period_start, 420)

    result = await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    assert result == 10
    assert credit_repo.deduct_calls[-1] == (user_id, 10, "music_generation via suno")


@pytest.mark.asyncio
async def test_plan_limit_zero_raises_429(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Plan with monthly limit = 0 raises QuotaExceededError with PLAN_LIMIT_ZERO."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    plan_repo.set_plan(user_id, _make_plan(monthly_song=0))

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(
            user_id, uuid4(), "music_generation", "suno"
        )

    assert exc_info.value.details["error_code"] == "PLAN_LIMIT_ZERO"


# ---------------------------------------------------------------------------
# Tests: Lifetime plans skip monthly check (Requirement 6.7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifetime_plan_skips_monthly_check(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Plans with null monthly limits (Lifetime) skip monthly check entirely."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    plan_repo.set_plan(
        user_id,
        _make_plan(monthly_song=None, monthly_image=None, billing_cycle_days=None, name="lifetime"),
    )

    # Should succeed even with no monthly limit configured
    result = await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )
    assert result == 10


@pytest.mark.asyncio
async def test_text_generation_skips_monthly_check(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
) -> None:
    """Text generation on subscription uses plan quota without wallet charge."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    result = await service.check_and_deduct(
        user_id, None, "text_generation", "deepseek"
    )
    assert result == 0
    assert credit_repo.deduct_calls == []


@pytest.mark.asyncio
async def test_subscription_monthly_exhausted_without_wallet_raises_402(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """When monthly quota is exhausted and wallet is empty, raise InsufficientCreditsError."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 0)
    today = billing_today()
    period_start = today.replace(day=1)
    usage_repo.set_monthly_count(user_id, "music", period_start, 420)

    with pytest.raises(InsufficientCreditsError):
        await service.check_and_deduct(
            user_id, channel_id, "music_generation", "suno"
        )


@pytest.mark.asyncio
async def test_subscription_monthly_exhausted_uses_wallet(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """When monthly quota is exhausted, subscription users pay from wallet."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    today = billing_today()
    period_start = today.replace(day=1)
    usage_repo.set_monthly_count(user_id, "music", period_start, 420)

    result = await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    assert result == 10
    assert credit_repo.deduct_calls[-1] == (user_id, 10, "music_generation via suno")


@pytest.mark.asyncio
async def test_preflight_batch_subscription_covers_without_wallet(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
) -> None:
    """Batch preflight passes for subscribers when quota covers the batch."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 0)

    await service.preflight_batch_cost(
        user_id,
        song_count=5,
        total_wallet_cost=500,
        image_jobs=0,
    )


@pytest.mark.asyncio
async def test_preflight_batch_requires_wallet_when_quota_exhausted(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """Batch preflight requires wallet balance when monthly song quota is exhausted."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 5)
    today = billing_today()
    period_start = today.replace(day=1)
    usage_repo.set_monthly_count(user_id, "music", period_start, 420)

    with pytest.raises(InsufficientCreditsError):
        await service.preflight_batch_cost(
            user_id,
            song_count=1,
            total_wallet_cost=100,
            image_jobs=0,
        )


@pytest.mark.asyncio
async def test_quota_period_follows_license_activation_not_calendar_month(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Quota is tracked on the activation-aligned billing window, not calendar month."""
    activated = datetime.now(timezone.utc) - timedelta(days=10)
    period_start = activated.date()
    calendar_start = date.today().replace(day=1)
    if calendar_start == period_start:
        pytest.skip("Activation date aligns with calendar month in this test run")

    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    quarterly_plan = _make_plan(
        monthly_song=50,
        billing_cycle_days=90,
        name="3-month",
    )
    plan_repo.set_plan(user_id, quarterly_plan, activated_at=activated)

    usage_repo.set_monthly_count(user_id, "music", calendar_start, 999)

    result = await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    assert result == 0
    assert credit_repo.deduct_calls == []
    assert usage_repo.increment_calls[-1]["period_start"] == period_start


# ---------------------------------------------------------------------------
# Tests: Redis caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_cache_hit(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    redis: FakeRedis,
) -> None:
    """Daily count is read from Redis cache when available."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 0)
    today = billing_today()
    cache_key = UsageEnforcementService._daily_cache_key(
        user_id, channel_id, "music", today
    )
    # Pre-populate cache with count that would exceed limit
    await redis.set(cache_key, "7")

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(
            user_id, channel_id, "music_generation", "suno"
        )

    assert exc_info.value.details["error_code"] == "DAILY_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_redis_ttl_set_on_increment(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    redis: FakeRedis,
) -> None:
    """After successful deduction, Redis cache is incremented with 25-hour TTL."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 0)
    today = billing_today()

    await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    cache_key = UsageEnforcementService._daily_cache_key(
        user_id, channel_id, "music", today
    )
    assert cache_key in redis._ttls
    assert redis._ttls[cache_key] == DAILY_CACHE_TTL_SECONDS


# ---------------------------------------------------------------------------
# Tests: Helper method unit tests
# ---------------------------------------------------------------------------


class TestGetDailyLimit:
    """Tests for _get_daily_limit static method."""

    def test_music_generation(self) -> None:
        plan = _make_plan(daily_song=10, daily_image=5)
        assert UsageEnforcementService._get_daily_limit(plan, "music_generation") == 10

    def test_image_generation(self) -> None:
        plan = _make_plan(daily_song=10, daily_image=5)
        assert UsageEnforcementService._get_daily_limit(plan, "image_generation") == 5

    def test_channel_setup(self) -> None:
        plan = _make_plan(daily_song=10, daily_image=5)
        assert UsageEnforcementService._get_daily_limit(plan, "channel_setup") == 5

    def test_text_generation_defaults_to_song(self) -> None:
        plan = _make_plan(daily_song=10, daily_image=5)
        assert UsageEnforcementService._get_daily_limit(plan, "text_generation") == 10

    def test_unknown_defaults_to_song(self) -> None:
        plan = _make_plan(daily_song=10, daily_image=5)
        assert UsageEnforcementService._get_daily_limit(plan, "something_else") == 10


class TestGetMonthlyLimit:
    """Tests for _get_monthly_limit static method."""

    def test_music_generation(self) -> None:
        plan = _make_plan(monthly_song=420, monthly_image=100)
        assert UsageEnforcementService._get_monthly_limit(plan, "music_generation") == 420

    def test_image_generation(self) -> None:
        plan = _make_plan(monthly_song=420, monthly_image=100)
        assert UsageEnforcementService._get_monthly_limit(plan, "image_generation") == 100

    def test_channel_setup(self) -> None:
        plan = _make_plan(monthly_song=420, monthly_image=100)
        assert UsageEnforcementService._get_monthly_limit(plan, "channel_setup") == 100

    def test_text_generation_returns_none(self) -> None:
        plan = _make_plan(monthly_song=420, monthly_image=100)
        assert UsageEnforcementService._get_monthly_limit(plan, "text_generation") is None

    def test_null_monthly_song_returns_none(self) -> None:
        plan = _make_plan(monthly_song=None)
        assert UsageEnforcementService._get_monthly_limit(plan, "music_generation") is None

    def test_null_monthly_image_returns_none(self) -> None:
        plan = _make_plan(monthly_image=None)
        assert UsageEnforcementService._get_monthly_limit(plan, "image_generation") is None


class TestDailyCacheKey:
    """Tests for _daily_cache_key static method."""

    def test_with_channel(self) -> None:
        user_id = uuid4()
        channel_id = uuid4()
        key = UsageEnforcementService._daily_cache_key(
            user_id, channel_id, "music_generation", date(2024, 6, 15)
        )
        expected = f"daily_usage:{user_id}:{channel_id}:music_generation:2024-06-15"
        assert key == expected

    def test_without_channel(self) -> None:
        user_id = uuid4()
        key = UsageEnforcementService._daily_cache_key(
            user_id, None, "text_generation", date(2024, 1, 1)
        )
        expected = f"daily_usage:{user_id}:none:text_generation:2024-01-01"
        assert key == expected


# ---------------------------------------------------------------------------
# Song package accounting (Model A)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suno_music_increments_song_quota_and_ledger_zero(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    pricing_repo: FakePricingRepo,
) -> None:
    """One Suno music call burns +1 song package and writes plan_allowance ledger."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    result = await service.check_and_deduct(user_id, channel_id, "music", "suno")

    assert result == 0
    assert credit_repo.deduct_calls == []
    assert len(usage_repo.increment_calls) == 1
    assert usage_repo.increment_calls[0]["operation_type"] == "music"
    assert len(credit_repo.ledger_calls) == 1
    ledger = credit_repo.ledger_calls[0]
    assert ledger["amount"] == 0
    assert ledger["direction"] == "debit"
    assert ledger["metadata"]["billing"] == "plan_allowance"
    assert ledger["metadata"]["list_credit_units"] == 10
    assert ledger["metadata"]["charged_credit_units"] == 0
    assert ledger["metadata"]["coverage"] == "song_package"


@pytest.mark.asyncio
async def test_lyric_under_plan_increments_draft_not_song(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    pricing_repo: FakePricingRepo,
) -> None:
    """Lyric burns draft meter (+1 draft), not song; ledger amount 0."""
    pricing_repo.seed("slai", "lyric", 216)
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    result = await service.check_and_deduct(user_id, channel_id, "lyric", "slai")

    assert result == 0
    assert credit_repo.deduct_calls == []
    assert len(usage_repo.increment_calls) == 1
    assert usage_repo.increment_calls[0]["operation_type"] == "draft"
    assert len(credit_repo.ledger_calls) == 1
    ledger = credit_repo.ledger_calls[0]
    assert ledger["amount"] == 0
    assert ledger["metadata"]["billing"] == "plan_allowance"
    assert ledger["metadata"]["coverage"] == "draft_allowance"
    assert ledger["metadata"]["list_credit_units"] == 216
    assert ledger["metadata"]["operation"] == "lyric"


@pytest.mark.asyncio
async def test_title_and_album_under_plan_bump_draft_meter(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    pricing_repo: FakePricingRepo,
) -> None:
    pricing_repo.seed("openai", "title", 32)
    pricing_repo.seed("openai", "album", 176)
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    await service.check_and_deduct(user_id, None, "title", "openai")
    await service.check_and_deduct(user_id, None, "album", "openai")

    assert len(usage_repo.increment_calls) == 2
    assert all(c["operation_type"] == "draft" for c in usage_repo.increment_calls)
    assert len(credit_repo.ledger_calls) == 2
    assert all(c["amount"] == 0 for c in credit_repo.ledger_calls)


@pytest.mark.asyncio
async def test_draft_daily_enforced_against_draft_pool(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    pricing_repo: FakePricingRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Draft ops use the hard daily draft pool and increment it."""
    pricing_repo.seed("slai", "lyric", 216)
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 0)
    plan_repo.set_plan(user_id, _make_plan(daily_draft=7))
    today = billing_today()
    usage_repo.set_daily_count(user_id, channel_id, "draft", today, 7)

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(user_id, channel_id, "lyric", "slai")

    assert exc_info.value.details["error_code"] == "DAILY_QUOTA_EXCEEDED"
    assert usage_repo.increment_calls == []
    assert credit_repo.ledger_calls == []


@pytest.mark.asyncio
async def test_attribute_secondary_daily_usage_drafts_without_monthly(
    service: UsageEnforcementService,
    usage_repo: FakeUsageRepo,
) -> None:
    """Secondary draft attribution mirrors Primary slot count on daily only."""
    user_id = uuid4()
    alt_channel_id = uuid4()
    today = billing_today()

    await service.attribute_secondary_daily_usage(
        user_id,
        alt_channel_id,
        "draft",
        count=21,
    )

    assert len(usage_repo.increment_calls) == 1
    call = usage_repo.increment_calls[0]
    assert call["channel_profile_id"] == alt_channel_id
    assert call["operation_type"] == "draft"
    assert call["count"] == 21
    assert call["include_monthly"] is False
    assert await usage_repo.get_daily_count(user_id, alt_channel_id, "draft", today) == 21
    assert await usage_repo.get_monthly_count(user_id, "draft", call["period_start"]) == 0


@pytest.mark.asyncio
async def test_check_and_deduct_plan_path_writes_ledger_for_music_generation(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
) -> None:
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    await service.check_and_deduct(user_id, uuid4(), "music_generation", "suno")
    assert credit_repo.ledger_calls[-1]["metadata"]["billing"] == "plan_allowance"


@pytest.mark.asyncio
async def test_refund_suno_failure_releases_song_quota_and_keeps_cogs_ledger(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """After music deduct, Suno failure returns the song unit; COGS debit stays."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    charged = await service.deduct_for_operation(
        user_id, channel_id, "music", "suno"
    )
    assert charged == 0
    assert len(usage_repo.increment_calls) == 1
    assert usage_repo.increment_calls[0]["operation_type"] == "music"
    debit_ledger = credit_repo.ledger_calls[-1]
    assert debit_ledger["metadata"]["billing"] == "plan_allowance"
    assert debit_ledger["direction"] == "debit"

    await service.refund_failed_operation(
        user_id,
        channel_id,
        "music",
        "suno",
        charged_credit_units=charged,
        reason="suno_generation_failed",
        prior_ledger_recorded=True,
    )

    assert len(usage_repo.decrement_calls) == 1
    assert usage_repo.decrement_calls[0]["operation_type"] == "music"
    refund_row = credit_repo.ledger_calls[-1]
    assert refund_row["direction"] == "refund"
    assert refund_row["amount"] == 0
    assert refund_row["metadata"]["outcome"] == "failed"
    assert refund_row["metadata"]["billing"] == "platform_absorb"
    assert refund_row["metadata"]["platform_absorbed_cost"] is True
    assert refund_row["metadata"]["list_credit_units"] == 10
    # Original plan_allowance debit still present for owner COGS.
    assert credit_repo.ledger_calls[0]["metadata"]["billing"] == "plan_allowance"


@pytest.mark.asyncio
async def test_refund_suno_failure_refunds_wallet_when_charged(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    plan_repo: FakePlanRepo,
) -> None:
    """Wallet-billed music failure returns both song quota and wallet credits."""
    plan_repo.set_plan(uuid4(), None)  # ensure no default pollution
    # Replace active plan with None for this user
    user_id = uuid4()
    channel_id = uuid4()
    plan_repo.set_plan(user_id, None)
    credit_repo.set_balance(user_id, 500)

    charged = await service.deduct_for_operation(
        user_id, channel_id, "music", "suno"
    )
    assert charged == 10
    assert await credit_repo.get_balance(user_id) == 490

    await service.refund_failed_operation(
        user_id,
        channel_id,
        "music",
        "suno",
        charged_credit_units=charged,
        reason="suno_generation_failed",
        prior_ledger_recorded=True,
    )

    assert await credit_repo.get_balance(user_id) == 500
    assert credit_repo.refund_calls[-1]["amount"] == 10
    assert credit_repo.refund_calls[-1]["metadata"]["outcome"] == "failed"
    assert len(usage_repo.decrement_calls) == 1


@pytest.mark.asyncio
async def test_refund_image_failure_releases_quota_and_writes_cogs_debit(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
    pricing_repo: FakePricingRepo,
) -> None:
    """Image reserve-then-fail path releases quota and records platform-absorb COGS."""
    pricing_repo.seed("fal", "background_image", 50)
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    await service.reserve_operation_quota(
        user_id=user_id,
        channel_profile_id=channel_id,
        operation_type="background_image",
    )
    # FakeUsageRepo.increment is used via try_increment absence — reserve falls
    # back to enforce + increment when try_increment is missing.
    assert usage_repo.increment_calls[-1]["operation_type"] == "background_image"

    await service.refund_failed_operation(
        user_id,
        channel_id,
        "background_image",
        "fal",
        charged_credit_units=0,
        reason="image_generation_failed",
        prior_ledger_recorded=False,
    )

    assert usage_repo.decrement_calls[-1]["operation_type"] == "background_image"
    cogs = credit_repo.ledger_calls[-1]
    assert cogs["direction"] == "debit"
    assert cogs["amount"] == 0
    assert cogs["metadata"]["billing"] == "platform_absorb"
    assert cogs["metadata"]["outcome"] == "failed"
    assert cogs["metadata"]["list_credit_units"] == 50
    assert cogs["metadata"]["platform_absorbed_cost"] is True


@pytest.mark.asyncio
async def test_fail_absorb_budget_blocks_after_daily_limit(
    service: UsageEnforcementService,
    redis: FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H2: after N platform_absorb events, further AI reservation is blocked."""
    from platform_api.exceptions import QuotaExceededError

    monkeypatch.setattr(
        "platform_api.services.usage_enforcement_service._daily_fail_absorb_budget",
        lambda: 2,
    )
    user_id = uuid4()
    channel_id = uuid4()

    await service.record_fail_absorb(user_id)
    await service.record_fail_absorb(user_id)
    assert await service.get_fail_absorb_count(user_id) == 2

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.enforce_fail_absorb_budget(user_id)
    assert exc_info.value.details["error_code"] == "FAIL_BUDGET_EXCEEDED"

    with pytest.raises(QuotaExceededError):
        await service.reserve_operation_quota(
            user_id=user_id,
            channel_profile_id=channel_id,
            operation_type="background_image",
        )


@pytest.mark.asyncio
async def test_refund_records_fail_absorb_counter(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    pricing_repo: FakePricingRepo,
    redis: FakeRedis,
) -> None:
    user_id = uuid4()
    channel_id = uuid4()
    pricing_repo.seed("fal", "background_image", 50)

    await service.refund_failed_operation(
        user_id,
        channel_id,
        "background_image",
        "fal",
        charged_credit_units=0,
        reason="image_generation_failed",
        prior_ledger_recorded=False,
    )
    assert await service.get_fail_absorb_count(user_id) == 1
