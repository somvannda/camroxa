"""Add reference videos to web-music generations.

Suno's create composer lets a user attach one reference clip
(`video/mp4`, `video/quicktime`, `video/webm`) alongside the prompt. The
upload id travels as `user_uploaded_video_id`; Camxora stores the uploaded
URL and forwards it to musicapi as `videoUrls` (max 1). Mirrors
`164_reference_images`.

Revision ID: 168_reference_videos
Revises: 167_remix_staff_picks
"""

from __future__ import annotations

from alembic import op

revision: str = "168_reference_videos"
down_revision: str | None = "167_remix_staff_picks"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS reference_video_urls JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS reference_video_urls")
