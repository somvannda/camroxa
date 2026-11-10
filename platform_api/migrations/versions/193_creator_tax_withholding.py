"""Tax withholding on creator payouts and annual statements.

Revision ID: 193
Revises: 192
"""

from __future__ import annotations

from alembic import op

revision = "193"
down_revision = "192"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tax profile captured alongside payout KYC.
    op.execute(
        "ALTER TABLE creator_kyc "
        "ADD COLUMN IF NOT EXISTS tax_form VARCHAR(10)"
    )
    op.execute(
        "ALTER TABLE creator_kyc "
        "ADD COLUMN IF NOT EXISTS tax_country CHAR(2)"
    )
    op.execute(
        "ALTER TABLE creator_kyc "
        "ADD COLUMN IF NOT EXISTS withholding_rate_bps INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE creator_kyc ADD CONSTRAINT creator_kyc_tax_form_check "
        "CHECK (tax_form IS NULL OR tax_form IN ('w9','w8ben')) NOT VALID; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE creator_kyc ADD CONSTRAINT creator_kyc_withholding_check "
        "CHECK (withholding_rate_bps BETWEEN 0 AND 3000) NOT VALID; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # Keep the gross and withheld amounts next to the net payout.
    op.execute(
        "ALTER TABLE creator_payouts "
        "ADD COLUMN IF NOT EXISTS gross_micros BIGINT NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE creator_payouts "
        "ADD COLUMN IF NOT EXISTS withheld_micros BIGINT NOT NULL DEFAULT 0"
    )
    op.execute(
        "UPDATE creator_payouts SET gross_micros = amount_micros "
        "WHERE gross_micros = 0 AND withheld_micros = 0"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_tax_statements (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tax_year INTEGER NOT NULL,
            currency VARCHAR(3) NOT NULL DEFAULT 'USD',
            gross_micros BIGINT NOT NULL DEFAULT 0,
            withheld_micros BIGINT NOT NULL DEFAULT 0,
            net_micros BIGINT NOT NULL DEFAULT 0,
            payout_count INTEGER NOT NULL DEFAULT 0,
            tax_form VARCHAR(10),
            tax_country CHAR(2),
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (creator_id, tax_year)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_tax_statements_year "
        "ON creator_tax_statements (tax_year, creator_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_creator_tax_statements_year")
    op.execute("DROP TABLE IF EXISTS creator_tax_statements")
    op.execute(
        "ALTER TABLE creator_payouts DROP COLUMN IF EXISTS withheld_micros"
    )
    op.execute("ALTER TABLE creator_payouts DROP COLUMN IF EXISTS gross_micros")
    op.execute(
        "ALTER TABLE creator_kyc DROP CONSTRAINT IF EXISTS creator_kyc_withholding_check"
    )
    op.execute(
        "ALTER TABLE creator_kyc DROP CONSTRAINT IF EXISTS creator_kyc_tax_form_check"
    )
    op.execute(
        "ALTER TABLE creator_kyc DROP COLUMN IF EXISTS withholding_rate_bps"
    )
    op.execute("ALTER TABLE creator_kyc DROP COLUMN IF EXISTS tax_country")
    op.execute("ALTER TABLE creator_kyc DROP COLUMN IF EXISTS tax_form")
