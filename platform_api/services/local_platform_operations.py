"""Registry for local desktop operations (no external AI provider).

Video export and auto-merge run on the user's machine (FFmpeg). COGS is $0;
list prices are fixed display credits, not margin-derived from model costs.
"""

from __future__ import annotations

from typing import Any

from platform_api.services.credit_units import credits_to_units

LOCAL_AI_SERVICE = "local"

# Canonical defaults — keep in sync with migration 048_plan_video_merge_limits.
LOCAL_PLATFORM_OPERATIONS: dict[str, dict[str, Any]] = {
    "video": {
        "label": "Studio export (per track)",
        "cost_usd": 0.0,
        "list_credits_display": 0.0,
        "cost_credits_display": 0.0,
        "notes": "Pipeline/auto local FFmpeg export — COGS $0; free (0 credits)",
    },
    "video_manual": {
        "label": "Manual export (per track)",
        "cost_usd": 0.0,
        "list_credits_display": 0.0,
        "cost_credits_display": 0.0,
        "notes": "Manual Video-page export — COGS $0; free (0 credits)",
    },
    "video_merge": {
        "label": "Auto merge video",
        "cost_usd": 0.0,
        "list_credits_display": 0.0,
        "cost_credits_display": 0.0,
        "notes": "Local FFmpeg concat — COGS $0; free (0 credits)",
    },
}


def build_local_model_cost_rows() -> list[dict[str, Any]]:
    """Suggested ai_model_costs rows for local platform operations."""
    rows: list[dict[str, Any]] = []
    for operation_type, spec in LOCAL_PLATFORM_OPERATIONS.items():
        rows.append(
            {
                "ai_service": LOCAL_AI_SERVICE,
                "sub_model": "",
                "operation_type": operation_type,
                "cost_usd": float(spec["cost_usd"]),
                "notes": str(spec["notes"]),
                "source": "registry",
            }
        )
    return rows


def build_local_pricing_seed_rows() -> list[dict[str, Any]]:
    """Suggested credit_pricing rows for local platform operations."""
    rows: list[dict[str, Any]] = []
    for operation_type, spec in LOCAL_PLATFORM_OPERATIONS.items():
        rows.append(
            {
                "ai_service": LOCAL_AI_SERVICE,
                "operation_type": operation_type,
                "sub_model": "",
                "credits_per_operation": credits_to_units(
                    float(spec["list_credits_display"])
                ),
                "external_cost_cents": credits_to_units(
                    float(spec["cost_credits_display"])
                ),
                "needs_review": False,
            }
        )
    return rows


def local_pricing_defaults_display() -> dict[str, dict[str, float]]:
    """Human-readable defaults for docs/admin copy."""
    return {
        operation_type: {
            "list_credits": float(spec["list_credits_display"]),
            "cost_credits": float(spec["cost_credits_display"]),
        }
        for operation_type, spec in LOCAL_PLATFORM_OPERATIONS.items()
    }
