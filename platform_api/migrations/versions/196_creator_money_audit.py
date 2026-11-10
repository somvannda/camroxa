"""Append-only audit trail for creator money actions.

Revision ID: 196
Revises: 195
"""

from __future__ import annotations

from alembic import op

revision = "196"
down_revision = "195"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_money_audit (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(60) NOT NULL,
            subject_type VARCHAR(40) NOT NULL,
            subject_id UUID,
            creator_id UUID REFERENCES users(id) ON DELETE SET NULL,
            amount_micros BIGINT,
            detail JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_money_audit_created "
        "ON creator_money_audit (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_money_audit_creator "
        "ON creator_money_audit (creator_id, created_at DESC)"
    )
    # Append-only: block updates and deletes so the trail cannot be rewritten.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION creator_money_audit_immutable()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'creator_money_audit is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_creator_money_audit_immutable ON creator_money_audit"
    )
    op.execute(
        "CREATE TRIGGER trg_creator_money_audit_immutable "
        "BEFORE UPDATE OR DELETE ON creator_money_audit "
        "FOR EACH ROW EXECUTE FUNCTION creator_money_audit_immutable()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_creator_money_audit_immutable ON creator_money_audit"
    )
    op.execute("DROP FUNCTION IF EXISTS creator_money_audit_immutable()")
    op.execute("DROP INDEX IF EXISTS idx_creator_money_audit_creator")
    op.execute("DROP INDEX IF EXISTS idx_creator_money_audit_created")
    op.execute("DROP TABLE IF EXISTS creator_money_audit")
