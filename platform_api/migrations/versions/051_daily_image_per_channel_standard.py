"""Align daily image limits: 2 per channel (1 BG + 1 TH), account daily = channels × 2."""

from alembic import op

revision = "051_daily_image_per_channel_standard"
down_revision = "050_channel_plan_billing_terms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET daily_image_limit_per_channel = 2,
            monthly_image_limit = profile_allowance * 60,
            updated_at = NOW()
        WHERE billing_cycle_days IN (30, 180, 365)
          AND profile_allowance >= 2
        """
    )


def downgrade() -> None:
    pass
