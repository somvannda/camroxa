"""Regression tests for subscription quota display helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from platform_api.models.domain import Plan
from platform_api.services.billing_period_service import ActiveSubscriptionContext
from platform_api.services.quota_display_service import (
    get_channel_daily_quotas,
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
    def __init__(
        self,
        monthly: int = 0,
        *,
        daily_by_op: dict[str, int] | None = None,
    ) -> None:
        self._monthly = monthly
        self._daily_by_op = daily_by_op or {}

    async def get_monthly_count(
        self, user_id, operation_type: str, period_start: date
    ) -> int:
        return self._monthly

    async def get_daily_count(
        self, user_id, channel_profile_id, operation_type: str, usage_date: date
    ) -> int:
        return int(self._daily_by_op.get(operation_type, 0))


class FakeAuthoritativeUsageRepo(FakeUsageRepo):
    """Exposes the authoritative song counter used by enforcement."""

    def __init__(self, monthly: int = 0, *, authoritative_songs: int = 0) -> None:
        super().__init__(monthly)
        self._authoritative_songs = authoritative_songs

    async def count_generated_songs_for_period(
        self, user_id, period_start: date, period_end: date
    ) -> int:
        return int(self._authoritative_songs)


class FakeProfile:
    def __init__(self, *, profile_id, name: str) -> None:
        self.id = profile_id
        self.name = name


class FakeProfileRepo:
    def __init__(self, profiles: list[FakeProfile]) -> None:
        self._profiles = profiles

    async def list_for_user(self, user_id):
        return self._profiles


@pytest.mark.asyncio
async def test_get_channel_daily_quotas_includes_drafts() -> None:
    plan = _plan()
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    profile_id = uuid4()
    channels = await get_channel_daily_quotas(
        user_id=uuid4(),
        plan_repo=FakePlanRepo(ctx),
        usage_repo=FakeUsageRepo(
            daily_by_op={
                "music": 10,
                "background_image": 1,
                "thumbnail_image": 1,
                "draft": 21,
            }
        ),
        profile_repo=FakeProfileRepo(
            [FakeProfile(profile_id=profile_id, name="Bass Drive")]
        ),
        usage_date=date(2026, 8, 1),
    )

    assert len(channels) == 1
    channel = channels[0]
    assert channel.profile_name == "Bass Drive"
    assert channel.daily_songs_used == 10
    assert channel.daily_songs_limit == 7
    assert channel.daily_songs_remaining == 0
    assert channel.daily_images_used == 2
    assert channel.daily_images_limit == 2
    assert channel.daily_drafts_used == 21
    assert channel.daily_drafts_limit == 300
    assert channel.daily_drafts_remaining == 279


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


@pytest.mark.asyncio
async def test_songs_remaining_uses_authoritative_song_count() -> None:
    """Songs remaining must reflect real generations, not the stale counter."""
    plan = _plan()
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    # Counter says 999 (stale / not written on the credits-only path);
    # the authoritative songs counter says 42.
    usage_repo = FakeAuthoritativeUsageRepo(monthly=999, authoritative_songs=42)

    songs_quota, songs_remaining = await get_monthly_quota_status(
        user_id=uuid4(),
        plan_repo=FakePlanRepo(ctx),
        usage_repo=usage_repo,
        quota_field="songs",
    )
    assert songs_quota == 300
    assert songs_remaining == 258  # 300 - 42 (authoritative), not 0 (999 counter)

    # Drafts have no authoritative source and keep using the counter (999).
    drafts_quota, drafts_remaining = await get_monthly_quota_status(
        user_id=uuid4(),
        plan_repo=FakePlanRepo(ctx),
        usage_repo=usage_repo,
        quota_field="drafts",
    )
    assert drafts_quota == 1260
    assert drafts_remaining == 261  # max(0, 1260 - 999)
