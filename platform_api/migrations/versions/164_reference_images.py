"""Add reference images to web-music generations.

Revision ID: 164_reference_images
Revises: 163_studio_presence_playhead
"""

from __future__ import annotations

from alembic import op

revision: str = "164_reference_images"
down_revision: str | None = "163_studio_presence_playhead"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS reference_image_urls JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS reference_image_urls")
