"""Terminal state for Suno MP3 channels whose source URL is permanently dead.

Suno's ``tempfile.aiquickdraw.com/r/{audio_id}.mp3`` host is short-lived (and
sometimes the guessed path is wrong from the start). When a channel's URL is
gone and no durable Backblaze copy exists, the desktop pending-download queue
used to retry it forever. These flags let ``/music/downloads/pending`` stop
returning a channel the server has confirmed dead, so the client can finish.

Revision ID: 120_suno_download_unavailable
Revises: 119_plan_pricing_credit_lines
Create Date: 2026-09-17
"""

from __future__ import annotations

from alembic import op

revision = "120_suno_download_unavailable"
down_revision = "119_plan_pricing_credit_lines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS download_unavailable_ok BOOLEAN NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS download_unavailable_alt BOOLEAN NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS download_unavailable_at_ok TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS download_unavailable_at_alt TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS download_unavailable_ok,
        DROP COLUMN IF EXISTS download_unavailable_alt,
        DROP COLUMN IF EXISTS download_unavailable_at_ok,
        DROP COLUMN IF EXISTS download_unavailable_at_alt
        """
    )
