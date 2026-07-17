"""Add planned date range columns to batches."""

from alembic import op

revision = "005_add_batch_planned_date_range"
down_revision = "004_credit_pricing_redesign"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE batches
        ADD COLUMN IF NOT EXISTS planned_from_date DATE
        """
    )
    op.execute(
        """
        ALTER TABLE batches
        ADD COLUMN IF NOT EXISTS planned_to_date DATE
        """
    )
    op.execute(
        """
        UPDATE batches
        SET
            planned_from_date = COALESCE(planned_from_date, DATE(created_at)),
            planned_to_date = COALESCE(planned_to_date, DATE(created_at))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE batches
        DROP COLUMN IF EXISTS planned_to_date
        """
    )
    op.execute(
        """
        ALTER TABLE batches
        DROP COLUMN IF EXISTS planned_from_date
        """
    )
