"""Pricing registry tests for the Post for Me upload operation."""

from __future__ import annotations

import pytest

from platform_api.services.credit_units import credits_to_units, units_to_credits
from platform_api.services.publish_pricing import (
    POSTFORME_AI_SERVICE,
    POSTFORME_UPLOAD_COST_CREDITS,
    POSTFORME_UPLOAD_CREDITS,
    POSTFORME_UPLOAD_OPERATION,
    build_postforme_pricing_seed_rows,
)
from platform_api.services.v3.list_prices import (
    OP_SCAN_ALIASES,
    resolve_op_list_units,
)
from platform_api.services.v3.ops import PRICING_FALLBACKS, SUPPORTED_OPS


class FakePricing:
    def __init__(self, units: int = 50_000) -> None:
        self.units = units

    async def get_price(self, ai_service: str, operation_type: str, sub_model=None) -> int:
        if (ai_service, operation_type) == (POSTFORME_AI_SERVICE, POSTFORME_UPLOAD_OPERATION):
            return self.units
        raise KeyError(f"{ai_service}/{operation_type}")

    async def get_all_pricing(self):
        return []


def test_publish_is_a_supported_v3_op() -> None:
    assert "publish" in SUPPORTED_OPS
    assert PRICING_FALLBACKS["publish"] == ((POSTFORME_AI_SERVICE, POSTFORME_UPLOAD_OPERATION),)
    assert OP_SCAN_ALIASES["publish"] == (POSTFORME_UPLOAD_OPERATION, "publish")


def test_publish_quote_resolves_five_credits() -> None:
    units = credits_to_units(POSTFORME_UPLOAD_CREDITS)
    assert units == 50_000
    assert units_to_credits(units) == 5.0


@pytest.mark.asyncio
async def test_resolve_publish_list_units_uses_postforme_row() -> None:
    units = await resolve_op_list_units(FakePricing(50_000), "publish")
    assert units == 50_000


def test_seed_rows_charge_five_and_cost_one_credit() -> None:
    rows = build_postforme_pricing_seed_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["ai_service"] == "postforme"
    assert row["operation_type"] == "upload"
    assert row["credits_per_operation"] == credits_to_units(5)
    assert row["external_cost_cents"] == credits_to_units(POSTFORME_UPLOAD_COST_CREDITS)
    assert row["needs_review"] is False
