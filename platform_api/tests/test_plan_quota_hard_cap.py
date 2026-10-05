"""Plan quota hard cap + daily bank cap.

Covers docs/bugs/2026-10-05-plan-quota-enforcement-bypass.md:
- subscription plans must NOT exceed ``monthly_song_limit`` unless the deployment
  opts into wallet overage (``PLATFORM_PLAN_MONTHLY_OVERAGE_ALLOWED``);
- the daily bank cannot accrue more than ``MAX_BANK_DAYS`` of unused allowance.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

import pytest

from platform_api.exceptions import QuotaExceededError
from platform_api.services.daily_quota_bank_service import (
    MAX_BANK_DAYS,
    DailyQuotaBankService,
)
from platform_api.services.usage_enforcement_service import UsageEnforcementService
from platform_api.tests.test_usage_enforcement_service import (
    FakeCreditRepo,
    FakePlanRepo,
    FakePricingRepo,
    FakeRedis,
    FakeUsageRepo,
    _make_plan,
)


# ---------------------------------------------------------------------------
# Daily bank cap
# ---------------------------------------------------------------------------


class _BankRepo:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row

    async def get_row(self, _user_id: Any, _channel: Any, _op: str):
        return self.row

    async def upsert_accrual(
        self,
        _user_id: Any,
        _channel: Any,
        _op: str,
        *,
        banked_units: int,
        last_accrual_date: date,
    ) -> None:
        self.row = {
            "banked_units": banked_units,
            "last_accrual_date": last_accrual_date,
        }

    async def decrement_bank(self, *_a: Any, **_k: Any) -> int:
        return 0


class _ZeroUsage:
    async def get_daily_count(self, *_a: Any, **_k: Any) -> int:
        return 0

    async def get_account_daily_count(self, *_a: Any, **_k: Any) -> int:
        return 0


@pytest.mark.asyncio
async def test_daily_bank_is_capped_at_max_days() -> None:
    """Months of unused daily allowance must NOT become an unbounded burst."""
    repo = _BankRepo({"banked_units": 0, "last_accrual_date": date(2026, 8, 1)})
    service = DailyQuotaBankService(repo, _ZeroUsage())

    banked = await service.accrue_and_get_banked_units(
        uuid4(), uuid4(), "music", daily_limit=150, usage_date=date(2026, 10, 5)
    )

    assert banked == 150 * MAX_BANK_DAYS


@pytest.mark.asyncio
async def test_daily_bank_accrues_normally_under_cap() -> None:
    # last_accrual 10-02, today 10-05 -> accrues 10-03 and 10-04 = 2 days.
    repo = _BankRepo({"banked_units": 0, "last_accrual_date": date(2026, 10, 2)})
    service = DailyQuotaBankService(repo, _ZeroUsage())

    banked = await service.accrue_and_get_banked_units(
        uuid4(), uuid4(), "music", daily_limit=150, usage_date=date(2026, 10, 5)
    )

    assert banked == 300


# ---------------------------------------------------------------------------
# Monthly hard cap for subscription plans
# ---------------------------------------------------------------------------


def _service(usage_repo: FakeUsageRepo) -> UsageEnforcementService:
    pricing = FakePricingRepo()
    pricing.seed("suno", "music_generation", 10)
    return UsageEnforcementService(
        credit_repo=FakeCreditRepo(balance=100000),
        usage_repo=usage_repo,
        plan_repo=FakePlanRepo(plan=_make_plan(monthly_song=450, daily_song=150)),
        pricing_repo=pricing,
        redis=FakeRedis(),
    )


@pytest.mark.asyncio
async def test_monthly_hard_cap_blocks_subscription_plan(monkeypatch) -> None:
    from platform_api.services import usage_enforcement_service as ues

    today = date(2026, 10, 5)
    monkeypatch.setattr(ues, "billing_today", lambda: today)
    # Default: overage NOT allowed.
    monkeypatch.setattr(
        ues, "get_settings", lambda: type("S", (), {"plan_monthly_overage_allowed": False})()
    )

    usage_repo = FakeUsageRepo()
    service = _service(usage_repo)
    user_id = uuid4()
    ctx = await service._plan_repo.get_user_active_subscription_context(user_id)
    period_start = service._period_start(ctx, today)
    # Already at the 450 monthly limit.
    usage_repo.set_monthly_count(user_id, "music", period_start, 450)

    with pytest.raises(QuotaExceededError) as exc:
        await service._enforce_plan_quotas(
            user_id=user_id,
            channel_profile_id=uuid4(),
            operation_type="music",
            subscription_context=ctx,
            additional_count=1,
        )
    assert exc.value.details["error_code"] == "MONTHLY_QUOTA_EXCEEDED"


class _AuthoritativeUsage(FakeUsageRepo):
    """Fake that exposes the authoritative `songs` count (B fix)."""

    def __init__(self, songs: int) -> None:
        super().__init__()
        self._songs = songs

    async def count_generated_songs_for_period(
        self, _user_id: Any, _period_start: date, _period_end: date
    ) -> int:
        return self._songs


@pytest.mark.asyncio
async def test_authoritative_song_count_drives_cap(monkeypatch) -> None:
    """Real generations cap the month even when the incremental counter reads 0."""
    from platform_api.services import usage_enforcement_service as ues

    today = date(2026, 10, 5)
    monkeypatch.setattr(ues, "billing_today", lambda: today)
    monkeypatch.setattr(
        ues, "get_settings", lambda: type("S", (), {"plan_monthly_overage_allowed": False})()
    )

    usage_repo = _AuthoritativeUsage(450)  # 450 real songs; counter stays 0
    pricing = FakePricingRepo()
    pricing.seed("suno", "music_generation", 10)
    service = UsageEnforcementService(
        credit_repo=FakeCreditRepo(balance=100000),
        usage_repo=usage_repo,
        plan_repo=FakePlanRepo(plan=_make_plan(monthly_song=450, daily_song=150)),
        pricing_repo=pricing,
        redis=FakeRedis(),
    )
    user_id = uuid4()
    ctx = await service._plan_repo.get_user_active_subscription_context(user_id)

    with pytest.raises(QuotaExceededError) as exc:
        await service._enforce_plan_quotas(
            user_id=user_id,
            channel_profile_id=uuid4(),
            operation_type="music",
            subscription_context=ctx,
            additional_count=1,
        )
    assert exc.value.details["error_code"] == "MONTHLY_QUOTA_EXCEEDED"
    # Sanity: the legacy counter alone would have allowed it.
    assert await usage_repo.get_monthly_count(user_id, "music", today.replace(day=1)) == 0


@pytest.mark.asyncio
async def test_monthly_overage_allowed_when_opted_in(monkeypatch) -> None:
    from platform_api.services import usage_enforcement_service as ues

    today = date(2026, 10, 5)
    monkeypatch.setattr(ues, "billing_today", lambda: today)
    monkeypatch.setattr(
        ues, "get_settings", lambda: type("S", (), {"plan_monthly_overage_allowed": True})()
    )

    usage_repo = FakeUsageRepo()
    service = _service(usage_repo)
    user_id = uuid4()
    ctx = await service._plan_repo.get_user_active_subscription_context(user_id)
    period_start = service._period_start(ctx, today)
    usage_repo.set_monthly_count(user_id, "music", period_start, 450)

    # Opted in -> no raise (wallet overage path).
    await service._enforce_plan_quotas(
        user_id=user_id,
        channel_profile_id=uuid4(),
        operation_type="music",
        subscription_context=ctx,
        additional_count=1,
    )
