"""Unify web music free tier as daily credits (50/day = 5 songs).

Revision ID: 095_web_music_daily_credits
Revises: 094_web_music_lyrics_pricing
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "095_web_music_daily_credits"
down_revision = "094_web_music_lyrics_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE web_music_daily_usage
            ADD COLUMN IF NOT EXISTS credits_used INTEGER NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        UPDATE web_music_daily_usage
        SET credits_used = generation_count * 10
        WHERE credits_used = 0 AND generation_count > 0
        """
    )
    op.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ('web_music_free_daily_credits', 'int', '50', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'web_music_free_daily_credits'")
    op.execute(
        """
        ALTER TABLE web_music_daily_usage
            DROP COLUMN IF EXISTS credits_used
        """
    )
