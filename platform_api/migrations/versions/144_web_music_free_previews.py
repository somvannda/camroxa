"""Web-music free-tier premium previews.

Revision ID: 144_web_music_free_previews
Revises: 143_platform_mail
Create Date: 2026-10-21
"""

from __future__ import annotations

from alembic import op

revision: str = "144_web_music_free_previews"
down_revision: str | None = "143_platform_mail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS is_preview BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS preview_seconds INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS preview_released BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_tasks_web_music_preview
            ON suno_tasks (user_id, created_at)
            WHERE is_preview = TRUE
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_preview_entitlements (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_start DATE NOT NULL,
            model TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
            PRIMARY KEY (user_id, period_start, model)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS web_music_preview_entitlements")
    op.execute(
        "DROP INDEX IF EXISTS idx_suno_tasks_web_music_preview"
    )
    op.execute(
        "ALTER TABLE suno_tasks DROP COLUMN IF EXISTS preview_seconds"
    )
    op.execute(
        "ALTER TABLE suno_tasks DROP COLUMN IF EXISTS preview_released"
    )
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS is_preview")
