"""Subscription plan change validation and checkout pricing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from platform_api.exceptions import ValidationError
from platform_api.models.domain import Plan
from platform_api.services.proration_service import ProrationQuote, compute_upgrade_proration


def is_plan_downgrade(current_plan: Plan, target_plan: Plan) -> bool:
    return int(target_plan.profile_allowance or 0) < int(current_plan.profile_allowance or 0)


def is_billing_term_change(current_plan: Plan, target_plan: Plan) -> bool:
    return int(target_plan.profile_allowance or 0) == int(current_plan.profile_allowance or 0) and int(
        target_plan.billing_cycle_days or 0
    ) != int(current_plan.billing_cycle_days or 0)


def is_channel_upgrade(current_plan: Plan, target_plan: Plan) -> bool:
    return int(target_plan.profile_allowance or 0) > int(current_plan.profile_allowance or 0)


def validate_mid_cycle_plan_change(
    *,
    current_plan: Plan,
    target_plan: Plan,
    license_expires_at: datetime | None,
    now: datetime | None = None,
) -> None:
    """Block immediate downgrades while the current subscription period is active."""
    if not is_plan_downgrade(current_plan, target_plan):
        return

    now = now or datetime.now(timezone.utc)
    if license_expires_at is None:
        raise ValidationError(
            "Downgrades take effect at renewal. Schedule a downgrade instead of immediate checkout.",
            details={"error_code": "DOWNGRADE_AT_RENEWAL_ONLY"},
        )

    period_end = (
        license_expires_at
        if license_expires_at.tzinfo is not None
        else license_expires_at.replace(tzinfo=timezone.utc)
    )
    if period_end > now:
        raise ValidationError(
            "Downgrades take effect at renewal when your current billing period ends.",
            details={
                "error_code": "DOWNGRADE_AT_RENEWAL_ONLY",
                "renewal_at": period_end.isoformat(),
            },
        )


def resolve_plan_change_checkout(
    *,
    current_plan: Plan,
    target_plan: Plan,
    license_expires_at: datetime | None,
    list_price_cents: int,
) -> tuple[int, dict[str, Any]]:
    """Return checkout amount and metadata for an existing subscriber changing plans."""
    validate_mid_cycle_plan_change(
        current_plan=current_plan,
        target_plan=target_plan,
        license_expires_at=license_expires_at,
    )

    metadata: dict[str, Any] = {
        "previous_plan_id": str(current_plan.id),
        "target_plan_id": str(target_plan.id),
    }

    if is_billing_term_change(current_plan, target_plan):
        metadata["plan_change"] = "term_change"
        metadata["charge_mode"] = "full_term"
        return max(0, int(list_price_cents)), metadata

    if is_channel_upgrade(current_plan, target_plan):
        proration: ProrationQuote = compute_upgrade_proration(
            current_plan_price_cents=int(current_plan.price_cents or 0),
            new_plan_price_cents=int(target_plan.price_cents or 0),
            billing_cycle_days=int(current_plan.billing_cycle_days or 30),
            period_end=license_expires_at,
        )
        metadata["plan_change"] = "upgrade"
        metadata["charge_mode"] = "proration"
        metadata.update(proration.as_metadata())
        amount = proration.amount_due_cents if proration.amount_due_cents > 0 else int(list_price_cents)
        return max(0, amount), metadata

    metadata["plan_change"] = "renewal"
    metadata["charge_mode"] = "list_price"
    return max(0, int(list_price_cents)), metadata
