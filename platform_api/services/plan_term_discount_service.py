"""Admin-managed billing-term discount percentages for subscription plan tooling."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PLAN_TERM_DISCOUNT_KEY = "plan_term_discounts"


@dataclass(frozen=True, slots=True)
class PlanTermDiscounts:
    semi_annual_discount_percent: int
    annual_discount_percent: int


def default_plan_term_discounts() -> PlanTermDiscounts:
    return PlanTermDiscounts(
        semi_annual_discount_percent=15,
        annual_discount_percent=25,
    )


def discounts_from_dict(data: dict[str, Any] | None) -> PlanTermDiscounts:
    defaults = default_plan_term_discounts()
    if not data:
        return defaults
    return PlanTermDiscounts(
        semi_annual_discount_percent=int(
            data.get("semi_annual_discount_percent") or defaults.semi_annual_discount_percent
        ),
        annual_discount_percent=int(
            data.get("annual_discount_percent") or defaults.annual_discount_percent
        ),
    )


def discounts_to_dict(discounts: PlanTermDiscounts) -> dict[str, int]:
    return {
        "semi_annual_discount_percent": discounts.semi_annual_discount_percent,
        "annual_discount_percent": discounts.annual_discount_percent,
    }


async def load_plan_term_discounts(pool: Any) -> PlanTermDiscounts:
    row = await pool.fetchrow(
        "SELECT value FROM system_settings WHERE key = $1",
        PLAN_TERM_DISCOUNT_KEY,
    )
    if row is None or not row.get("value"):
        legacy = await pool.fetchrow(
            "SELECT value FROM system_settings WHERE key = 'channel_pricing_config'",
        )
        if legacy and legacy.get("value"):
            raw = legacy["value"]
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {}
            elif isinstance(raw, dict):
                data = raw
            else:
                data = {}
            return discounts_from_dict(data)
        return default_plan_term_discounts()

    raw = row["value"]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return default_plan_term_discounts()
    elif isinstance(raw, dict):
        data = raw
    else:
        return default_plan_term_discounts()
    return discounts_from_dict(data)


async def save_plan_term_discounts(pool: Any, discounts: PlanTermDiscounts) -> None:
    payload = json.dumps(discounts_to_dict(discounts))
    await pool.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ($1, 'json', $2::jsonb, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        PLAN_TERM_DISCOUNT_KEY,
        payload,
    )
