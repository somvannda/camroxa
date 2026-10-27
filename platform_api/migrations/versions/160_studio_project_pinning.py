"""Add pinned flag to Studio projects.

Revision ID: 160_studio_project_pinning
Revises: 159_studio_comment_replies
"""

from __future__ import annotations

from alembic import op

revision: str = "160_studio_project_pinning"
down_revision: str | None = "159_studio_comment_replies"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_projects
            ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE studio_projects DROP COLUMN IF EXISTS pinned")
