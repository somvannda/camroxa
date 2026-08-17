"""Add web_subscriptions table for web music subscriptions.

Revision ID: 089_web_subscriptions
Revises: 088_web_music_subscription_plans
Create Date: 2026-08-16

"""
from alembic import op

revision = "089_web_subscriptions"
down_revision = "088_web_music_subscription_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create web_subscriptions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS web_subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            
            -- Relations
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id UUID NOT NULL REFERENCES plans(id),
            
            -- Status
            status VARCHAR(20) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'cancelled', 'expired', 'past_due')),
            
            -- Billing
            billing_cycle VARCHAR(10) NOT NULL DEFAULT 'monthly'
                CHECK (billing_cycle IN ('monthly', 'yearly')),
            current_period_start TIMESTAMPTZ NOT NULL,
            current_period_end TIMESTAMPTZ NOT NULL,
            cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
            cancelled_at TIMESTAMPTZ,
            
            -- Payment (CutLuy)
            payment_provider VARCHAR(20) NOT NULL DEFAULT 'cutluy',
            external_subscription_id VARCHAR(255),
            external_customer_id VARCHAR(255),
            last_payment_at TIMESTAMPTZ,
            last_payment_amount_cents INTEGER,
            
            -- Credit tracking
            monthly_credits_granted INTEGER NOT NULL,
            monthly_credits_used INTEGER NOT NULL DEFAULT 0,
            last_credit_reset TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Metadata
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- One subscription per user
            UNIQUE(user_id),
            
            -- Ensure valid period
            CHECK (current_period_end > current_period_start)
        )
    """)
    
    # Create indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_subscriptions_user
            ON web_subscriptions(user_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_subscriptions_status
            ON web_subscriptions(status)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_subscriptions_period_end
            ON web_subscriptions(current_period_end)
            WHERE status = 'active'
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_subscriptions_external_id
            ON web_subscriptions(external_subscription_id)
            WHERE external_subscription_id IS NOT NULL
    """)
    
    # Create function to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_web_subscription_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    
    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER trigger_web_subscription_updated_at
        BEFORE UPDATE ON web_subscriptions
        FOR EACH ROW
        EXECUTE FUNCTION update_web_subscription_updated_at()
    """)


def downgrade() -> None:
    # Drop trigger and function
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_web_subscription_updated_at ON web_subscriptions
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS update_web_subscription_updated_at()
    """)
    
    # Drop table
    op.execute("""
        DROP TABLE IF EXISTS web_subscriptions CASCADE
    """)
