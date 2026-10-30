"""Store the Suno Studio project id on the local project index.

Revision ID: 174_studio_project_suno_id
Revises: 173_web_music_reports
"""

from __future__ import annotations

from alembic import op

revision: str = "174_studio_project_suno_id"
down_revision: str | None = "173_web_music_reports"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_projects
            ADD COLUMN IF NOT EXISTS suno_project_id VARCHAR(64)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_projects_suno_id_idx
            ON studio_projects (user_id, suno_project_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS studio_projects_suno_id_idx")
    op.execute(
        "ALTER TABLE studio_projects DROP COLUMN IF EXISTS suno_project_id"
    )
