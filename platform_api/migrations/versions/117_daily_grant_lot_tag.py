"""Allow daily_grant wallet lots (Free plan daily mint).

Revision ID: 117
Revises: 116
Create Date: 2026-08-25
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "117_daily_grant_lot_tag"
down_revision: Union[str, None] = "116_credits_only_v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_wallet_lots_daily_grant
            ON credit_wallet_lots (user_id, period_start)
            WHERE tag = 'daily_grant' AND period_start IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_credit_wallet_lots_daily_grant")
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
            CHECK (tag IN ('grant', 'quota_conversion', 'pack', 'admin'))
        """
    )
