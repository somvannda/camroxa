"""Collaborator presence for editable Studio shares.

Revision ID: 157_studio_presence
Revises: 156_studio_share_permission
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "157_studio_presence"
down_revision: str | None = "156_studio_share_permission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_project_presence (
            project_id UUID NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            display_name TEXT NOT NULL DEFAULT 'Collaborator',
            last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (project_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_project_presence_seen_idx
            ON studio_project_presence (project_id, last_seen DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_project_presence")
