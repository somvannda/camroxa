"""Tests for subscription renewal alert levels."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from platform_api.services.subscription_renewal_alert_service import (
    RenewalAlertLevel,
    renewal_alert_level,
)


def test_renewal_alert_none_when_no_expiry() -> None:
    assert renewal_alert_level(None) == RenewalAlertLevel.NONE


def test_renewal_alert_expired() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    expires = now - timedelta(hours=1)
    assert renewal_alert_level(expires, now=now) == RenewalAlertLevel.EXPIRED


def test_renewal_alert_warn_at_seven_days() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    expires = now + timedelta(days=5)
    assert renewal_alert_level(expires, now=now) == RenewalAlertLevel.WARN


def test_renewal_alert_urgent_at_three_days() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    expires = now + timedelta(days=2)
    assert renewal_alert_level(expires, now=now) == RenewalAlertLevel.URGENT


def test_renewal_alert_urgent_at_one_day() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    expires = now + timedelta(hours=20)
    assert renewal_alert_level(expires, now=now) == RenewalAlertLevel.URGENT
