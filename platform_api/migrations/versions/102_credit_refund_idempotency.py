"""Credit refund idempotency index for web music.

Revision ID: 102_credit_refund_idempotency
Revises: 101_web_music_b2_lrc_storage
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "102_credit_refund_idempotency"
down_revision = "101_web_music_b2_lrc_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_txn_refund_idempotency
        ON credit_transactions (user_id, ref_id, reason)
        WHERE direction = 'credit'
          AND ref_id IS NOT NULL
          AND reason LIKE 'refunded_%'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_credit_txn_refund_idempotency")
