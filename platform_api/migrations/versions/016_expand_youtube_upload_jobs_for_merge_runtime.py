"""Expand youtube_upload_jobs for merge-runtime parity."""

from alembic import op

revision = "016_expand_youtube_upload_jobs_for_merge_runtime"
down_revision = "015_batch_channel_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE youtube_upload_jobs
        ADD COLUMN IF NOT EXISTS job_uid VARCHAR(180),
        ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES batches(id),
        ADD COLUMN IF NOT EXISTS profile_id UUID REFERENCES channel_profiles(id),
        ADD COLUMN IF NOT EXISTS role VARCHAR(20),
        ADD COLUMN IF NOT EXISTS file_path TEXT,
        ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS youtube_url TEXT
        """
    )
    op.execute(
        """
        UPDATE youtube_upload_jobs
        SET role = UPPER(role)
        WHERE role IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_youtube_upload_jobs_job_uid
        ON youtube_upload_jobs(job_uid)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_youtube_upload_jobs_batch_profile_role
        ON youtube_upload_jobs(user_id, batch_id, profile_id, role)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_youtube_upload_jobs_batch_profile_role")
    op.execute("DROP INDEX IF EXISTS idx_youtube_upload_jobs_job_uid")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS youtube_url")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS attempt_count")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS file_path")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS role")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS profile_id")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS batch_id")
    op.execute("ALTER TABLE youtube_upload_jobs DROP COLUMN IF EXISTS job_uid")
