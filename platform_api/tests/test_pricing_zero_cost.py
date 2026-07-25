"""Regression: local COGS $0 must be accepted on pricing create/update."""

from __future__ import annotations

from platform_api.routers.credits import _pricing_units_from_request


def test_pricing_units_allow_zero_provider_cost() -> None:
    pricing_units, cost_units = _pricing_units_from_request(5.0, 0.0)
    assert pricing_units == 50_000
    assert cost_units == 0


def test_pricing_units_still_require_positive_sell_price() -> None:
    pricing_units, cost_units = _pricing_units_from_request(0.0001, None)
    assert pricing_units == 1
    assert cost_units is None
