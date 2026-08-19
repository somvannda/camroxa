"""Add topup_purchases table to track credit top-up purchases.

Revision ID: 091_topup_purchases
Revises: 090_update_credit_packs
Create Date: 2026-08-16

"""
from alembic import op

revision = "091_topup_purchases"
down_revision = "090_update_credit_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create topup_purchases table
    op.execute("""
        CREATE TABLE IF NOT EXISTS topup_purchases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            
            -- Relations
            user_id UUID NOT NULL REFERENCES users(id),
            web_subscription_id UUID REFERENCES web_subscriptions(id),
            credit_pack_id UUID NOT NULL REFERENCES credit_packs(id),
            
            -- Purchase details
            credits_purchased INTEGER NOT NULL CHECK (credits_purchased > 0),
            amount_paid_cents INTEGER NOT NULL CHECK (amount_paid_cents >= 0),
            currency VARCHAR(3) NOT NULL DEFAULT 'USD',
            
            -- Payment (CutLuy)
            payment_provider VARCHAR(20) NOT NULL DEFAULT 'cutluy',
            external_payment_id VARCHAR(255),
            payment_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded')),
            
            -- Timestamps
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            refunded_at TIMESTAMPTZ
        )
    """)
    
    # Create indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topup_purchases_user
            ON topup_purchases(user_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topup_purchases_subscription
            ON topup_purchases(web_subscription_id)
            WHERE web_subscription_id IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topup_purchases_status
            ON topup_purchases(payment_status)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topup_purchases_created
            ON topup_purchases(created_at DESC)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_topup_purchases_external_payment
            ON topup_purchases(external_payment_id)
            WHERE external_payment_id IS NOT NULL
    """)
    
    # Create function to link topup to credit_transactions
    op.execute("""
        CREATE OR REPLACE FUNCTION grant_topup_credits()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Only process when status changes to 'completed'
            IF NEW.payment_status = 'completed' AND (OLD.payment_status IS NULL OR OLD.payment_status != 'completed') THEN
                -- Add credits to user's wallet
                INSERT INTO credit_wallets (user_id, balance)
                VALUES (NEW.user_id, NEW.credits_purchased)
                ON CONFLICT (user_id) DO UPDATE
                SET balance = credit_wallets.balance + NEW.credits_purchased,
                    updated_at = NOW();
                
                -- Log transaction
                INSERT INTO credit_transactions (
                    user_id,
                    amount,
                    direction,
                    reason,
                    ref_id,
                    pack_id,
                    payment_ref
                ) VALUES (
                    NEW.user_id,
                    NEW.credits_purchased,
                    'credit',
                    'topup_purchase',
                    NEW.id::text,
                    NEW.credit_pack_id,
                    NEW.external_payment_id
                );
                
                -- Update topup_credits_balance in web_subscriptions
                IF NEW.web_subscription_id IS NOT NULL THEN
                    UPDATE web_subscriptions
                    SET topup_credits_balance = COALESCE(topup_credits_balance, 0) + NEW.credits_purchased,
                        updated_at = NOW()
                    WHERE id = NEW.web_subscription_id;
                END IF;
                
                -- Set completed_at timestamp
                NEW.completed_at = NOW();
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    
    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_grant_topup_credits
        BEFORE UPDATE OF payment_status ON topup_purchases
        FOR EACH ROW
        EXECUTE FUNCTION grant_topup_credits()
    """)
    
    # Add topup_credits_balance to web_subscriptions if not exists
    op.execute("""
        ALTER TABLE web_subscriptions
            ADD COLUMN IF NOT EXISTS topup_credits_balance INTEGER NOT NULL DEFAULT 0
                CHECK (topup_credits_balance >= 0)
    """)


def downgrade() -> None:
    # Remove column from web_subscriptions
    op.execute("""
        ALTER TABLE web_subscriptions
            DROP COLUMN IF EXISTS topup_credits_balance
    """)
    
    # Drop trigger and function
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_grant_topup_credits ON topup_purchases
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS grant_topup_credits()
    """)
    
    # Drop table
    op.execute("""
        DROP TABLE IF EXISTS topup_purchases CASCADE
    """)
