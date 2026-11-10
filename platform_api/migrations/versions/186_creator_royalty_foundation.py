"""Creator Program royalty foundation.

The admin streaming catalog already reads ``valid_streams``, ``royalty_ledger``
and ``stream_tracks.origin``, and imports ``RoyaltyPolicyService`` — but none of
those existed in the schema. This migration adds the missing tables and column
so analytics and monetization can be built on a real foundation.

Revision ID: 186
Revises: 185
"""

from __future__ import annotations

from alembic import op

revision = "186"
down_revision = "185"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Stream origin (AI vs original) -----------------------------------
    op.execute(
        "ALTER TABLE stream_tracks "
        "ADD COLUMN IF NOT EXISTS origin VARCHAR(20) NOT NULL DEFAULT 'ai_generated'"
    )
    op.execute("ALTER TABLE stream_tracks DROP CONSTRAINT IF EXISTS chk_stream_tracks_origin")
    op.execute(
        "ALTER TABLE stream_tracks ADD CONSTRAINT chk_stream_tracks_origin "
        "CHECK (origin IN ('original','ai_assisted','ai_generated'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_stream_tracks_origin ON stream_tracks (origin)"
    )

    # --- Royalty policy versions ------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS royalty_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            version INTEGER NOT NULL UNIQUE,
            document JSONB NOT NULL,
            effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            effective_to TIMESTAMPTZ,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_royalty_policies_effective "
        "ON royalty_policies (effective_from DESC, version DESC)"
    )

    # --- Monthly royalty periods ------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS royalty_periods (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            policy_id UUID REFERENCES royalty_policies(id) ON DELETE SET NULL,
            pool_micros BIGINT NOT NULL DEFAULT 0,
            total_weighted_streams BIGINT NOT NULL DEFAULT 0,
            rate_micros NUMERIC(18,8) NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','calculated','locked','paid')),
            calculated_at TIMESTAMPTZ,
            locked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (period_start, period_end)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_royalty_periods_status "
        "ON royalty_periods (status, period_start DESC)"
    )

    # --- Qualified listen events ------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS valid_streams (
            id BIGSERIAL PRIMARY KEY,
            subject_type VARCHAR(30) NOT NULL DEFAULT 'stream_track',
            subject_id UUID NOT NULL,
            owner_user_id UUID NOT NULL,
            listener_user_id UUID NOT NULL,
            session_id VARCHAR(64),
            played_seconds INTEGER NOT NULL,
            duration_seconds NUMERIC(8,2),
            completed BOOLEAN NOT NULL DEFAULT FALSE,
            status VARCHAR(20) NOT NULL
                CHECK (status IN ('valid','royalty','excluded_owner','excluded_short','excluded_fraud','capped')),
            reason TEXT,
            dedupe_key VARCHAR(160) NOT NULL UNIQUE,
            ip_hash VARCHAR(64),
            ua_hash VARCHAR(64),
            played_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_valid_streams_subject "
        "ON valid_streams (subject_id, played_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_valid_streams_owner "
        "ON valid_streams (owner_user_id, played_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_valid_streams_listener "
        "ON valid_streams (listener_user_id, played_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_valid_streams_status "
        "ON valid_streams (status, played_at DESC)"
    )

    # --- Immutable royalty ledger -----------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS royalty_ledger (
            id BIGSERIAL PRIMARY KEY,
            period_id UUID REFERENCES royalty_periods(id) ON DELETE CASCADE,
            policy_id UUID REFERENCES royalty_policies(id) ON DELETE SET NULL,
            creator_id UUID REFERENCES users(id) ON DELETE SET NULL,
            track_id UUID REFERENCES stream_tracks(id) ON DELETE SET NULL,
            subject_type VARCHAR(30) NOT NULL DEFAULT 'stream_track',
            subject_id UUID,
            entry_type VARCHAR(20) NOT NULL
                CHECK (entry_type IN ('accrual','cap_adjustment','reserve','release','clawback','payout','adjustment')),
            weighted_streams BIGINT NOT NULL DEFAULT 0,
            rate_micros NUMERIC(18,8) NOT NULL DEFAULT 0,
            amount_micros BIGINT NOT NULL DEFAULT 0,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_royalty_ledger_creator "
        "ON royalty_ledger (creator_id, period_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_royalty_ledger_subject "
        "ON royalty_ledger (subject_type, subject_id, entry_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_royalty_ledger_period "
        "ON royalty_ledger (period_id, entry_type)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS royalty_ledger CASCADE")
    op.execute("DROP TABLE IF EXISTS valid_streams CASCADE")
    op.execute("DROP TABLE IF EXISTS royalty_periods CASCADE")
    op.execute("DROP TABLE IF EXISTS royalty_policies CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_stream_tracks_origin")
    op.execute("ALTER TABLE stream_tracks DROP CONSTRAINT IF EXISTS chk_stream_tracks_origin")
    op.execute("ALTER TABLE stream_tracks DROP COLUMN IF EXISTS origin")
