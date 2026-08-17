"""Update credit_packs table for web music top-ups.

Revision ID: 090_update_credit_packs
Revises: 089_web_subscriptions
Create Date: 2026-08-16

"""
from alembic import op

revision = "090_update_credit_packs"
down_revision = "089_web_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add slug column for easier reference
    op.execute("""
        ALTER TABLE credit_packs
            ADD COLUMN IF NOT EXISTS slug VARCHAR(50)
    """)
    
    # Add total_credits column (replaces song_credits for web music)
    op.execute("""
        ALTER TABLE credit_packs
            ADD COLUMN IF NOT EXISTS total_credits INTEGER
    """)
    
    # Add display_order for sorting
    op.execute("""
        ALTER TABLE credit_packs
            ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0
    """)
    
    # Add pack_type to differentiate desktop vs web music packs
    op.execute("""
        ALTER TABLE credit_packs
            ADD COLUMN IF NOT EXISTS pack_type VARCHAR(20) DEFAULT 'desktop'
    """)
    
    # Create unique index on slug (without WHERE clause for ON CONFLICT support)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_packs_slug
            ON credit_packs(slug)
    """)
    
    # Create index on pack_type
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_packs_type
            ON credit_packs(pack_type)
    """)
    
    # Insert web music credit packs
    op.execute("""
        INSERT INTO credit_packs (
            slug,
            name,
            pack_type,
            total_credits,
            price_cents,
            song_credits,
            request_count,
            display_order,
            is_active
        ) VALUES
            -- Small Pack: 400 credits, $5, 40 songs
            (
                'small',
                'Small Pack',
                'web_music',
                400,
                500,  -- $5
                40,   -- song_credits (for backward compat)
                40,   -- request_count (for backward compat)
                1,
                true
            ),
            -- Medium Pack: 1,000 credits, $10, 100 songs
            (
                'medium',
                'Medium Pack',
                'web_music',
                1000,
                1000,  -- $10
                100,
                100,
                2,
                true
            ),
            -- Large Pack: 2,500 credits, $25, 250 songs
            (
                'large',
                'Large Pack',
                'web_music',
                2500,
                2500,  -- $25
                250,
                250,
                3,
                true
            ),
            -- Mega Pack: 8,000 credits, $50, 800 songs
            (
                'mega',
                'Mega Pack',
                'web_music',
                8000,
                5000,  -- $50
                800,
                800,
                4,
                true
            )
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade() -> None:
    # Remove web music credit packs
    op.execute("""
        DELETE FROM credit_packs WHERE pack_type = 'web_music'
    """)
    
    # Remove indexes
    op.execute("""
        DROP INDEX IF EXISTS idx_credit_packs_type
    """)
    op.execute("""
        DROP INDEX IF EXISTS idx_credit_packs_slug
    """)
    
    # Remove columns
    op.execute("""
        ALTER TABLE credit_packs DROP COLUMN IF EXISTS pack_type
    """)
    op.execute("""
        ALTER TABLE credit_packs DROP COLUMN IF EXISTS display_order
    """)
    op.execute("""
        ALTER TABLE credit_packs DROP COLUMN IF EXISTS total_credits
    """)
    op.execute("""
        ALTER TABLE credit_packs DROP COLUMN IF EXISTS slug
    """)
