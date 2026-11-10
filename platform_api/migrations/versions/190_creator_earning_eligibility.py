"""Creator earning eligibility per track.

Revision ID: 190
Revises: 189
"""

from __future__ import annotations

from alembic import op

revision = "190"
down_revision = "189"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_earning_eligibility (
            track_id UUID PRIMARY KEY REFERENCES stream_tracks(id) ON DELETE CASCADE,
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(24) NOT NULL DEFAULT 'not_eligible'
                CHECK (status IN ('not_eligible','eligible','pending_verification','earning','suspended')),
            valid_streams INTEGER NOT NULL DEFAULT 0,
            unique_listeners INTEGER NOT NULL DEFAULT 0,
            threshold_streams INTEGER NOT NULL DEFAULT 500,
            threshold_listeners INTEGER NOT NULL DEFAULT 50,
            notified_half_at TIMESTAMPTZ,
            notified_eligible_at TIMESTAMPTZ,
            eligible_at TIMESTAMPTZ,
            earning_started_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_eligibility_creator "
        "ON creator_earning_eligibility (creator_id, status, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_eligibility_status "
        "ON creator_earning_eligibility (status, updated_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS creator_earning_eligibility CASCADE")
