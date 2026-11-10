"""Creator payouts: KYC, payout accounts, earnings, and payout requests.

Revision ID: 191
Revises: 190
"""

from __future__ import annotations

from alembic import op

revision = "191"
down_revision = "190"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_kyc (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            legal_name VARCHAR(120) NOT NULL,
            date_of_birth DATE NOT NULL,
            country_code CHAR(2) NOT NULL,
            id_type VARCHAR(30) NOT NULL,
            id_last4 CHAR(4) NOT NULL,
            id_document_ref TEXT NOT NULL,
            selfie_ref TEXT,
            tax_id VARCHAR(40),
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','verified','rejected','expired')),
            submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TIMESTAMPTZ,
            reason TEXT,
            expires_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_kyc_status "
        "ON creator_kyc (status, submitted_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_payout_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            method VARCHAR(20) NOT NULL
                CHECK (method IN ('aba','wing','khqr','bank','paypal','wise')),
            account_name VARCHAR(120) NOT NULL,
            account_last4 CHAR(4) NOT NULL,
            bank_code VARCHAR(30),
            currency CHAR(3) NOT NULL DEFAULT 'USD',
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','verified','rejected','disabled')),
            verified_at TIMESTAMPTZ,
            is_default BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_payout_default "
        "ON creator_payout_accounts (user_id) WHERE is_default"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_earnings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source VARCHAR(20) NOT NULL
                CHECK (source IN ('royalty','tip','download','license','marketplace','service','bonus','adjustment')),
            source_id TEXT,
            period DATE,
            gross_micros BIGINT NOT NULL DEFAULT 0,
            fee_micros BIGINT NOT NULL DEFAULT 0,
            net_micros BIGINT NOT NULL DEFAULT 0,
            currency CHAR(3) NOT NULL DEFAULT 'USD',
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','available','held','paid','clawed_back')),
            available_at TIMESTAMPTZ,
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_earnings_creator "
        "ON creator_earnings (creator_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_earnings_status "
        "ON creator_earnings (status, available_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_payouts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            amount_micros BIGINT NOT NULL,
            currency CHAR(3) NOT NULL DEFAULT 'USD',
            method VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'requested'
                CHECK (status IN ('requested','approved','processing','paid','failed','cancelled')),
            requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMPTZ,
            paid_at TIMESTAMPTZ,
            payment_ref VARCHAR(120),
            statement_key TEXT,
            failure_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (creator_id, period_start, period_end)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_payouts_status "
        "ON creator_payouts (status, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS creator_payouts CASCADE")
    op.execute("DROP TABLE IF EXISTS creator_earnings CASCADE")
    op.execute("DROP TABLE IF EXISTS creator_payout_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS creator_kyc CASCADE")
