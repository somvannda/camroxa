"""User reports for web-music clips.

Suno's song menu has a Report action; ours had none. Store one row per
(user, clip, reason) so repeated taps are idempotent and ops can triage.

Revision ID: 173_web_music_reports
Revises: 172_web_music_dislikes
"""

from __future__ import annotations

from alembic import op

revision: str = "173_web_music_reports"
down_revision: str | None = "172_web_music_dislikes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_music_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            task_id UUID NOT NULL REFERENCES suno_tasks(id) ON DELETE CASCADE,
            variant TEXT NOT NULL,
            reason TEXT NOT NULL,
            details TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, task_id, variant, reason)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_web_music_reports_status
            ON web_music_reports (status, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_web_music_reports_status")
    op.execute("DROP TABLE IF EXISTS web_music_reports")
