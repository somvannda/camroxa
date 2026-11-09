"""Creator identity: profiles and handle history.

Revision ID: 187
Revises: 186
"""

from __future__ import annotations

from alembic import op

revision = "187"
down_revision = "186"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_profiles (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            handle VARCHAR(30) NOT NULL,
            display_name VARCHAR(50) NOT NULL,
            tagline VARCHAR(120),
            bio TEXT,
            country_code CHAR(2),
            city VARCHAR(80),
            avatar_url TEXT,
            banner_url TEXT,
            links JSONB NOT NULL DEFAULT '[]'::jsonb,
            genres TEXT[] NOT NULL DEFAULT '{}',
            influences TEXT[] NOT NULL DEFAULT '{}',
            pronouns VARCHAR(20),
            ai_disclosure VARCHAR(20) NOT NULL DEFAULT 'none'
                CHECK (ai_disclosure IN ('none','ai_assisted','ai_artist')),
            tier VARCHAR(20) NOT NULL DEFAULT 'creator'
                CHECK (tier IN ('creator','verified','partner')),
            status VARCHAR(20) NOT NULL DEFAULT 'active'
                CHECK (status IN ('draft','active','at_risk','suspended','offboarded')),
            verified_at TIMESTAMPTZ,
            verification_expires_at TIMESTAMPTZ,
            follower_count INTEGER NOT NULL DEFAULT 0,
            program_joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            payout_currency CHAR(3) NOT NULL DEFAULT 'USD',
            support_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            is_sample BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_handle "
        "ON creator_profiles (LOWER(handle))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_status "
        "ON creator_profiles (status, tier)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_genres "
        "ON creator_profiles USING GIN (genres)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_country "
        "ON creator_profiles (country_code)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_handle_history (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            old_handle VARCHAR(30) NOT NULL,
            new_handle VARCHAR(30) NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            redirect_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '12 months'
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_handle_history_old "
        "ON creator_handle_history (LOWER(old_handle), redirect_until)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_handle_history_user "
        "ON creator_handle_history (user_id, changed_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS creator_handle_history CASCADE")
    op.execute("DROP TABLE IF EXISTS creator_profiles CASCADE")
