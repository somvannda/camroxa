"""Creator Program workflow: applications, verification evidence, badges.

Revision ID: 188
Revises: 187
"""

from __future__ import annotations

from alembic import op

revision = "188"
down_revision = "187"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_applications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            version INTEGER NOT NULL DEFAULT 1,
            requested_tier VARCHAR(20) NOT NULL DEFAULT 'verified'
                CHECK (requested_tier IN ('verified')),
            status VARCHAR(30) NOT NULL DEFAULT 'submitted'
                CHECK (status IN ('draft','submitted','in_review','changes_requested','approved','rejected','withdrawn')),
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            submitted_at TIMESTAMPTZ,
            sla_due_at TIMESTAMPTZ,
            reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TIMESTAMPTZ,
            decision_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_app_open "
        "ON creator_applications (user_id) "
        "WHERE status IN ('submitted','in_review','changes_requested')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_app_status "
        "ON creator_applications (status, submitted_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_app_user "
        "ON creator_applications (user_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_verifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind VARCHAR(30) NOT NULL
                CHECK (kind IN ('identity','authenticity','business','voice_consent')),
            status VARCHAR(20) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','approved','rejected','expired')),
            evidence_ref TEXT,
            reviewer_id UUID REFERENCES users(id) ON DELETE SET NULL,
            reviewed_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_verifications_user "
        "ON creator_verifications (user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_verifications_status "
        "ON creator_verifications (status, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_badges (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            badge VARCHAR(30) NOT NULL
                CHECK (badge IN ('verified','founding','top_creator','partner','label','ai_artist','ai_assisted','staff')),
            granted_by UUID REFERENCES users(id) ON DELETE SET NULL,
            granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ,
            reason TEXT
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_creator_badge_active "
        "ON creator_badges (user_id, badge) WHERE revoked_at IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_badges_user "
        "ON creator_badges (user_id, granted_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS creator_badges CASCADE")
    op.execute("DROP TABLE IF EXISTS creator_verifications CASCADE")
    op.execute("DROP TABLE IF EXISTS creator_applications CASCADE")
