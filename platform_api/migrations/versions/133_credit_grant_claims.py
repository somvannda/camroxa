"""Non-destructive idempotency guard for credit grants.

Adds ``credit_grant_claims`` — one row per ``(user_id, reason, ref_id)`` grant, so
a retried/duplicated grant with a stable ``ref_id`` credits at most once. Unlike a
unique index on ``credit_transactions`` this is non-destructive: historical
duplicate grant rows are left intact (audit), and existing refs are backfilled so
a re-grant of an already-used ref is still a no-op.

Revision ID: 133_credit_grant_claims
Revises: 132_plan_credit_cadence_guard
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op

revision = "133_credit_grant_claims"
down_revision = "132_plan_credit_cadence_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_grant_claims (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, reason, ref_id)
        )
        """
    )
    # Backfill from existing grants so a re-grant of an already-used ref stays a
    # no-op. Historical duplicates (same key) collapse to one claim row.
    op.execute(
        """
        INSERT INTO credit_grant_claims (user_id, reason, ref_id, created_at)
        SELECT user_id, reason, ref_id, MIN(created_at)
        FROM credit_transactions
        WHERE direction = 'credit' AND ref_id IS NOT NULL
        GROUP BY user_id, reason, ref_id
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS credit_grant_claims")
