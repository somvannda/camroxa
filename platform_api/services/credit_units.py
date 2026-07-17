"""Fixed-point credit amounts (micro-credits) for sub-cent billing.

Display credits are what admins and users see (e.g. 0.03, 1000).
Internal storage uses integer micro-units: 1 display credit = CREDIT_SCALE units.

With GCV = $0.01, $0.0003 provider cost = 0.03 display credits = 300 units.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from platform_api.exceptions import ValidationError

# 4 decimal places on display credits (0.0001 cr minimum charge).
CREDIT_SCALE = 10_000

DEFAULT_GCV = 0.01

MAX_DISPLAY_CREDITS = 10_000_000
MIN_DISPLAY_CREDITS = 0.0001

MAX_CREDIT_UNITS = MAX_DISPLAY_CREDITS * CREDIT_SCALE
MIN_CREDIT_UNITS = 1

# Credit packs must grant at least one whole display credit.
MIN_PACK_CREDIT_UNITS = CREDIT_SCALE


def _to_decimal(value: float | int | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def units_to_credits(units: int | None) -> float:
    """Convert stored micro-units to display credits."""
    if units is None:
        return 0.0
    return float(_to_decimal(units) / CREDIT_SCALE)


def credits_to_units(
    credits: float | int | str | Decimal,
    *,
    rounding: str = ROUND_HALF_UP,
) -> int:
    """Convert display credits to stored micro-units."""
    amount = (_to_decimal(credits) * CREDIT_SCALE).quantize(Decimal("1"), rounding=rounding)
    return int(amount)


def credits_to_units_ceil(credits: float | int | str | Decimal) -> int:
    return credits_to_units(credits, rounding=ROUND_CEILING)


def validate_display_credits(
    credits: float,
    *,
    field: str = "credits",
    minimum: float = MIN_DISPLAY_CREDITS,
    maximum: float = MAX_DISPLAY_CREDITS,
) -> int:
    """Validate a display-credit amount and return micro-units."""
    if credits < minimum or credits > maximum:
        raise ValidationError(
            f"{field} must be between {minimum} and {maximum} display credits.",
            details={"field": field, "value": credits},
        )
    units = credits_to_units(credits)
    if units < MIN_CREDIT_UNITS:
        raise ValidationError(
            f"{field} is below the minimum charge of {MIN_DISPLAY_CREDITS} credits.",
            details={"field": field, "value": credits},
        )
    return units


def validate_pack_credits(credits: float) -> int:
    """Credit packs must contain at least one whole credit."""
    units = validate_display_credits(credits, field="song_credits")
    if units < MIN_PACK_CREDIT_UNITS:
        raise ValidationError(
            "Credit packs must include at least 1 whole credit.",
            details={"song_credits": credits},
        )
    return units


def usd_to_cost_units(cost_usd: float, global_credit_value: float) -> int:
    """Convert provider USD cost to cost micro-units at the configured GCV."""
    if global_credit_value <= 0:
        raise ValueError("global_credit_value must be positive")
    credits = _to_decimal(cost_usd) / _to_decimal(global_credit_value)
    units = credits_to_units(credits, rounding=ROUND_HALF_UP)
    return max(MIN_CREDIT_UNITS, units)


def cost_units_to_pricing_units(cost_units: int, margin_percent: float) -> int:
    """Apply target margin on revenue and return pricing micro-units."""
    if margin_percent < 0 or margin_percent >= 100:
        raise ValueError("margin_percent must be between 0 and 99.99")
    cost_credits = _to_decimal(cost_units) / CREDIT_SCALE
    divisor = Decimal("1") - (_to_decimal(margin_percent) / Decimal("100"))
    pricing_credits = cost_credits / divisor
    pricing_units = credits_to_units_ceil(pricing_credits)
    return max(cost_units, max(MIN_CREDIT_UNITS, pricing_units))


def format_display_credits(credits: float) -> str:
    """Human-friendly credit formatting."""
    if credits == 0:
        return "0"
    if credits >= 100:
        return f"{credits:,.2f}".rstrip("0").rstrip(".")
    if credits >= 1:
        return f"{credits:.4f}".rstrip("0").rstrip(".")
    return f"{credits:.4f}".rstrip("0").rstrip(".")


def format_credit_log_amount(units: int) -> str:
    """Format micro-units for human-readable server logs."""
    return f"{format_display_credits(units_to_credits(units))} credits ({units} units)"
