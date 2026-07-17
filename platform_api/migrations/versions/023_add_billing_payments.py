"""Add billing_payments table for hosted checkout purchases."""

from alembic import op

revision = "023_add_billing_payments"
down_revision = "022_music_languages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_payments (
            id UUID PRIMARY KEY,
            provider VARCHAR(32) NOT NULL,
            external_payment_id VARCHAR(128) NOT NULL UNIQUE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            offer_id UUID NULL REFERENCES plan_offers(id) ON DELETE SET NULL,
            reference_id VARCHAR(255) NOT NULL UNIQUE,
            status VARCHAR(32) NOT NULL,
            amount_cents INTEGER NOT NULL,
            currency VARCHAR(8) NOT NULL DEFAULT 'USD',
            checkout_url TEXT NOT NULL,
            approved_at TIMESTAMPTZ NULL,
            fulfilled_at TIMESTAMPTZ NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            raw_response JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_billing_payments_user_created
        ON billing_payments (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_billing_payments_status
        ON billing_payments (status, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing_payments")
