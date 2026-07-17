"""Time-based proration quotes for mid-cycle subscription upgrades."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from platform_api.services.plan_tier_pricing_service import round_whole_dollars


@dataclass(frozen=True, slots=True)
class ProrationQuote:
    amount_due_cents: int
    unused_credit_cents: int
    new_charge_cents: int
    days_remaining: int
    period_days: int
    current_plan_price_cents: int
    new_plan_price_cents: int

    def as_metadata(self) -> dict[str, int]:
        return {key: int(value) for key, value in asdict(self).items()}


def compute_upgrade_proration(
    *,
    current_plan_price_cents: int,
    new_plan_price_cents: int,
    billing_cycle_days: int,
    period_end: datetime | None,
    now: datetime | None = None,
) -> ProrationQuote:
    """Return the amount due for upgrading for the remainder of the current period."""
    now = now or datetime.now(timezone.utc)
    period_days = max(1, int(billing_cycle_days or 30))
    current_price = max(0, int(current_plan_price_cents or 0))
    new_price = max(0, int(new_plan_price_cents or 0))

    if period_end is None:
        amount_due = max(0, round_whole_dollars(new_price - current_price))
        return ProrationQuote(
            amount_due_cents=amount_due,
            unused_credit_cents=0,
            new_charge_cents=new_price,
            days_remaining=period_days,
            period_days=period_days,
            current_plan_price_cents=current_price,
            new_plan_price_cents=new_price,
        )

    end = period_end if period_end.tzinfo is not None else period_end.replace(tzinfo=timezone.utc)
    days_remaining = max(0, (end - now).days)
    if days_remaining <= 0:
        return ProrationQuote(
            amount_due_cents=new_price,
            unused_credit_cents=0,
            new_charge_cents=new_price,
            days_remaining=0,
            period_days=period_days,
            current_plan_price_cents=current_price,
            new_plan_price_cents=new_price,
        )

    unused_credit = int(current_price * days_remaining / period_days)
    new_charge = int(new_price * days_remaining / period_days)
    amount_due = max(0, round_whole_dollars(new_charge - unused_credit))
    return ProrationQuote(
        amount_due_cents=amount_due,
        unused_credit_cents=unused_credit,
        new_charge_cents=new_charge,
        days_remaining=days_remaining,
        period_days=period_days,
        current_plan_price_cents=current_price,
        new_plan_price_cents=new_price,
    )
