"""Add redeem codes and redemption ledger tables."""

from alembic import op

revision = "033_redeem_codes"
down_revision = "032_onboarding_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS redeem_codes (
            id UUID PRIMARY KEY,
            code VARCHAR(64) NOT NULL UNIQUE,
            description VARCHAR(255) NULL,
            reward_type VARCHAR(32) NOT NULL,
            discount_amount_cents INTEGER NULL,
            discount_percent INTEGER NULL,
            credit_amount INTEGER NULL,
            applicable_plan_id UUID NULL REFERENCES plans(id) ON DELETE SET NULL,
            max_redemptions INTEGER NULL,
            current_redemptions INTEGER NOT NULL DEFAULT 0,
            per_user_limit INTEGER NOT NULL DEFAULT 1,
            starts_at TIMESTAMPTZ NULL,
            expires_at TIMESTAMPTZ NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_redeem_codes_active_window
        ON redeem_codes (is_active, starts_at, expires_at, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_redeem_codes_plan
        ON redeem_codes (applicable_plan_id)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS redeem_code_redemptions (
            id UUID PRIMARY KEY,
            redeem_code_id UUID NOT NULL REFERENCES redeem_codes(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            billing_payment_id UUID NULL REFERENCES billing_payments(id) ON DELETE SET NULL,
            plan_id UUID NULL REFERENCES plans(id) ON DELETE SET NULL,
            status VARCHAR(32) NOT NULL,
            amount_cents INTEGER NULL,
            credit_amount INTEGER NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_redeem_code_redemptions_code_user
        ON redeem_code_redemptions (redeem_code_id, user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_redeem_code_redemptions_user_created
        ON redeem_code_redemptions (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_redeem_code_redemptions_payment
        ON redeem_code_redemptions (billing_payment_id)
        WHERE billing_payment_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_redeem_code_redemptions_payment")
    op.execute("DROP TABLE IF EXISTS redeem_code_redemptions")
    op.execute("DROP TABLE IF EXISTS redeem_codes")
