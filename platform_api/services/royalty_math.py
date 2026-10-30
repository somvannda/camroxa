"""Money conversion helpers for royalty reporting.

The streaming admin catalog stores royalty amounts in micro-USD (1e-6 USD).
"""

from __future__ import annotations

MICROS_PER_USD = 1_000_000


def micros_to_usd(micros: int | float | None) -> float:
    """Convert micro-USD to USD."""
    return float(micros or 0) / MICROS_PER_USD


def usd_to_micros(usd: float | int | None) -> int:
    """Convert USD to micro-USD."""
    return int(round(float(usd or 0) * MICROS_PER_USD))
