"""Add image job reference fields for chained generation."""

from alembic import op

revision = "013_image_job_reference_fields"
down_revision = "012_add_batch_auto_gsuno"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE image_jobs
        ADD COLUMN IF NOT EXISTS input_image_path TEXT,
        ADD COLUMN IF NOT EXISTS style_reference_path TEXT,
        ADD COLUMN IF NOT EXISTS source_job_id UUID
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_jobs_source_job_id
        ON image_jobs(source_job_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_image_jobs_source_job_id")
    op.execute(
        """
        ALTER TABLE image_jobs
        DROP COLUMN IF EXISTS source_job_id,
        DROP COLUMN IF EXISTS style_reference_path,
        DROP COLUMN IF EXISTS input_image_path
        """
    )
