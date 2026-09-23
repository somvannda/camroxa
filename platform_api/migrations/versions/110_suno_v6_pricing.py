"""Seed credit pricing for the Suno V6 music models.

V6, V6_MINI and V6_WILD are the current Suno music models. Copy the existing
V5_5/V5 (or provider-wide) music price so generation is priced the moment the
new models go live; mark rows ``needs_review`` for the admin to confirm.

Revision ID: 110_suno_v6_pricing
Revises: 109_playback_event_detail
Create Date: 2026-09-23
"""

from __future__ import annotations

from alembic import op

revision = "110_suno_v6_pricing"
down_revision = "109_playback_event_detail"
branch_labels = None
depends_on = None

_V6_MODELS = ("V6", "V6_MINI", "V6_WILD")


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO credit_pricing (
            id, ai_service, operation_type, sub_model,
            credits_per_operation, external_cost_cents, needs_review,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'suno',
            'music',
            v.model_id,
            COALESCE(
                (
                    SELECT credits_per_operation FROM credit_pricing
                    WHERE ai_service = 'suno'
                      AND operation_type IN ('music', 'music_generation')
                      AND COALESCE(sub_model, '') IN ('V5_5', 'V5')
                    ORDER BY (COALESCE(sub_model, '') = 'V5_5') DESC
                    LIMIT 1
                ),
                (
                    SELECT credits_per_operation FROM credit_pricing
                    WHERE ai_service = 'suno'
                      AND operation_type IN ('music', 'music_generation')
                      AND COALESCE(sub_model, '') = ''
                    LIMIT 1
                ),
                100000
            ),
            COALESCE(
                (
                    SELECT external_cost_cents FROM credit_pricing
                    WHERE ai_service = 'suno'
                      AND operation_type IN ('music', 'music_generation')
                      AND COALESCE(sub_model, '') IN ('V5_5', 'V5')
                    ORDER BY (COALESCE(sub_model, '') = 'V5_5') DESC
                    LIMIT 1
                ),
                (
                    SELECT external_cost_cents FROM credit_pricing
                    WHERE ai_service = 'suno'
                      AND operation_type IN ('music', 'music_generation')
                      AND COALESCE(sub_model, '') = ''
                    LIMIT 1
                ),
                60000
            ),
            true,
            NOW(),
            NOW()
        FROM (VALUES ('V6'), ('V6_MINI'), ('V6_WILD')) AS v(model_id)
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing cp
            WHERE cp.ai_service = 'suno'
              AND cp.operation_type IN ('music', 'music_generation')
              AND COALESCE(cp.sub_model, '') = v.model_id
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE ai_service = 'suno'
          AND operation_type IN ('music', 'music_generation')
          AND COALESCE(sub_model, '') IN ('V6', 'V6_MINI', 'V6_WILD')
        """
    )
