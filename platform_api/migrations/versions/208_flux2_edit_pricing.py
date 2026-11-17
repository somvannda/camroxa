"""Price FLUX.2 edit for AI-text thumbnails; retire Flux.1 img2img fallback.

Revision ID: 208
Revises: 207
Create Date: 2026-11-17

Live model tests showed Flux.1 dev image-to-image preserves the background but
does not render the requested text. FLUX.2 edit rendered the exact text and kept
the scene.

FAL pricing (checked 2026-11-17):
- fal-ai/flux-2/edit: $0.012 per processed megapixel.
  1920x1080 = 2.0736 MP -> $0.0248832 cost. 100% markup = $0.0497664.
  At $0.005/credit -> 9.95328 -> 10 credits (100,000 micro-units).
- fal-ai/flux-2-pro/edit: $0.03 first output MP + $0.015 per extra input/output MP.
  1920x1080 edit -> $0.045 cost. 100% markup = $0.09 -> 18 credits
  (180,000 micro-units).
"""

from __future__ import annotations

from alembic import op

revision = "208"
down_revision = "207"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove the Flux.1 img2img model that failed text rendering.
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE ai_service = 'fal'
          AND operation_type = 'thumbnail_image'
          AND sub_model = 'flux-dev-image-to-image'
        """
    )
    op.execute(
        """
        DELETE FROM ai_model_costs
        WHERE ai_service = 'fal'
          AND sub_model = 'flux-dev-image-to-image'
        """
    )

    op.execute(
        """
        INSERT INTO credit_pricing (
            ai_service, operation_type, sub_model, credits_per_operation,
            external_cost_cents, created_at, updated_at
        )
        VALUES ('fal', 'thumbnail_image', 'flux-2/edit', 100000, 2488, NOW(), NOW())
        ON CONFLICT (ai_service, operation_type, sub_model) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ai_model_costs (
            ai_service, sub_model, operation_type, cost_usd, source,
            created_at, updated_at
        )
        VALUES ('fal', 'flux-2/edit', 'thumbnail_image', 0.0248832, 'registry', NOW(), NOW())
        ON CONFLICT (ai_service, sub_model, operation_type) DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO credit_pricing (
            ai_service, operation_type, sub_model, credits_per_operation,
            external_cost_cents, created_at, updated_at
        )
        VALUES ('fal', 'thumbnail_image', 'flux-2-pro/edit', 180000, 4500, NOW(), NOW())
        ON CONFLICT (ai_service, operation_type, sub_model) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO ai_model_costs (
            ai_service, sub_model, operation_type, cost_usd, source,
            created_at, updated_at
        )
        VALUES ('fal', 'flux-2-pro/edit', 'thumbnail_image', 0.045, 'registry', NOW(), NOW())
        ON CONFLICT (ai_service, sub_model, operation_type) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ai_model_costs
        WHERE ai_service = 'fal'
          AND sub_model IN ('flux-2/edit', 'flux-2-pro/edit')
          AND operation_type = 'thumbnail_image'
        """
    )
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE ai_service = 'fal'
          AND operation_type = 'thumbnail_image'
          AND sub_model IN ('flux-2/edit', 'flux-2-pro/edit')
        """
    )
