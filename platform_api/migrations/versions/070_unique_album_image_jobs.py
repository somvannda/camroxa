"""Unique album image jobs per batch/channel/kind (dedupe race)."""

from __future__ import annotations

from alembic import op

revision = "070_unique_album_image_jobs"
down_revision = "069_music_moods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the earliest job per album slot; concurrent Suno callbacks could insert
    # duplicates before application-level dedupe saw them.
    op.execute(
        """
        DELETE FROM image_jobs
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY batch_id, profile_id, kind, channel_role
                           ORDER BY created_at ASC, id ASC
                       ) AS rn
                FROM image_jobs
                WHERE batch_id IS NOT NULL
                  AND profile_id IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_image_jobs_album_channel_kind
        ON image_jobs (batch_id, profile_id, kind, channel_role)
        WHERE batch_id IS NOT NULL AND profile_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_image_jobs_album_channel_kind")
