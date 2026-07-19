"""Tests for billing calendar helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from platform_api.services.billing_calendar import (
    BILLING_TIMEZONE,
    billing_today,
    billing_usage_date,
    next_billing_midnight,
)


def test_billing_usage_date_from_utc_before_phnom_penh_midnight() -> None:
    # 2026-07-16 18:00 UTC = 2026-07-17 01:00 Cambodia
    dt = datetime(2026, 7, 16, 18, 0, tzinfo=timezone.utc)
    assert billing_usage_date(dt) == date(2026, 7, 17)


def test_billing_usage_date_from_date_passthrough() -> None:
    assert billing_usage_date(date(2026, 7, 17)) == date(2026, 7, 17)


def test_next_billing_midnight_is_phnom_penh_rollover_in_utc() -> None:
    reset = next_billing_midnight(from_date=date(2026, 7, 17))
    local = reset.astimezone(BILLING_TIMEZONE)
    assert local.date() == date(2026, 7, 18)
    assert local.hour == 0
    assert local.minute == 0


def test_billing_today_returns_date() -> None:
    today = billing_today()
    assert isinstance(today, date)
