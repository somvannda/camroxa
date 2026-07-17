"""Tests for license-aligned billing period calculations."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from platform_api.services.billing_period_service import (
    compute_billing_period,
    period_start_for_subscription,
)


def test_ninety_day_plan_uses_activation_not_calendar_month() -> None:
    activated = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    reference = date(2026, 2, 10)

    period = compute_billing_period(
        activated_at=activated,
        billing_cycle_days=90,
        reference_date=reference,
    )

    assert period.start == date(2026, 1, 15)
    assert period.end == date(2026, 4, 14)


def test_ninety_day_plan_rolls_to_next_period() -> None:
    activated = datetime(2026, 1, 15, tzinfo=timezone.utc)
    reference = date(2026, 5, 1)

    period = compute_billing_period(
        activated_at=activated,
        billing_cycle_days=90,
        reference_date=reference,
    )

    assert period.start == date(2026, 4, 15)
    assert period.end == date(2026, 7, 13)


def test_thirty_day_plan_aligns_to_activation() -> None:
    activated = datetime(2026, 3, 12, tzinfo=timezone.utc)
    reference = date(2026, 3, 25)

    period = compute_billing_period(
        activated_at=activated,
        billing_cycle_days=30,
        reference_date=reference,
    )

    assert period.start == date(2026, 3, 12)
    assert period.end == date(2026, 4, 10)


def test_missing_activation_falls_back_to_calendar_month() -> None:
    from platform_api.models.domain import Plan

    plan = Plan(
        name="quarterly",
        price_cents=10000,
        billing_cycle_days=90,
        profile_allowance=2,
        monthly_song_limit=420,
        monthly_image_limit=100,
        daily_song_limit_per_channel=7,
        daily_image_limit_per_channel=7,
    )

    period_start = period_start_for_subscription(
        plan=plan,
        activated_at=None,
        reference_date=date(2026, 6, 18),
    )

    assert period_start == date(2026, 6, 1)
