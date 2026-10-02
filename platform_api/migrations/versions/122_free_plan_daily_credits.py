"""Make the Free plan daily-credit based (50/day) instead of a monthly grant.

The Free plan row carried monthly_credits=50 with daily_credits=0, so the v3
period-grant service minted a month-long `grant` lot for Free users. That lot
occupies the unique (user_id, period_start) period-grant slot, so when the same
user upgraded to a paid plan on the same day the paid grant was skipped as
"already_granted". Free is meant to be 50 daily credits (separate `daily_grant`
slot), never a period grant.

Revision ID: 122_free_plan_daily_credits
Revises: 121_upload_job_permanent_failed
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op

revision = "122_free_plan_daily_credits"
down_revision = "121_upload_job_permanent_failed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET monthly_credits = 0,
            daily_credits = 50,
            updated_at = NOW()
        WHERE lower(name) = 'free'
          AND COALESCE(price_cents, 0) <= 0
          AND is_active = true
          AND (COALESCE(monthly_credits, 0) <> 0 OR COALESCE(daily_credits, 0) <> 50)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plans
        SET monthly_credits = 50,
            daily_credits = 0,
            updated_at = NOW()
        WHERE lower(name) = 'free'
          AND COALESCE(price_cents, 0) <= 0
          AND is_active = true
        """
    )
