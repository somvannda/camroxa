"""Price FAL flux-dev image-to-image for AI-text thumbnails.

Revision ID: 206
Revises: 205
Create Date: 2026-11-17

FAL charges ``$0.03`` per megapixel for ``fal-ai/flux/dev/image-to-image``.
A 1920x1080 output is 2.0736 MP -> $0.062208 provider cost. A 100% markup
gives $0.124416, which is 24.8832 credits at the $0.005 global credit value.
The credit price is rounded to 25 credits (250,000 micro-units).
"""

from __future__ import annotations

from alembic import op

revision = "206"
down_revision = "205"
branch_labels = None
depends_on = None

_PROVIDER = "fal"
_MODEL = "flux-dev-image-to-image"
_OPERATION = "thumbnail_image"
_CREDITS = 250_000  # 25 credits = $0.125 at $0.005/credit
_COST_USD = "0.062208"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO credit_pricing (
            ai_service, operation_type, sub_model, credits_per_operation,
            external_cost_cents, created_at, updated_at
        )
        VALUES ('{_PROVIDER}', '{_OPERATION}', '{_MODEL}', {_CREDITS}, 6221, NOW(), NOW())
        ON CONFLICT (ai_service, operation_type, sub_model) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO ai_model_costs (
            ai_service, sub_model, operation_type, cost_usd, source,
            created_at, updated_at
        )
        VALUES ('{_PROVIDER}', '{_MODEL}', '{_OPERATION}', {_COST_USD}, 'registry', NOW(), NOW())
        ON CONFLICT (ai_service, sub_model, operation_type) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM ai_model_costs
        WHERE ai_service = '{_PROVIDER}'
          AND sub_model = '{_MODEL}'
          AND operation_type = '{_OPERATION}'
        """
    )
    op.execute(
        f"""
        DELETE FROM credit_pricing
        WHERE ai_service = '{_PROVIDER}'
          AND operation_type = '{_OPERATION}'
          AND sub_model = '{_MODEL}'
        """
    )
