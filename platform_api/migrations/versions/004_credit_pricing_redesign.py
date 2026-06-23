"""Add per-service limits and usage tracking for credit pricing redesign.

Revision ID: 004_credit_pricing_redesign
Revises: 003_channel_prompts
Create Date: 2026-06-20

Changes:
- Rename plans.monthly_song_quota → monthly_song_limit
- Add plans.monthly_image_limit (INTEGER, nullable, DEFAULT NULL)
- Add plans.daily_image_limit_per_channel (INTEGER, NOT NULL, DEFAULT 7)
- Rename credit_pricing.model_identifier → ai_service
- Create usage_tracking table with unique constraint and indexes

Note: system_settings table already exists from 001_initial_schema.
"""

from alembic import op

revision = "004_credit_pricing_redesign"
down_revision = "003_channel_prompts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── Plans table changes ────────────────────────────────────────────────

    # Rename monthly_song_quota → monthly_song_limit
    op.execute("""
        ALTER TABLE plans
        RENAME COLUMN monthly_song_quota TO monthly_song_limit
    """)

    # Add monthly_image_limit (nullable = unlimited)
    op.execute("""
        ALTER TABLE plans
        ADD COLUMN monthly_image_limit INTEGER DEFAULT NULL
    """)

    # Add daily_image_limit_per_channel (NOT NULL, DEFAULT 7)
    op.execute("""
        ALTER TABLE plans
        ADD COLUMN daily_image_limit_per_channel INTEGER NOT NULL DEFAULT 7
    """)

    # ─── Credit pricing table changes ───────────────────────────────────────

    # Rename model_identifier → ai_service
    op.execute("""
        ALTER TABLE credit_pricing
        RENAME COLUMN model_identifier TO ai_service
    """)

    # ─── Usage tracking table ───────────────────────────────────────────────

    op.execute("""
        CREATE TABLE usage_tracking (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            channel_profile_id UUID REFERENCES channel_profiles(id),
            operation_type VARCHAR(50) NOT NULL,
            usage_date DATE NOT NULL,
            daily_count INTEGER NOT NULL DEFAULT 0,
            monthly_count INTEGER NOT NULL DEFAULT 0,
            period_start_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_usage_tracking
                UNIQUE (user_id, channel_profile_id, operation_type, usage_date)
        )
    """)

    op.execute("""
        CREATE INDEX idx_usage_tracking_monthly
        ON usage_tracking (user_id, operation_type, period_start_date)
    """)

    op.execute("""
        CREATE INDEX idx_usage_tracking_daily
        ON usage_tracking (user_id, channel_profile_id, operation_type, usage_date)
    """)


def downgrade() -> None:
    # Drop usage_tracking
    op.execute("DROP TABLE IF EXISTS usage_tracking CASCADE")

    # Revert credit_pricing rename
    op.execute("""
        ALTER TABLE credit_pricing
        RENAME COLUMN ai_service TO model_identifier
    """)

    # Revert plans changes
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS daily_image_limit_per_channel")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS monthly_image_limit")
    op.execute("""
        ALTER TABLE plans
        RENAME COLUMN monthly_song_limit TO monthly_song_quota
    """)
