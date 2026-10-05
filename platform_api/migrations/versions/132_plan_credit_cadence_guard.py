"""Enforce exclusive daily/monthly plan credit cadence; retire the legacy reset setting.

A plan grants **either** daily **or** monthly credits. Allowing both let
``ensure_daily_grant`` and ``ensure_period_grant`` both fire and double-credit.
This adds a CHECK so an invalid plan cannot be stored, and drops the retired
``music_web_free_reset_period`` setting now that the active Free plan row is the
single source of truth for the free cadence.

Revision ID: 132_plan_credit_cadence_guard
Revises: 131_camxora_music_api_music_default
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op

revision = "132_plan_credit_cadence_guard"
down_revision = "131_camxora_music_api_music_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE plans DROP CONSTRAINT IF EXISTS plans_credit_cadence_exclusive")
    op.execute(
        """
        ALTER TABLE plans
        ADD CONSTRAINT plans_credit_cadence_exclusive
        CHECK (NOT (COALESCE(daily_credits, 0) > 0 AND COALESCE(monthly_credits, 0) > 0))
        """
    )
    op.execute("DELETE FROM system_settings WHERE key = 'music_web_free_reset_period'")


def downgrade() -> None:
    op.execute("ALTER TABLE plans DROP CONSTRAINT IF EXISTS plans_credit_cadence_exclusive")
    op.execute(
        """
        INSERT INTO system_settings (key, value_type, value, updated_at)
        VALUES ('music_web_free_reset_period', 'string', 'monthly', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )
