"""Invite-a-friend referral program for music.camxora.com.

Adds a per-user referral code and a ``referrals`` table linking an inviter to a
brand-new invitee. Rewards are paid only after the invitee's **first paid credit
pack** is fulfilled; the invite row is the idempotency guard.

Revision ID: 139_referral_program
Revises: 138_users_email_lower_unique
Create Date: 2026-10-20
"""

from alembic import op

revision = "139_referral_program"
down_revision = "138_users_email_lower_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS referral_code VARCHAR(16)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_referral_code
            ON users (referral_code)
            WHERE referral_code IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            inviter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invitee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invitee_email VARCHAR(255) NOT NULL,
            code VARCHAR(16) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'rewarded', 'skipped', 'rejected')),
            -- First paid pack purchase that qualified (or would have qualified).
            -- Stored as text so the same table serves topup_purchases and the
            -- legacy billing_payments path without a cross-table FK.
            qualifying_ref VARCHAR(64),
            purchased_credits INTEGER,
            inviter_reward INTEGER NOT NULL DEFAULT 0,
            invitee_reward INTEGER NOT NULL DEFAULT 0,
            invited_ip VARCHAR(64),
            rewarded_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            -- One referral per invited account; retried OAuth callbacks and
            -- duplicate signup attempts can never create a second reward path.
            UNIQUE (invitee_id)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_referrals_inviter
            ON referrals (inviter_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_referrals_status
            ON referrals (status, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS referrals")
    op.execute("DROP INDEX IF EXISTS uq_users_referral_code")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS referral_code")
