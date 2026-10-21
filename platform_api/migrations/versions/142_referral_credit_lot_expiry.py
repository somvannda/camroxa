"""30-day expiry for referral reward credits.

Referral rewards are universal wallet credits, but they should not outlive the
normal 30-day credit term. This adds a ``referral`` wallet lot (with a stable
``ref_id`` for idempotency) so the existing grant-expiry sweep claws back unused
referral credits exactly like pack credits.

Revision ID: 142_referral_credit_lot_expiry
Revises: 141_telegram_ops_messages
Create Date: 2026-10-21
"""

from alembic import op

revision = "142_referral_credit_lot_expiry"
down_revision = "141_telegram_ops_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE credit_wallet_lots
            ADD COLUMN IF NOT EXISTS ref_id TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE credit_wallet_lots
            DROP CONSTRAINT IF EXISTS credit_wallet_lots_tag_check
        """
    )
    op.execute(
        """
        ALTER TABLE credit_wallet_lots
            ADD CONSTRAINT credit_wallet_lots_tag_check
            CHECK (tag IN ('grant', 'daily_grant', 'quota_conversion', 'pack', 'admin', 'referral'))
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_wallet_lots_referral_ref
            ON credit_wallet_lots (user_id, ref_id)
            WHERE tag = 'referral' AND ref_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_credit_wallet_lots_referral_ref")
    op.execute("DELETE FROM credit_wallet_lots WHERE tag = 'referral'")
    op.execute(
        """
        ALTER TABLE credit_wallet_lots
            DROP CONSTRAINT IF EXISTS credit_wallet_lots_tag_check
        """
    )
    op.execute(
        """
        ALTER TABLE credit_wallet_lots
            ADD CONSTRAINT credit_wallet_lots_tag_check
            CHECK (tag IN ('grant', 'daily_grant', 'quota_conversion', 'pack', 'admin'))
        """
    )
    op.execute("ALTER TABLE credit_wallet_lots DROP COLUMN IF EXISTS ref_id")
