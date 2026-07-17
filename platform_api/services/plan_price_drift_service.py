"""Detect drift between computed term prices and stored plan row prices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from platform_api.services.plan_tier_pricing_service import (
    billing_term_quotes,
    is_profile_addon_plan,
    is_subscription_plan,
    round_whole_dollars,
)


@dataclass(frozen=True, slots=True)
class PlanPriceDriftItem:
    plan_id: str
    plan_name: str
    billing_cycle_days: int
    profile_allowance: int
    stored_cents: int
    expected_cents: int
    plan_kind: str


def compute_subscription_term_drift(
    plans: list[Any],
    *,
    semi_annual_discount_percent: int,
    annual_discount_percent: int,
) -> list[PlanPriceDriftItem]:
    drift: list[PlanPriceDriftItem] = []
    monthly_by_channels: dict[int, Any] = {}
    for plan in subscription_plans_only(plans):
        if int(getattr(plan, "billing_cycle_days", 0) or 0) != 30:
            continue
        channels = int(getattr(plan, "profile_allowance", 0) or 0)
        monthly_by_channels[channels] = plan

    for plan in subscription_plans_only(plans):
        cycle = int(getattr(plan, "billing_cycle_days", 0) or 0)
        if cycle not in (180, 365):
            continue
        channels = int(getattr(plan, "profile_allowance", 0) or 0)
        monthly = monthly_by_channels.get(channels)
        if monthly is None:
            continue
        terms = billing_term_quotes(
            int(monthly.price_cents or 0),
            semi_annual_discount_percent=semi_annual_discount_percent,
            annual_discount_percent=annual_discount_percent,
        )
        expected = next((term.total_cents for term in terms if term.billing_cycle_days == cycle), None)
        if expected is None:
            continue
        stored = int(getattr(plan, "price_cents", 0) or 0)
        if stored != expected:
            drift.append(
                PlanPriceDriftItem(
                    plan_id=str(plan.id),
                    plan_name=str(getattr(plan, "name", "") or ""),
                    billing_cycle_days=cycle,
                    profile_allowance=channels,
                    stored_cents=stored,
                    expected_cents=expected,
                    plan_kind="subscription",
                )
            )
    return drift


def compute_profile_addon_term_drift(
    plans: list[Any],
    *,
    semi_annual_discount_percent: int,
    annual_discount_percent: int,
) -> list[PlanPriceDriftItem]:
    drift: list[PlanPriceDriftItem] = []
    monthly_addons = [
        plan
        for plan in plans
        if is_profile_addon_plan(plan)
        and bool(getattr(plan, "is_active", False))
        and int(getattr(plan, "billing_cycle_days", 0) or 0) == 30
    ]
    for monthly in monthly_addons:
        bundle = int(getattr(monthly, "profile_allowance", 0) or 0)
        terms = billing_term_quotes(
            int(monthly.price_cents or 0),
            semi_annual_discount_percent=semi_annual_discount_percent,
            annual_discount_percent=annual_discount_percent,
        )
        for term in terms:
            if term.billing_cycle_days == 30:
                continue
            matches = [
                plan
                for plan in plans
                if is_profile_addon_plan(plan)
                and int(getattr(plan, "profile_allowance", 0) or 0) == bundle
                and int(getattr(plan, "billing_cycle_days", 0) or 0) == term.billing_cycle_days
            ]
            if not matches:
                continue
            for plan in matches:
                stored = int(getattr(plan, "price_cents", 0) or 0)
                if stored != term.total_cents:
                    drift.append(
                        PlanPriceDriftItem(
                            plan_id=str(plan.id),
                            plan_name=str(getattr(plan, "name", "") or ""),
                            billing_cycle_days=term.billing_cycle_days,
                            profile_allowance=bundle,
                            stored_cents=stored,
                            expected_cents=term.total_cents,
                            plan_kind="profile_addon",
                        )
                    )
    return drift


def subscription_plans_only(plans: list[Any]) -> list[Any]:
    return [plan for plan in plans if is_subscription_plan(plan) and bool(getattr(plan, "is_active", False))]
