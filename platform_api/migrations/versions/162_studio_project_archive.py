"""Add archive flag to Studio projects.

Revision ID: 162_studio_project_archive
Revises: 161_studio_project_tags
"""

from __future__ import annotations

from alembic import op

revision: str = "162_studio_project_archive"
down_revision: str | None = "161_studio_project_tags"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_projects
            ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_projects_archived_idx
            ON studio_projects (user_id, archived, updated_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS studio_projects_archived_idx")
    op.execute("ALTER TABLE studio_projects DROP COLUMN IF EXISTS archived")
