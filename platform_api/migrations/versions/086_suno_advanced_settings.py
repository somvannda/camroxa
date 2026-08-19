"""Add advanced Suno settings to suno_tasks table.

Revision ID: 086_suno_advanced_settings
Revises: 085_web_music_wav_support
Create Date: 2026-08-16
"""

from __future__ import annotations

from alembic import op

revision = "086_suno_advanced_settings"
down_revision = "085_web_music_wav_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS negative_tags TEXT,
        ADD COLUMN IF NOT EXISTS vocal_gender TEXT,
        ADD COLUMN IF NOT EXISTS style_weight NUMERIC(3, 2),
        ADD COLUMN IF NOT EXISTS weirdness_constraint NUMERIC(3, 2),
        ADD COLUMN IF NOT EXISTS audio_weight NUMERIC(3, 2)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS audio_weight,
        DROP COLUMN IF EXISTS weirdness_constraint,
        DROP COLUMN IF EXISTS style_weight,
        DROP COLUMN IF EXISTS vocal_gender,
        DROP COLUMN IF EXISTS negative_tags
        """
    )
