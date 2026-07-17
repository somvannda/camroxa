"""Unit tests for billing mode helpers."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from platform_api.models.domain import Plan
from platform_api.services.billing_mode_service import (
    TRACKS_PER_SONG_PACKAGE,
    counts_toward_product_quota,
    counts_toward_song_quota,
    grant_included_wallet_credits,
    is_lifetime_plan,
    is_subscription_plan,
    quota_operation_type,
    song_packages_to_tracks,
    subscription_covers_batch,
    subscription_covers_operation,
)
from platform_api.services.credit_units import credits_to_units


def _plan(
    *,
    name: str = "monthly",
    billing_cycle_days: int | None = 30,
    monthly_song_limit: int | None = 300,
    monthly_image_limit: int | None = 60,
    monthly_draft_limit: int | None = 900,
    price_cents: int = 7900,
    included_wallet_credits: int = 0,
) -> Plan:
    from datetime import datetime, timezone

    return Plan(
        id=uuid4(),
        name=name,
        price_cents=price_cents,
        billing_cycle_days=billing_cycle_days,
        profile_allowance=2,
        monthly_song_limit=monthly_song_limit,
        monthly_image_limit=monthly_image_limit,
        monthly_draft_limit=monthly_draft_limit,
        daily_song_limit_per_channel=100,
        daily_image_limit_per_channel=30,
        daily_draft_limit_per_channel=300,
        included_wallet_credits=included_wallet_credits,
        is_active=True,
        effective_from=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


class FakeUsageRepo:
    def __init__(self) -> None:
        self._monthly: dict[tuple, int] = {}

    def set_monthly(self, user_id, operation_type: str, period_start: date, count: int) -> None:
        self._monthly[(user_id, operation_type, period_start)] = count

    async def get_monthly_count(self, user_id, operation_type: str, period_start: date) -> int:
        return self._monthly.get((user_id, operation_type, period_start), 0)


class FakeCreditRepo:
    def __init__(self) -> None:
        self.add_calls: list[tuple] = []

    async def add_credits(self, user_id, amount: int, reason: str, ref_id: str | None = None) -> int:
        self.add_calls.append((user_id, amount, reason, ref_id))
        return amount


def test_is_subscription_plan_monthly() -> None:
    assert is_subscription_plan(_plan(name="monthly")) is True


def test_quota_operation_type_song_package() -> None:
    assert quota_operation_type("music") == "music"
    assert quota_operation_type("music_generation") == "music"
    assert quota_operation_type("lyric") == "draft"
    assert quota_operation_type("title") == "draft"
    assert quota_operation_type("album") == "draft"
    assert counts_toward_song_quota("music") is True
    assert counts_toward_song_quota("lyric") is False
    assert counts_toward_product_quota("lyric") is True
    assert counts_toward_product_quota("background_image") is True


def test_song_packages_to_tracks_display() -> None:
    assert TRACKS_PER_SONG_PACKAGE == 2
    assert song_packages_to_tracks(300) == 600
    assert song_packages_to_tracks(None) is None


def test_is_lifetime_plan() -> None:
    assert is_lifetime_plan(_plan(name="lifetime", billing_cycle_days=None, monthly_song_limit=None)) is True


@pytest.mark.asyncio
async def test_subscription_covers_operation_under_quota() -> None:
    user_id = uuid4()
    repo = FakeUsageRepo()
    plan = _plan()
    period = date.today().replace(day=1)

    covered = await subscription_covers_operation(
        plan=plan,
        user_id=user_id,
        operation_type="music_generation",
        usage_repo=repo,
        period_start=period,
    )
    assert covered is True


@pytest.mark.asyncio
async def test_subscription_covers_batch_within_limits() -> None:
    user_id = uuid4()
    repo = FakeUsageRepo()
    plan = _plan()
    period = date.today().replace(day=1)

    covered = await subscription_covers_batch(
        plan=plan,
        user_id=user_id,
        song_count=10,
        usage_repo=repo,
        period_start=period,
        image_jobs=5,
    )
    assert covered is True


@pytest.mark.asyncio
async def test_subscription_covers_draft_meter() -> None:
    user_id = uuid4()
    repo = FakeUsageRepo()
    plan = _plan()
    period = date.today().replace(day=1)
    repo.set_monthly(user_id, "draft", period, 10)

    assert await subscription_covers_operation(
        plan=plan,
        user_id=user_id,
        operation_type="lyric",
        usage_repo=repo,
        period_start=period,
    )
    repo.set_monthly(user_id, "draft", period, 900)
    assert not await subscription_covers_operation(
        plan=plan,
        user_id=user_id,
        operation_type="title",
        usage_repo=repo,
        period_start=period,
    )


@pytest.mark.asyncio
async def test_subscription_covers_after_reservation_includes_last_unit() -> None:
    """Post-reserve coverage uses <= so the last in-quota image is plan_allowance."""
    user_id = uuid4()
    repo = FakeUsageRepo()
    plan = _plan(monthly_image_limit=120)
    period = date.today().replace(day=1)
    repo.set_monthly(user_id, "background_image", period, 120)

    assert not await subscription_covers_operation(
        plan=plan,
        user_id=user_id,
        operation_type="background_image",
        usage_repo=repo,
        period_start=period,
    )
    assert await subscription_covers_operation(
        plan=plan,
        user_id=user_id,
        operation_type="background_image",
        usage_repo=repo,
        period_start=period,
        after_reservation=True,
    )
    repo.set_monthly(user_id, "background_image", period, 121)
    assert not await subscription_covers_operation(
        plan=plan,
        user_id=user_id,
        operation_type="background_image",
        usage_repo=repo,
        period_start=period,
        after_reservation=True,
    )


@pytest.mark.asyncio
async def test_grant_included_wallet_credits_lifetime_only() -> None:
    user_id = uuid4()
    license_id = uuid4()
    credit_repo = FakeCreditRepo()
    plan = _plan(
        name="lifetime",
        billing_cycle_days=None,
        monthly_song_limit=None,
        included_wallet_credits=10000,
    )

    units = await grant_included_wallet_credits(
        credit_repo,
        user_id=user_id,
        plan=plan,
        license_id=license_id,
    )

    assert units == credits_to_units(10000)
    assert credit_repo.add_calls == [
        (user_id, credits_to_units(10000), "plan_purchase", str(license_id))
    ]


@pytest.mark.asyncio
async def test_grant_included_wallet_credits_skips_subscription() -> None:
    credit_repo = FakeCreditRepo()
    plan = _plan(name="monthly", included_wallet_credits=5000)

    units = await grant_included_wallet_credits(
        credit_repo,
        user_id=uuid4(),
        plan=plan,
        license_id=uuid4(),
    )

    assert units == 0
    assert credit_repo.add_calls == []
