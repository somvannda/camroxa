"""Seed credit pricing for web music AI style generation.

Revision ID: 093_web_music_style_pricing
Revises: 092_web_music_workspaces
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "093_web_music_style_pricing"
down_revision = "092_web_music_workspaces"
branch_labels = None
depends_on = None


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
            'openai',
            'web_music_style',
            'gpt-4o-mini',
            2,
            0,
            true,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'openai'
              AND operation_type = 'web_music_style'
              AND COALESCE(sub_model, '') = 'gpt-4o-mini'
        )
        """
    )
    op.execute(
        """
        INSERT INTO credit_pricing (
            id, ai_service, operation_type, sub_model,
            credits_per_operation, external_cost_cents, needs_review,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'deepseek',
            'web_music_style',
            'deepseek-chat',
            1,
            0,
            true,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'deepseek'
              AND operation_type = 'web_music_style'
              AND COALESCE(sub_model, '') = 'deepseek-chat'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM credit_pricing
        WHERE operation_type = 'web_music_style'
        """
    )
