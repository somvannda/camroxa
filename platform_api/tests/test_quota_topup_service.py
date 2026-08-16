"""Tests for period-scoped admin quota top-ups."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.models.domain import Plan
from platform_api.services.billing_period_service import ActiveSubscriptionContext
from platform_api.services.quota_display_service import get_monthly_quota_status
from platform_api.services.quota_topup_service import (
    QuotaTopupService,
    normalize_quota_kind,
    quota_kind_for_operation,
)


def _plan(*, song_limit: int | None = 100, draft_limit: int | None = 500) -> Plan:
    now = datetime.now(timezone.utc)
    return Plan(
        id=uuid4(),
        name="monthly",
        price_cents=7900,
        billing_cycle_days=30,
        profile_allowance=2,
        monthly_song_limit=song_limit,
        monthly_image_limit=60,
        monthly_draft_limit=draft_limit,
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


class FakeTopupRepo:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def add_topup(
        self,
        *,
        user_id,
        license_id,
        period_start,
        quota_kind,
        extra_units,
        reason,
        created_by,
    ):
        topup_id = uuid4()
        self.rows.append(
            {
                "id": topup_id,
                "user_id": user_id,
                "license_id": license_id,
                "period_start": period_start,
                "quota_kind": quota_kind,
                "extra_units": int(extra_units),
                "reason": reason,
                "created_by": created_by,
            }
        )
        return topup_id

    async def sum_extra_units(self, user_id, period_start, quota_kind) -> int:
        return sum(
            int(r["extra_units"])
            for r in self.rows
            if r["user_id"] == user_id
            and r["period_start"] == period_start
            and r["quota_kind"] == quota_kind
        )

    async def sum_extras_for_period(self, user_id, period_start) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.rows:
            if r["user_id"] != user_id or r["period_start"] != period_start:
                continue
            out[r["quota_kind"]] = out.get(r["quota_kind"], 0) + int(r["extra_units"])
        return out


class FakePlanRepo:
    def __init__(self, ctx: ActiveSubscriptionContext | None) -> None:
        self._ctx = ctx

    async def get_user_active_subscription_context(self, user_id):
        return self._ctx

    async def get_user_active_plan(self, user_id):
        return self._ctx.plan if self._ctx else None


class FakeUsageRepo:
    def __init__(self, monthly_by_op: dict[str, int] | None = None) -> None:
        self._monthly_by_op = monthly_by_op or {}

    async def get_monthly_count(self, user_id, operation_type: str, period_start: date) -> int:
        return int(self._monthly_by_op.get(operation_type, 0))


def test_normalize_quota_kind_aliases() -> None:
    assert normalize_quota_kind("songs") == "music"
    assert normalize_quota_kind("Drafts") == "draft"
    assert normalize_quota_kind("images") == "image"
    assert normalize_quota_kind("videos") == "video"
    assert normalize_quota_kind("merges") == "merge"
    with pytest.raises(ValidationError):
        normalize_quota_kind("album")


def test_quota_kind_for_operation_maps_draft_ops() -> None:
    assert quota_kind_for_operation("lyric") == "draft"
    assert quota_kind_for_operation("title") == "draft"
    assert quota_kind_for_operation("album") == "draft"
    assert quota_kind_for_operation("music") == "music"
    assert quota_kind_for_operation("video_merge") == "merge"


@pytest.mark.asyncio
async def test_extras_for_period_sums_current_period() -> None:
    user_id = uuid4()
    repo = FakeTopupRepo()
    service = QuotaTopupService(
        topup_repo=repo,
        plan_repo=FakePlanRepo(None),
    )
    period = date(2026, 8, 2)
    await repo.add_topup(
        user_id=user_id,
        license_id=None,
        period_start=period,
        quota_kind="image",
        extra_units=10,
        reason="first Batch",
        created_by=uuid4(),
    )
    await repo.add_topup(
        user_id=user_id,
        license_id=None,
        period_start=date(2026, 7, 3),
        quota_kind="image",
        extra_units=99,
        reason="old period",
        created_by=uuid4(),
    )
    extras = await service.extras_for_period(user_id, period)
    assert extras == {"image": 10}


@pytest.mark.asyncio
async def test_grant_adds_extra_for_current_period_only() -> None:
    user_id = uuid4()
    admin_id = uuid4()
    plan = _plan()
    activated = datetime(2026, 7, 10, tzinfo=timezone.utc)
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=activated,
        profile_addon_slots=0,
    )
    repo = FakeTopupRepo()
    service = QuotaTopupService(
        topup_repo=repo,
        plan_repo=FakePlanRepo(ctx),
        usage_repo=FakeUsageRepo({"music": 40}),
    )
    period_start, _period_end = service.period_bounds(ctx, reference_date=date(2026, 8, 4))

    result = await service.grant(
        user_id=user_id,
        quota_kind="music",
        amount=25,
        reason="support goodwill",
        admin_id=admin_id,
    )
    assert result["base_limit"] == 100
    assert result["topup_extra"] == 25
    assert result["effective_limit"] == 125
    assert result["used"] == 40
    assert result["remaining"] == 85
    assert result["period_start"] == period_start.isoformat()

    # Prior period rows must not count.
    repo.rows.append(
        {
            "id": uuid4(),
            "user_id": user_id,
            "license_id": None,
            "period_start": date(2026, 1, 1),
            "quota_kind": "music",
            "extra_units": 999,
            "reason": "old",
            "created_by": admin_id,
        }
    )
    extra = await service.extra_for(user_id, period_start, "music")
    assert extra == 25


@pytest.mark.asyncio
async def test_grant_rejects_no_plan_and_unlimited() -> None:
    user_id = uuid4()
    admin_id = uuid4()
    service = QuotaTopupService(
        topup_repo=FakeTopupRepo(),
        plan_repo=FakePlanRepo(None),
        usage_repo=FakeUsageRepo(),
    )
    with pytest.raises(ValidationError):
        await service.grant(
            user_id=user_id,
            quota_kind="draft",
            amount=10,
            reason="x",
            admin_id=admin_id,
        )

    plan = _plan(draft_limit=None)
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    service2 = QuotaTopupService(
        topup_repo=FakeTopupRepo(),
        plan_repo=FakePlanRepo(ctx),
        usage_repo=FakeUsageRepo(),
    )
    with pytest.raises(ValidationError):
        await service2.grant(
            user_id=user_id,
            quota_kind="draft",
            amount=10,
            reason="x",
            admin_id=admin_id,
        )


@pytest.mark.asyncio
async def test_display_remaining_includes_topup() -> None:
    user_id = uuid4()
    plan = _plan(song_limit=100)
    ctx = ActiveSubscriptionContext(
        plan=plan,
        license_id=uuid4(),
        activated_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    plan_repo = FakePlanRepo(ctx)
    usage_repo = FakeUsageRepo({"music": 90})
    topup_repo = FakeTopupRepo()
    service = QuotaTopupService(
        topup_repo=topup_repo,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
    )
    period_start, _ = service.period_bounds(ctx, reference_date=date(2026, 8, 4))
    await topup_repo.add_topup(
        user_id=user_id,
        license_id=ctx.license_id,
        period_start=period_start,
        quota_kind="music",
        extra_units=20,
        reason="bump",
        created_by=uuid4(),
    )

    limit, remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="songs",
        topup_service=service,
    )
    assert limit == 120
    assert remaining == 30
