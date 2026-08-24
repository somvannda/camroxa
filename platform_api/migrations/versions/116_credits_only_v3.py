"""Credits-only API v3: plan per-op amounts, wallet lots, conversion runs.

Revision ID: 116_credits_only_v3
Revises: 115_hls_playback
Create Date: 2026-08-22

Additive only. Existing /api/v1 routers ignore these columns/tables.
"""

from __future__ import annotations

from alembic import op

revision = "116_credits_only_v3"
down_revision = "115_hls_playback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS daily_credits INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS lyric_credits INTEGER,
            ADD COLUMN IF NOT EXISTS title_credits INTEGER,
            ADD COLUMN IF NOT EXISTS album_credits INTEGER,
            ADD COLUMN IF NOT EXISTS music_credits INTEGER,
            ADD COLUMN IF NOT EXISTS style_credits INTEGER,
            ADD COLUMN IF NOT EXISTS image_credits INTEGER,
            ADD COLUMN IF NOT EXISTS video_credits INTEGER,
            ADD COLUMN IF NOT EXISTS merge_credits INTEGER
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_wallet_lots (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            amount_units BIGINT NOT NULL,
            remaining_units BIGINT NOT NULL,
            expires_at TIMESTAMPTZ,
            period_start DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT credit_wallet_lots_tag_check
                CHECK (tag IN ('grant', 'quota_conversion', 'pack', 'admin')),
            CONSTRAINT credit_wallet_lots_remaining_check
                CHECK (remaining_units >= 0 AND remaining_units <= amount_units)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_credit_wallet_lots_user
            ON credit_wallet_lots (user_id, tag, expires_at)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_wallet_lots_period_grant
            ON credit_wallet_lots (user_id, period_start)
            WHERE tag = 'grant' AND period_start IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_conversion_runs (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id UUID REFERENCES plans(id) ON DELETE SET NULL,
            leftover_packages INTEGER NOT NULL,
            credits_minted INTEGER NOT NULL,
            amount_units BIGINT NOT NULL,
            status TEXT NOT NULL,
            dry_run BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT billing_conversion_runs_status_check
                CHECK (status IN ('dry_run', 'applied', 'skipped'))
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_conversion_applied_user
            ON billing_conversion_runs (user_id)
            WHERE status = 'applied'
        """
    )
    # If this ran as postgres (sandbox hotfix), the API user still needs access.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'camxora') THEN
                EXECUTE 'ALTER TABLE credit_wallet_lots OWNER TO camxora';
                EXECUTE 'ALTER TABLE billing_conversion_runs OWNER TO camxora';
                EXECUTE 'GRANT ALL PRIVILEGES ON TABLE credit_wallet_lots TO camxora';
                EXECUTE 'GRANT ALL PRIVILEGES ON TABLE billing_conversion_runs TO camxora';
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing_conversion_runs")
    op.execute("DROP TABLE IF EXISTS credit_wallet_lots")
    op.execute(
        """
        ALTER TABLE plans
            DROP COLUMN IF EXISTS daily_credits,
            DROP COLUMN IF EXISTS lyric_credits,
            DROP COLUMN IF EXISTS title_credits,
            DROP COLUMN IF EXISTS album_credits,
            DROP COLUMN IF EXISTS music_credits,
            DROP COLUMN IF EXISTS style_credits,
            DROP COLUMN IF EXISTS image_credits,
            DROP COLUMN IF EXISTS video_credits,
            DROP COLUMN IF EXISTS merge_credits
        """
    )
