"""Comments on shared Studio projects.

Revision ID: 155_studio_project_comments
Revises: 154_studio_project_shares
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "155_studio_project_comments"
down_revision: str | None = "154_studio_project_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_project_comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
            user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
            author_name TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_project_comments_project_created_idx
            ON studio_project_comments (project_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_project_comments")
