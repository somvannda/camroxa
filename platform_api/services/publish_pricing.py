"""Post for Me (postforme.dev) publishing price registry.

The provider is external, so pricing lives in ``credit_pricing`` under the
``postforme`` provider instead of the local desktop registry. The seeded
default is 5 display credits per upload job (migration 178).
"""

from __future__ import annotations

from typing import Any

from platform_api.services.credit_units import credits_to_units

POSTFORME_AI_SERVICE = "postforme"
POSTFORME_UPLOAD_OPERATION = "upload"
POSTFORME_PUBLISH_OP = "publish"

# Display credits charged per publish/upload job.
POSTFORME_UPLOAD_CREDITS = 5
# Approximate provider COGS at the $10 / 1,000-post tier, in display credits.
POSTFORME_UPLOAD_COST_CREDITS = 1


def build_postforme_pricing_seed_rows() -> list[dict[str, Any]]:
    """Suggested credit_pricing rows for the Post for Me provider."""
    return [
        {
            "ai_service": POSTFORME_AI_SERVICE,
            "operation_type": POSTFORME_UPLOAD_OPERATION,
            "sub_model": "",
            "credits_per_operation": credits_to_units(POSTFORME_UPLOAD_CREDITS),
            "external_cost_cents": credits_to_units(POSTFORME_UPLOAD_COST_CREDITS),
            "needs_review": False,
        }
    ]
