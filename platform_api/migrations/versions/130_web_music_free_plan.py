"""Seed the web-music Free plan if it does not already exist.

Production already has an admin-managed Free row (50 credits/month), so this is
idempotent and case-insensitive: it only inserts when no plan named "free"
exists. Fresh/sandbox databases get the Free tier so the public pricing page
renders all five columns (Free + the four paid tiers).

Revision ID: 130_web_music_free_plan
Revises: 129_web_music_real_economics
Create Date: 2026-10-04
"""

from __future__ import annotations

from alembic import op

revision = "130_web_music_free_plan"
down_revision = "129_web_music_real_economics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO plans (
            name, plan_type, price_cents, billing_cycle_days, monthly_credits,
            daily_credits, profile_allowance, monthly_song_limit,
            daily_song_limit_per_channel, features, is_public, display_order,
            is_active, pricing_features, pricing_credit_lines
        )
        SELECT
            'free', 'web_music', 0, 30, 50,
            0, 1, NULL,
            999, '{"music": true, "images": true, "topup": true}'::jsonb,
            true, 0, true,
            ARRAY['Web Create', 'Monthly credit reset', 'Top-up packs']::text[],
            '{}'::text[]
        WHERE NOT EXISTS (
            SELECT 1 FROM plans WHERE lower(name) = 'free'
        )
        """
    )


def downgrade() -> None:
    # Only remove a Free row this migration could have created; leave an
    # admin-managed one alone by checking it carries the seeded marker values.
    op.execute(
        """
        DELETE FROM plans
        WHERE lower(name) = 'free'
          AND plan_type = 'web_music'
          AND price_cents = 0
          AND monthly_credits = 50
        """
    )
