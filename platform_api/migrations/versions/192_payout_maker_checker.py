"""Payout maker-checker: record who created a payout.

Revision ID: 192
Revises: 191
"""

from __future__ import annotations

from alembic import op

revision = "192"
down_revision = "191"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE creator_payouts "
        "ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_payouts_created_by "
        "ON creator_payouts (created_by) WHERE created_by IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_creator_payouts_created_by")
    op.execute("ALTER TABLE creator_payouts DROP COLUMN IF EXISTS created_by")
