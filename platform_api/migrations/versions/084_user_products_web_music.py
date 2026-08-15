"""User product tags, web-music Suno source, and daily free-generation cap.

Revision ID: 084_user_products_web_music
Revises: 083_image_fallback_drop_openai
Create Date: 2026-08-15
"""

from __future__ import annotations

from alembic import op

revision = "084_user_products_web_music"
down_revision = "083_image_fallback_drop_openai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS products TEXT[] NOT NULL DEFAULT '{}'
        """
    )
    op.execute(
        """
        UPDATE users
        SET products = ARRAY['studio']::text[]
        WHERE products IS NULL OR cardinality(products) = 0
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'studio'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_daily_usage (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            usage_date DATE NOT NULL,
            generation_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, usage_date)
        )
        """
    )
    op.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ('web_music_free_daily_limit', 'int', '5', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'web_music_free_daily_limit'")
    op.execute("DROP TABLE IF EXISTS web_music_daily_usage")
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS products")
