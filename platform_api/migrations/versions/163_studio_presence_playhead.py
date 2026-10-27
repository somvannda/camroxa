"""Add collaborator playhead fields to Studio presence.

Revision ID: 163_studio_presence_playhead
Revises: 162_studio_project_archive
"""

from __future__ import annotations

from alembic import op

revision: str = "163_studio_presence_playhead"
down_revision: str | None = "162_studio_project_archive"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_project_presence
            ADD COLUMN IF NOT EXISTS playhead_seconds DOUBLE PRECISION NULL
        """
    )
    op.execute(
        """
        ALTER TABLE studio_project_presence
            ADD COLUMN IF NOT EXISTS selected_lane_id TEXT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE studio_project_presence DROP COLUMN IF EXISTS selected_lane_id"
    )
    op.execute(
        "ALTER TABLE studio_project_presence DROP COLUMN IF EXISTS playhead_seconds"
    )
