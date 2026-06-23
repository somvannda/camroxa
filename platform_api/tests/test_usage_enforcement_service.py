"""Unit tests for UsageEnforcementService.

Tests the enforcement check ordering, daily/monthly limits, credit deduction,
Redis caching, and edge cases (no plan, plan-limit-zero, race conditions).

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 1.5
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    QuotaExceededError,
)
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
    ) -> bool:
        self.deduct_calls.append((user_id, amount, reason))
        if self.deduct_should_fail:
            return False
        balance = self._balances.get(user_id, self._default_balance)
        if balance < amount:
            return False
        self._balances[user_id] = balance - amount
        return True


class FakeUsageRepo:
    """In-memory fake for UsageTrackingRepositoryProtocol."""

    def __init__(self) -> None:
        self._daily: dict[tuple[UUID, UUID | None, str, date], int] = {}
        self._monthly: dict[tuple[UUID, str, date], int] = {}
        self.increment_calls: list[dict[str, Any]] = []

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
    ) -> None:
        self.increment_calls.append(
            {
                "user_id": user_id,
                "channel_profile_id": channel_profile_id,
                "operation_type": operation_type,
                "usage_date": usage_date,
                "period_start": period_start,
            }
        )
        key_d = (user_id, channel_profile_id, operation_type, usage_date)
        self._daily[key_d] = self._daily.get(key_d, 0) + 1
        key_m = (user_id, operation_type, period_start)
        self._monthly[key_m] = self._monthly.get(key_m, 0) + 1


class FakePlanRepo:
    """In-memory fake for PlanRepositoryProtocol."""

    def __init__(self, plan: Plan | None = None) -> None:
        self._plans: dict[UUID, Plan | None] = {}
        self._default_plan = plan

    def set_plan(self, user_id: UUID, plan: Plan | None) -> None:
        self._plans[user_id] = plan

    async def get_user_active_plan(self, user_id: UUID) -> Plan | None:
        if user_id in self._plans:
            return self._plans[user_id]
        return self._default_plan


class FakePricingRepo:
    """In-memory fake for CreditPricingRepositoryProtocol."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], dict[str, Any]] = {}

    def seed(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
    ) -> None:
        self._entries[(ai_service, operation_type)] = {
            "ai_service": ai_service,
            "operation_type": operation_type,
            "credits_per_operation": credits_per_operation,
        }

    async def get_by_service_and_operation(
        self, ai_service: str, operation_type: str
    ) -> dict[str, Any] | None:
        return self._entries.get((ai_service, operation_type))


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
    monthly_song: int | None = 420,
    monthly_image: int | None = 100,
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
        daily_song_limit_per_channel=daily_song,
        daily_image_limit_per_channel=daily_image,
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
    """Successful deduction returns credits_per_operation and increments counters."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    result = await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    assert result == 10
    assert credit_repo.deduct_calls[-1] == (user_id, 10, "music_generation via suno")
    assert len(usage_repo.increment_calls) == 1
    assert usage_repo.increment_calls[0]["user_id"] == user_id
    assert usage_repo.increment_calls[0]["operation_type"] == "music_generation"


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
) -> None:
    """Balance below credits_per_operation raises InsufficientCreditsError."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 5)  # needs 10 for music

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
) -> None:
    """Race condition during atomic_deduct raises InsufficientCreditsError."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)
    credit_repo.deduct_should_fail = True

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
    credit_repo.set_balance(user_id, 500)
    today = date.today()
    usage_repo.set_daily_count(user_id, channel_id, "music_generation", today, 7)

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
    credit_repo.set_balance(user_id, 500)
    today = date.today()
    usage_repo.set_daily_count(user_id, channel_id, "image_generation", today, 7)

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(
            user_id, channel_id, "image_generation", "fal"
        )

    assert exc_info.value.details["error_code"] == "DAILY_QUOTA_EXCEEDED"


# ---------------------------------------------------------------------------
# Tests: Monthly quota exceeded (Requirement 6.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monthly_quota_exceeded_raises_429(
    service: UsageEnforcementService,
    credit_repo: FakeCreditRepo,
    usage_repo: FakeUsageRepo,
) -> None:
    """Reaching monthly limit raises QuotaExceededError with MONTHLY_QUOTA_EXCEEDED."""
    user_id = uuid4()
    channel_id = uuid4()
    credit_repo.set_balance(user_id, 5000)
    today = date.today()
    period_start = today.replace(day=1)
    usage_repo.set_monthly_count(user_id, "music_generation", period_start, 420)

    with pytest.raises(QuotaExceededError) as exc_info:
        await service.check_and_deduct(
            user_id, channel_id, "music_generation", "suno"
        )

    assert exc_info.value.details["error_code"] == "MONTHLY_QUOTA_EXCEEDED"
    assert exc_info.value.details["limit"] == 420
    assert exc_info.value.details["current_usage"] == 420


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
    """Text generation always skips monthly limit check."""
    user_id = uuid4()
    credit_repo.set_balance(user_id, 500)

    result = await service.check_and_deduct(
        user_id, None, "text_generation", "deepseek"
    )
    assert result == 2


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
    credit_repo.set_balance(user_id, 500)
    today = date.today()
    cache_key = UsageEnforcementService._daily_cache_key(
        user_id, channel_id, "music_generation", today
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
    credit_repo.set_balance(user_id, 500)
    today = date.today()

    await service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    cache_key = UsageEnforcementService._daily_cache_key(
        user_id, channel_id, "music_generation", today
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
