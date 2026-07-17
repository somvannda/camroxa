"""Tests for subscription upgrade proration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from platform_api.services.proration_service import compute_upgrade_proration


def test_proration_mid_cycle_upgrade() -> None:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    period_end = now + timedelta(days=15)
    quote = compute_upgrade_proration(
        current_plan_price_cents=7900,
        new_plan_price_cents=15900,
        billing_cycle_days=30,
        period_end=period_end,
        now=now,
    )
    assert quote.days_remaining == 15
    assert quote.amount_due_cents > 0
    assert quote.unused_credit_cents > 0


def test_proration_after_period_end_charges_full_new_price() -> None:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    period_end = now - timedelta(days=1)
    quote = compute_upgrade_proration(
        current_plan_price_cents=7900,
        new_plan_price_cents=15900,
        billing_cycle_days=30,
        period_end=period_end,
        now=now,
    )
    assert quote.amount_due_cents == 15900
