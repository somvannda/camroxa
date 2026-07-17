"""Add batch auto GSuno flag."""

from alembic import op

revision = "012_add_batch_auto_gsuno"
down_revision = "011_add_batch_auto_gen_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE batches
        ADD COLUMN IF NOT EXISTS auto_gsuno BOOLEAN NOT NULL DEFAULT false
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE batches
        DROP COLUMN IF EXISTS auto_gsuno
        """
    )
