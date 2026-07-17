"""Scheduled subscription downgrades at renewal."""

from alembic import op

revision = "056_license_pending_plan_change"
down_revision = "055_plan_term_discounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE licenses
            ADD COLUMN IF NOT EXISTS pending_plan_id UUID REFERENCES plans(id),
            ADD COLUMN IF NOT EXISTS pending_plan_effective_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE licenses
            DROP COLUMN IF EXISTS pending_plan_effective_at,
            DROP COLUMN IF EXISTS pending_plan_id
        """
    )
