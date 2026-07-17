"""Regression tests for subscription quota display helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from platform_api.models.domain import Plan
from platform_api.services.billing_period_service import ActiveSubscriptionContext
from platform_api.services.quota_display_service import (
    get_monthly_quota_status,
    period_start_for_context,
    resolve_subscription_context,
)


def _plan(*, billing_cycle_days: int | None = 30) -> Plan:
    now = datetime.now(timezone.utc)
    return Plan(
        id=uuid4(),
        name="monthly",
        price_cents=7900,
        billing_cycle_days=billing_cycle_days,
        profile_allowance=2,
        monthly_song_limit=300,
        monthly_image_limit=60,
        monthly_draft_limit=1260,
        monthly_video_limit=300,
        monthly_merge_limit=30,
        daily_song_limit_per_channel=7,
        daily_image_limit_per_channel=2,
        daily_draft_limit_per_channel=300,
        is_active=True,
        effective_from=now,
        created_at=now,
        updated_at=now,
    )


class FakeUsageRepo:
    def __init__(self, monthly: int = 0) -> None:
        self._monthly = monthly

    async def get_monthly_count(
        self, user_id, operation_type: str, period_start: date
    ) -> int:
        return self._monthly


class FakePlanRepo:
    def __init__(self, ctx: ActiveSubscriptionContext | None) -> None:
        self._ctx = ctx

    async def get_user_active_subscription_context(self, user_id):
        return self._ctx

    async def get_user_active_plan(self, user_id) -> Plan | None:
        return self._ctx.plan if self._ctx else None


def test_period_start_for_context_uses_billing_period_helper() -> None:
    """Missing billing_period import used to NameError here (preflight 500)."""
    plan = _plan(billing_cycle_days=90)
    activated = datetime(2026, 1, 15, tzinfo=timezone.utc)
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=activated,
    )

    assert period_start_for_context(ctx, reference_date=date(2026, 2, 10)) == date(
        2026, 1, 15
    )


@pytest.mark.asyncio
async def test_resolve_subscription_context_builds_fallback_context() -> None:
    plan = _plan()

    class PlanOnlyRepo:
        async def get_user_active_plan(self, user_id) -> Plan | None:
            return plan

    ctx = await resolve_subscription_context(PlanOnlyRepo(), uuid4())
    assert ctx is not None
    assert ctx.plan.id == plan.id


@pytest.mark.asyncio
async def test_get_monthly_quota_status_songs_and_drafts() -> None:
    """End-to-end path used by POST /batches/preflight after quota checks."""
    plan = _plan()
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    plan_repo = FakePlanRepo(ctx)
    usage_repo = FakeUsageRepo(monthly=42)
    user_id = uuid4()

    songs_quota, songs_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="songs",
    )
    drafts_quota, drafts_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="drafts",
    )

    assert songs_quota == 300
    assert songs_remaining == 258
    assert drafts_quota == 1260
    assert drafts_remaining == 1218
