"""Tests for local video/merge platform operation seeds."""

from __future__ import annotations

from platform_api.services.credit_units import units_to_credits
from platform_api.services.local_platform_operations import (
    LOCAL_AI_SERVICE,
    build_local_model_cost_rows,
    build_local_pricing_seed_rows,
)
from platform_api.services.model_cost_estimates import build_seed_cost_rows


def test_local_model_cost_rows_in_registry_seed() -> None:
    rows = build_seed_cost_rows()
    local = [
        row
        for row in rows
        if row["ai_service"] == LOCAL_AI_SERVICE
    ]
    assert {row["operation_type"] for row in local} == {
        "video",
        "video_manual",
        "video_merge",
    }
    assert all(row["cost_usd"] == 0 for row in local)
    assert all(row["source"] == "registry" for row in local)


def test_local_pricing_seed_defaults() -> None:
    rows = build_local_pricing_seed_rows()
    by_op = {row["operation_type"]: row for row in rows}
    assert by_op["video"]["ai_service"] == LOCAL_AI_SERVICE
    assert by_op["video_manual"]["ai_service"] == LOCAL_AI_SERVICE
    assert by_op["video_merge"]["ai_service"] == LOCAL_AI_SERVICE
    assert units_to_credits(by_op["video"]["credits_per_operation"]) == 3.0
    assert units_to_credits(by_op["video_manual"]["credits_per_operation"]) == 3.0
    assert units_to_credits(by_op["video_merge"]["credits_per_operation"]) == 10.0
    assert by_op["video"]["external_cost_cents"] == 0
    assert by_op["video_manual"]["external_cost_cents"] == 0
    assert by_op["video_merge"]["external_cost_cents"] == 0
    assert by_op["video"]["needs_review"] is False


def test_build_local_model_cost_rows_matches_platform_registry() -> None:
    rows = build_local_model_cost_rows()
    assert len(rows) == 3
