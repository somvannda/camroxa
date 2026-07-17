"""Billing period helpers aligned to license activation and plan cycle length."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from platform_api.models.domain import Plan


@dataclass(frozen=True)
class BillingPeriod:
    """Inclusive billing period boundaries for quota accounting."""

    start: date
    end: date


@dataclass(frozen=True)
class ActiveSubscriptionContext:
    """Active license + plan context needed for quota enforcement."""

    plan: Plan
    license_id: UUID
    activated_at: datetime | None
    profile_addon_slots: int = 0
    profile_addon_pending: int = 0


def _as_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def compute_billing_period(
    *,
    activated_at: datetime | date | None,
    billing_cycle_days: int | None,
    reference_date: date | None = None,
) -> BillingPeriod:
    """Compute the current billing period from license activation.

    Subscription quotas are counted within this window. For example, a 90-day
    plan activated on 2026-01-15 uses period 2026-01-15..2026-04-14, then
    rolls forward in 90-day blocks while the license remains active.
    """
    today = reference_date or date.today()

    if activated_at is None or billing_cycle_days is None or billing_cycle_days <= 0:
        return _calendar_month_period(today)

    activation_date = _as_date(activated_at)
    if today < activation_date:
        return BillingPeriod(
            start=activation_date,
            end=activation_date + timedelta(days=billing_cycle_days - 1),
        )

    days_since_activation = (today - activation_date).days
    periods_elapsed = days_since_activation // billing_cycle_days
    period_start = activation_date + timedelta(days=periods_elapsed * billing_cycle_days)
    period_end = period_start + timedelta(days=billing_cycle_days - 1)
    return BillingPeriod(start=period_start, end=period_end)


def period_start_for_subscription(
    *,
    plan: Plan | None,
    activated_at: datetime | date | None,
    reference_date: date | None = None,
) -> date:
    """Return quota period_start for usage_tracking and subscription checks."""
    if plan is None:
        today = reference_date or date.today()
        return today.replace(day=1)

    period = compute_billing_period(
        activated_at=activated_at,
        billing_cycle_days=plan.billing_cycle_days,
        reference_date=reference_date,
    )
    return period.start


def period_end_for_subscription(
    *,
    plan: Plan,
    period_start: date,
) -> date:
    """Return inclusive period end for quota reset messaging."""
    if plan.billing_cycle_days is not None and plan.billing_cycle_days > 0:
        return period_start + timedelta(days=plan.billing_cycle_days - 1)
    return _calendar_month_period(period_start).end


def _calendar_month_period(reference: date) -> BillingPeriod:
    """Fallback when no license cycle is available."""
    period_start = reference.replace(day=1)
    if period_start.month == 12:
        next_month = period_start.replace(year=period_start.year + 1, month=1, day=1)
    else:
        next_month = period_start.replace(month=period_start.month + 1, day=1)
    return BillingPeriod(start=period_start, end=next_month - timedelta(days=1))
