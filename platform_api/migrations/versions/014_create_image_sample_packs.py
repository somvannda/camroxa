"""Create image sample pack catalog for admin-managed downloads."""

from alembic import op

revision = "014_create_image_sample_packs"
down_revision = "013_image_job_reference_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_sample_packs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_value TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            version_label TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_sample_packs_category_sort
        ON image_sample_packs(category, sort_order, lower(name))
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_image_sample_packs_category_name
        ON image_sample_packs(category, lower(name))
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS image_sample_packs")
