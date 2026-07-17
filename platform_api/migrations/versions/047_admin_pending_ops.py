"""Admin dual-control queue for sensitive credit adjusts (Phase 3)."""

from alembic import op

revision = "047_admin_pending_ops"
down_revision = "046_monthly_plan_standard_quotas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_pending_ops (
            id UUID PRIMARY KEY,
            op_type VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending',
            requested_by UUID NOT NULL REFERENCES users(id),
            approved_by UUID NULL REFERENCES users(id),
            rejected_by UUID NULL REFERENCES users(id),
            target_user_id UUID NULL REFERENCES users(id),
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            reason TEXT NOT NULL,
            decision_note TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            decided_at TIMESTAMPTZ NULL,
            CONSTRAINT admin_pending_ops_status_check
                CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_admin_pending_ops_status_created
            ON admin_pending_ops (status, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_pending_ops")
