"""Add web music subscription plans to existing plans table.

Revision ID: 088_web_music_subscription_plans
Revises: 087_web_music_b2_storage
Create Date: 2026-08-16

"""
from alembic import op

revision = "088_web_music_subscription_plans"
down_revision = "087_web_music_b2_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add plan_type column to differentiate web_music from desktop_pro
    op.execute("""
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS plan_type VARCHAR(20) DEFAULT 'desktop_pro'
    """)
    
    # Add monthly_credits column for credit-based quotas
    op.execute("""
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS monthly_credits INTEGER
    """)
    
    # Add features JSON column for feature flags
    op.execute("""
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}'::jsonb
    """)
    
    # Add is_public column to control pricing page visibility
    op.execute("""
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false
    """)
    
    # Add display_order for sorting
    op.execute("""
        ALTER TABLE plans
            ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0
    """)
    
    # Create index on plan_type
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plans_type ON plans(plan_type)
    """)
    
    # Create index on is_public
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plans_public ON plans(is_public) WHERE is_public = true
    """)
    
    # Insert web music plans
    op.execute("""
        INSERT INTO plans (
            name,
            plan_type,
            price_cents,
            billing_cycle_days,
            monthly_credits,
            profile_allowance,
            monthly_song_limit,
            daily_song_limit_per_channel,
            features,
            is_public,
            display_order,
            is_active
        ) VALUES
            -- Starter Plan ($10/mo, $102/yr)
            (
                'starter_monthly',
                'web_music',
                1000,  -- $10
                30,    -- Monthly
                1000,  -- 1,000 credits = 100 songs
                1,     -- 1 profile (workspace)
                NULL,  -- monthly_song_limit (use credits instead)
                999,   -- daily_song_limit_per_channel (high limit)
                '{"music": true, "images": true, "topup": true}'::jsonb,
                true,  -- Show on pricing page
                1,
                true
            ),
            (
                'starter_yearly',
                'web_music',
                10200,  -- $102 (15% off)
                365,    -- Yearly
                1000,   -- 1,000 credits per month
                1,
                NULL,  -- monthly_song_limit (use credits instead)
                999,   -- daily_song_limit_per_channel
                '{"music": true, "images": true, "topup": true}'::jsonb,
                true,
                1,
                true
            ),
            
            -- Creator Plan ($30/mo, $306/yr)
            (
                'creator_monthly',
                'web_music',
                3000,  -- $30
                30,    -- Monthly
                3500,  -- 3,500 credits = 350 songs
                1,
                NULL,  -- monthly_song_limit (use credits instead)
                999,   -- daily_song_limit_per_channel
                '{"music": true, "images": true, "topup": true}'::jsonb,
                true,
                2,
                true
            ),
            (
                'creator_yearly',
                'web_music',
                30600,  -- $306 (15% off)
                365,    -- Yearly
                3500,   -- 3,500 credits per month
                1,
                NULL,  -- monthly_song_limit (use credits instead)
                999,   -- daily_song_limit_per_channel
                '{"music": true, "images": true, "topup": true}'::jsonb,
                true,
                2,
                true
            ),
            
            -- Studio Plan ($60/mo, $612/yr)
            (
                'studio_monthly',
                'web_music',
                6000,  -- $60
                30,    -- Monthly
                8000,  -- 8,000 credits = 800 songs
                1,
                NULL,  -- monthly_song_limit (use credits instead)
                999,   -- daily_song_limit_per_channel
                '{"music": true, "images": true, "topup": true}'::jsonb,
                true,
                3,
                true
            ),
            (
                'studio_yearly',
                'web_music',
                61200,  -- $612 (15% off)
                365,    -- Yearly
                8000,   -- 8,000 credits per month
                1,
                NULL,  -- monthly_song_limit (use credits instead)
                999,   -- daily_song_limit_per_channel
                '{"music": true, "images": true, "topup": true}'::jsonb,
                true,
                3,
                true
            )
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    # Remove web music plans
    op.execute("""
        DELETE FROM plans WHERE plan_type = 'web_music'
    """)
    
    # Remove added columns
    op.execute("""
        DROP INDEX IF EXISTS idx_plans_public
    """)
    op.execute("""
        DROP INDEX IF EXISTS idx_plans_type
    """)
    op.execute("""
        ALTER TABLE plans DROP COLUMN IF EXISTS display_order
    """)
    op.execute("""
        ALTER TABLE plans DROP COLUMN IF EXISTS is_public
    """)
    op.execute("""
        ALTER TABLE plans DROP COLUMN IF EXISTS features
    """)
    op.execute("""
        ALTER TABLE plans DROP COLUMN IF EXISTS monthly_credits
    """)
    op.execute("""
        ALTER TABLE plans DROP COLUMN IF EXISTS plan_type
    """)
