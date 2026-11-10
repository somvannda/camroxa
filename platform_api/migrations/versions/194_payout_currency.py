"""Payout currency conversion for KHR and USD.

Revision ID: 194
Revises: 193
"""

from __future__ import annotations

from alembic import op

revision = "194"
down_revision = "193"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The ledger stays in USD micros; a payout records the currency it is sent
    # in plus the rate used, so a KHR transfer can still be reconciled.
    op.execute(
        "ALTER TABLE creator_payouts "
        "ADD COLUMN IF NOT EXISTS fx_rate NUMERIC(18,8) NOT NULL DEFAULT 1"
    )
    op.execute(
        "ALTER TABLE creator_payouts "
        "ADD COLUMN IF NOT EXISTS payout_amount_minor BIGINT NOT NULL DEFAULT 0"
    )
    op.execute(
        "UPDATE creator_payouts SET payout_amount_minor = (amount_micros / 10000) "
        "WHERE payout_amount_minor = 0 AND amount_micros > 0"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE creator_payouts ADD CONSTRAINT creator_payouts_currency_check "
        "CHECK (currency IN ('USD','KHR')) NOT VALID; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE creator_payouts DROP CONSTRAINT IF EXISTS creator_payouts_currency_check"
    )
    op.execute(
        "ALTER TABLE creator_payouts DROP COLUMN IF EXISTS payout_amount_minor"
    )
    op.execute("ALTER TABLE creator_payouts DROP COLUMN IF EXISTS fx_rate")
