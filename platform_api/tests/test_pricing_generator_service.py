"""Tests for margin-based pricing generation."""

from __future__ import annotations

import pytest

from platform_api.services.credit_units import units_to_credits
from platform_api.services.pricing_generator_service import compute_credit_prices


def test_compute_credit_prices_applies_margin_on_revenue() -> None:
    cost_units, pricing_units = compute_credit_prices(
        cost_usd=0.10,
        global_credit_value=0.01,
        margin_percent=10.0,
    )
    assert units_to_credits(cost_units) == 10
    assert pricing_units > cost_units


def test_compute_credit_prices_minimum_fractional_credit() -> None:
    cost_units, pricing_units = compute_credit_prices(
        cost_usd=0.0003,
        global_credit_value=0.01,
        margin_percent=10.0,
    )
    assert cost_units == 300
    assert pricing_units >= cost_units


def test_compute_credit_prices_sub_cent_cost() -> None:
    cost_units, pricing_units = compute_credit_prices(
        cost_usd=0.0003,
        global_credit_value=0.01,
        margin_percent=10.0,
    )
    assert units_to_credits(cost_units) == 0.03
    assert units_to_credits(pricing_units) >= 0.03


def test_compute_credit_prices_rejects_invalid_margin() -> None:
    with pytest.raises(Exception):
        compute_credit_prices(
            cost_usd=0.10,
            global_credit_value=0.01,
            margin_percent=100.0,
        )
