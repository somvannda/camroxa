"""USD amount helpers for model cost storage."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def normalize_cost_usd(value: float | str | Decimal | None) -> Decimal:
    """Normalize a USD amount to 8 decimal places."""
    if value is None:
        return Decimal("0")
    amount = Decimal(str(value))
    if amount < 0:
        amount = Decimal("0")
    return amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def cost_usd_to_float(value: Decimal | float | str | None) -> float:
    return float(normalize_cost_usd(value))
