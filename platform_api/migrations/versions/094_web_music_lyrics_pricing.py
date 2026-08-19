"""Fix web music AI assist pricing to micro-credit units and add lyrics operation.

Revision ID: 094_web_music_lyrics_pricing
Revises: 093_web_music_style_pricing
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "094_web_music_lyrics_pricing"
down_revision = "093_web_music_style_pricing"
branch_labels = None
depends_on = None

# 1 display credit = 10_000 micro-units
_STYLE_UNITS = 20_000  # 2 display credits
_LYRICS_UNITS = 30_000  # 3 display credits


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE credit_pricing
        SET credits_per_operation = {_STYLE_UNITS}, updated_at = NOW()
        WHERE operation_type = 'web_music_style'
          AND credits_per_operation < 1000
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
            'openai',
            'web_music_lyrics',
            'gpt-4o-mini',
            30000,
            0,
            true,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'openai'
              AND operation_type = 'web_music_lyrics'
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
            'web_music_lyrics',
            'deepseek-chat',
            20000,
            0,
            true,
            NOW(),
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_pricing
            WHERE ai_service = 'deepseek'
              AND operation_type = 'web_music_lyrics'
              AND COALESCE(sub_model, '') = 'deepseek-chat'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM credit_pricing WHERE operation_type = 'web_music_lyrics'")
