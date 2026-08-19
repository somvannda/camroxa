"""Add web_music_workspaces and link suno_tasks to workspaces.

Revision ID: 092_web_music_workspaces
Revises: 091_topup_purchases
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "092_web_music_workspaces"
down_revision = "091_topup_purchases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_workspaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(120) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_workspaces_user_id
        ON web_music_workspaces (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_web_music_workspaces_user_default
        ON web_music_workspaces (user_id)
        WHERE is_default = true
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS workspace_id UUID
        REFERENCES web_music_workspaces(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_tasks_workspace_id
        ON suno_tasks (workspace_id)
        WHERE workspace_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO web_music_workspaces (user_id, name, is_default)
        SELECT DISTINCT st.user_id, 'My Workspace', true
        FROM suno_tasks st
        WHERE st.source = 'web_music'
          AND NOT EXISTS (
              SELECT 1 FROM web_music_workspaces w WHERE w.user_id = st.user_id
          )
        """
    )
    op.execute(
        """
        UPDATE suno_tasks st
        SET workspace_id = w.id
        FROM web_music_workspaces w
        WHERE st.user_id = w.user_id
          AND w.is_default = true
          AND st.source = 'web_music'
          AND st.workspace_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS workspace_id")
    op.execute("DROP TABLE IF EXISTS web_music_workspaces")
