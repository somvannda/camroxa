"""Add curated remix staff picks and allow catalog operations without a task.

Revision ID: 167_remix_staff_picks
Revises: 166_studio_lyrics
"""

from __future__ import annotations

from alembic import op

revision: str = "167_remix_staff_picks"
down_revision: str | None = "166_studio_lyrics"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS remix_staff_picks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provider_clip_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            image_url TEXT,
            styles TEXT,
            model TEXT,
            account_id TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS remix_staff_picks_active_idx
            ON remix_staff_picks (is_active, sort_order, created_at DESC)
        """
    )
    op.execute(
        "ALTER TABLE studio_operations ALTER COLUMN task_id DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS remix_staff_picks_active_idx")
    op.execute("DROP TABLE IF EXISTS remix_staff_picks")
