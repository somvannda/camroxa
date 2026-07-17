"""Tests for micro-credit conversion helpers."""

from __future__ import annotations

from platform_api.services.credit_units import (
    CREDIT_SCALE,
    cost_units_to_pricing_units,
    credits_to_units,
    units_to_credits,
    usd_to_cost_units,
)
from platform_api.services.pricing_generator_service import compute_credit_prices


def test_units_round_trip() -> None:
    assert credits_to_units(0.03) == 300
    assert units_to_credits(300) == 0.03
    assert credits_to_units(1000) == 10_000_000


def test_deepseek_cost_at_gcv_one_cent() -> None:
    units = usd_to_cost_units(0.0003, 0.01)
    assert units == 300
    assert units_to_credits(units) == 0.03


def test_compute_credit_prices_deepseek_with_margin() -> None:
    cost_units, pricing_units = compute_credit_prices(
        cost_usd=0.0003,
        global_credit_value=0.01,
        margin_percent=10.0,
    )
    assert cost_units == 300
    assert pricing_units == 334
    assert units_to_credits(pricing_units) == 0.0334


def test_compute_credit_prices_ten_dollar_op() -> None:
    cost_units, pricing_units = compute_credit_prices(
        cost_usd=0.10,
        global_credit_value=0.01,
        margin_percent=10.0,
    )
    assert cost_units == 100_000
    assert pricing_units == 111_112
