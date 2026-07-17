"""Add metadata JSONB to credit_transactions for rich usage auditing."""

from __future__ import annotations

from alembic import op

revision = "031_credit_transaction_metadata"
down_revision = "030_plan_included_wallet_credits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE credit_transactions
        ADD COLUMN IF NOT EXISTS metadata JSONB
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_credit_txn_metadata_provider
        ON credit_transactions ((metadata->>'provider'))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_credit_txn_metadata_operation
        ON credit_transactions ((metadata->>'operation'))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_credit_txn_metadata_operation")
    op.execute("DROP INDEX IF EXISTS idx_credit_txn_metadata_provider")
    op.execute("ALTER TABLE credit_transactions DROP COLUMN IF EXISTS metadata")
