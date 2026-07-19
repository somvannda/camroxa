"""Billing-day calendar helpers (Asia/Phnom_Penh midnight)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BILLING_TIMEZONE = ZoneInfo("Asia/Phnom_Penh")


def billing_today() -> date:
    """Return the current billing date in Cambodia (UTC+7)."""
    return datetime.now(BILLING_TIMEZONE).date()


def next_billing_midnight(*, from_date: date | None = None) -> datetime:
    """Return the next billing-day rollover as UTC-aware datetime."""
    base = from_date or billing_today()
    local_midnight = datetime.combine(
        base + timedelta(days=1),
        datetime.min.time(),
        tzinfo=BILLING_TIMEZONE,
    )
    return local_midnight.astimezone(timezone.utc)


def billing_usage_date(dt: datetime | date | None = None) -> date:
    """Map an instant (or date) to the billing usage date."""
    if dt is None:
        return billing_today()
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BILLING_TIMEZONE).date()
