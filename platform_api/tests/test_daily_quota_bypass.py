"""Tests for daily wallet bypass and subscription wallet gate."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import LicenseExpiredError, QuotaExceededError
from platform_api.models.domain import Plan
from platform_api.services.usage_enforcement_service import UsageEnforcementService
from platform_api.tests.test_usage_enforcement_service import (
    FakeCreditRepo,
    FakePlanRepo,
    FakePricingRepo,
    FakeRedis,
    FakeUsageRepo,
    _make_plan,
)


class FakeBankService:
    async def accrue_and_get_banked_units(self, *args: Any, **kwargs: Any) -> int:
        return int(kwargs.get("seed", 0))

    async def consume_bank_for_usage(self, *args: Any, **kwargs: Any) -> int:
        return 0


class FakeLicenseRepo:
    def __init__(
        self,
        *,
        requires_active: bool = False,
        has_active: bool = True,
    ) -> None:
        self.requires_active = requires_active
        self.has_active = has_active

    async def requires_active_license_for_wallet(self, user_id: UUID) -> bool:
        return self.requires_active

    async def has_active_license(self, user_id: str) -> bool:
        return self.has_active


@pytest.fixture
def bypass_service() -> UsageEnforcementService:
    credit_repo = FakeCreditRepo(balance=1000)
    usage_repo = FakeUsageRepo()
    plan_repo = FakePlanRepo(plan=_make_plan(daily_song=7))
    pricing_repo = FakePricingRepo()
    pricing_repo.seed("suno", "music_generation", 10)
    return UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=usage_repo,
        plan_repo=plan_repo,
        pricing_repo=pricing_repo,
        redis=FakeRedis(),
        daily_quota_bank_service=FakeBankService(),
    )


@pytest.mark.asyncio
async def test_wallet_daily_bypass_when_bank_exhausted(
    bypass_service: UsageEnforcementService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import usage_enforcement_service

    today = date(2026, 7, 17)
    monkeypatch.setattr(usage_enforcement_service, "billing_today", lambda: today)

    user_id = uuid4()
    channel_id = uuid4()
    usage_repo = bypass_service._usage_repo
    assert isinstance(usage_repo, FakeUsageRepo)
    usage_repo.set_daily_count(user_id, channel_id, "music", today, 7)

    async def _zero_bank(*args: Any, **kwargs: Any) -> int:
        return 0

    bank = bypass_service._daily_quota_bank_service
    assert bank is not None
    bank.accrue_and_get_banked_units = _zero_bank  # type: ignore[method-assign]

    result = await bypass_service.check_and_deduct(
        user_id, channel_id, "music_generation", "suno"
    )

    assert result == 10


@pytest.mark.asyncio
async def test_daily_exceeded_without_wallet_raises(
    bypass_service: UsageEnforcementService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from platform_api.services import usage_enforcement_service

    today = date(2026, 7, 17)
    monkeypatch.setattr(usage_enforcement_service, "billing_today", lambda: today)

    user_id = uuid4()
    channel_id = uuid4()
    bypass_service._credit_repo.set_balance(user_id, 0)  # type: ignore[attr-defined]
    usage_repo = bypass_service._usage_repo
    assert isinstance(usage_repo, FakeUsageRepo)
    usage_repo.set_daily_count(user_id, channel_id, "music", today, 7)

    async def _zero_bank(*args: Any, **kwargs: Any) -> int:
        return 0

    bank = bypass_service._daily_quota_bank_service
    assert bank is not None
    bank.accrue_and_get_banked_units = _zero_bank  # type: ignore[method-assign]

    with pytest.raises(QuotaExceededError) as exc_info:
        await bypass_service.check_and_deduct(
            user_id, channel_id, "music_generation", "suno"
        )

    assert exc_info.value.details["error_code"] == "DAILY_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_expired_subscription_cannot_spend_wallet() -> None:
    credit_repo = FakeCreditRepo(balance=5000)
    plan_repo = FakePlanRepo(plan=None)
    pricing_repo = FakePricingRepo()
    pricing_repo.seed("suno", "music_generation", 10)
    service = UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=FakeUsageRepo(),
        plan_repo=plan_repo,
        pricing_repo=pricing_repo,
        redis=FakeRedis(),
        license_repo=FakeLicenseRepo(requires_active=True, has_active=False),
    )

    with pytest.raises(LicenseExpiredError):
        await service.preflight_quotas_and_balance(
            uuid4(),
            None,
            "music_generation",
            min_credits=10,
        )


@pytest.mark.asyncio
async def test_wallet_only_user_without_subscription_plan_allowed() -> None:
    credit_repo = FakeCreditRepo(balance=500)
    plan_repo = FakePlanRepo(plan=None)
    pricing_repo = FakePricingRepo()
    pricing_repo.seed("suno", "music_generation", 10)
    service = UsageEnforcementService(
        credit_repo=credit_repo,
        usage_repo=FakeUsageRepo(),
        plan_repo=plan_repo,
        pricing_repo=pricing_repo,
        redis=FakeRedis(),
        license_repo=FakeLicenseRepo(requires_active=False, has_active=False),
    )

    result = await service.check_and_deduct(uuid4(), None, "music_generation", "suno")
    assert result == 10
