"""Renewal reminder levels for subscription licenses."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum


class RenewalAlertLevel(str, Enum):
    NONE = "none"
    WARN = "warn"
    URGENT = "urgent"
    EXPIRED = "expired"


def renewal_alert_level(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> RenewalAlertLevel:
    """Return alert severity from license expiry (7d / 3d / 1d thresholds)."""
    if expires_at is None:
        return RenewalAlertLevel.NONE

    reference = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= reference:
        return RenewalAlertLevel.EXPIRED

    days_remaining = (expires_at - reference).total_seconds() / 86400.0
    if days_remaining <= 1:
        return RenewalAlertLevel.URGENT
    if days_remaining <= 3:
        return RenewalAlertLevel.URGENT
    if days_remaining <= 7:
        return RenewalAlertLevel.WARN
    return RenewalAlertLevel.NONE


def renewal_alert_for_license(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> str:
    """String value for API responses."""
    return renewal_alert_level(expires_at, now=now).value
