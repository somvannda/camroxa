"""Tests for COGS estimate helpers used by User Spent."""

from __future__ import annotations

from datetime import date

import pytest

from platform_api.services.cogs_estimate import (
    estimate_cogs_usd,
    prorate_plan_revenue_usd,
    resolve_cost_credits,
    resolve_model_cost_usd,
)
from platform_api.services.credit_units import CREDIT_SCALE


def test_resolve_cost_credits_prefers_exact_model() -> None:
    pricing = [
        {
            "ai_service": "suno",
            "operation_type": "music",
            "sub_model": "",
            "external_cost_cents": 6 * CREDIT_SCALE,  # 6 display credits
        },
        {
            "ai_service": "suno",
            "operation_type": "music",
            "sub_model": "chirp-v4",
            "external_cost_cents": 8 * CREDIT_SCALE,
        },
    ]
    assert resolve_cost_credits(pricing, "music", "suno", "chirp-v4") == 8.0
    # Provider known, model unknown: average that provider's matching rows.
    assert resolve_cost_credits(pricing, "music_generation", "suno", None) == 7.0


def test_resolve_cost_credits_image_v3_op_and_uppercase_model() -> None:
    """v3 image charges log op "image" and an uppercased model id.

    Pricing rows are keyed by background_image/thumbnail_image, so the COGS
    estimate must alias the generic op and match the model case-insensitively;
    otherwise image spend silently reports no COGS in User Spent.
    """
    pricing = [
        {
            "ai_service": "slai",
            "operation_type": "background_image",
            "sub_model": "cx/gpt-image-2.5",
            "external_cost_cents": 2 * CREDIT_SCALE,
        },
        {
            "ai_service": "slai",
            "operation_type": "thumbnail_image",
            "sub_model": "cx/gpt-image-2.5",
            "external_cost_cents": 2 * CREDIT_SCALE,
        },
        {
            "ai_service": "kie",
            "operation_type": "background_image",
            "sub_model": "grok-imagine-image-2-0/text-to-image",
            "external_cost_cents": 4 * CREDIT_SCALE,
        },
        {
            "ai_service": "kie",
            "operation_type": "thumbnail_image",
            "sub_model": "grok-imagine-image-2-0/text-to-image",
            "external_cost_cents": 4 * CREDIT_SCALE,
        },
    ]

    assert resolve_cost_credits(pricing, "image", "", "CX/GPT-IMAGE-2.5") == 2.0
    assert (
        resolve_cost_credits(
            pricing, "image", "KIE", "GROK-IMAGINE-IMAGE-2-0/TEXT-TO-IMAGE"
        )
        == 4.0
    )
    assert (
        resolve_cost_credits(
            pricing, "background_image", "slai", "cx/gpt-image-2.5"
        )
        == 2.0
    )


def test_resolve_model_cost_usd_averages_provider_rows() -> None:
    costs = [
        {"ai_service": "openai", "operation_type": "lyric", "sub_model": "a", "cost_usd": 0.02},
        {"ai_service": "openai", "operation_type": "lyric", "sub_model": "b", "cost_usd": 0.04},
    ]
    assert resolve_model_cost_usd(costs, "lyric", "openai", None) == 0.03


def test_estimate_cogs_usd_pricing_path() -> None:
    pricing = [
        {
            "ai_service": "suno",
            "operation_type": "music",
            "sub_model": "",
            "external_cost_cents": 6 * CREDIT_SCALE,
        }
    ]
    usd, coverage = estimate_cogs_usd(
        events=2,
        operation="music",
        provider="suno",
        model=None,
        pricing=pricing,
        model_costs=[],
        gcv=0.01,
    )
    assert coverage == "pricing"
    assert usd == pytest.approx(0.12)


def test_estimate_cogs_usd_model_cost_fallback() -> None:
    costs = [
        {
            "ai_service": "suno",
            "operation_type": "music",
            "sub_model": "",
            "cost_usd": 0.06,
        }
    ]
    usd, coverage = estimate_cogs_usd(
        events=3,
        operation="music",
        provider="suno",
        model=None,
        pricing=[],
        model_costs=costs,
        gcv=0.01,
    )
    assert coverage == "model_cost"
    assert usd == pytest.approx(0.18)


def test_prorate_plan_revenue_yearly() -> None:
    usd = prorate_plan_revenue_usd(
        price_cents=12000,
        billing_cycle_days=365,
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 30),
    )
    assert usd == pytest.approx(120.0 * 30 / 365)
