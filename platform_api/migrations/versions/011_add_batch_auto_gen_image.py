"""Add batch auto image flag."""

from alembic import op

revision = "011_add_batch_auto_gen_image"
down_revision = "010_content_pool_reservations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE batches
        ADD COLUMN IF NOT EXISTS auto_gen_image BOOLEAN NOT NULL DEFAULT false
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE batches
        DROP COLUMN IF EXISTS auto_gen_image
        """
    )
