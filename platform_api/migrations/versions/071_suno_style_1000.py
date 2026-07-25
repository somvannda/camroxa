"""Expand suno_tasks.style to VARCHAR(1000) for V5/V5_5 style limit."""

from __future__ import annotations

from alembic import op

revision = "071_suno_style_1000"
down_revision = "070_unique_album_image_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Suno V4_5 / V5 / V5_5 accept style up to 1000 chars in customMode.
    # We previously mirrored an outdated VARCHAR(255) cap.
    op.execute(
        """
        ALTER TABLE suno_tasks
        ALTER COLUMN style TYPE VARCHAR(1000)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ALTER COLUMN style TYPE VARCHAR(255)
        USING LEFT(style, 255)
        """
    )
