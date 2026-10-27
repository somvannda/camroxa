"""Add tags to Studio projects.

Revision ID: 161_studio_project_tags
Revises: 160_studio_project_pinning
"""

from __future__ import annotations

from alembic import op

revision: str = "161_studio_project_tags"
down_revision: str | None = "160_studio_project_pinning"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_projects
            ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_projects_tags_idx
            ON studio_projects USING GIN (tags)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS studio_projects_tags_idx")
    op.execute("ALTER TABLE studio_projects DROP COLUMN IF EXISTS tags")
