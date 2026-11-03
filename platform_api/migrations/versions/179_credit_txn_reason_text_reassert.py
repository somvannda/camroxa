"""Re-assert ``credit_transactions.reason`` as TEXT.

Production ran with ``alembic_version = 178`` while the column was still
``character varying(100)``: the revision was recorded but its DDL was not in
effect. ``174`` rebuilds tables from ``*_archive`` snapshots and the deploy that
applied ``178`` also reported ``DEPLOY_LOCK_NOT_OWNER``, so a concurrent runner
most likely restored the pre-178 shape after the ALTER.

Re-running the ALTER unconditionally costs nothing (PostgreSQL treats a type
change to the current type as a no-op), and the version gate ``178 -> 179``
guarantees this one is actually executed.

Revision ID: 179
Revises: 178
"""

from __future__ import annotations

from alembic import op

revision = "179"
down_revision = "178"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE credit_transactions
        ALTER COLUMN reason TYPE TEXT
        """
    )


def downgrade() -> None:
    # Deliberately a no-op: narrowing back to VARCHAR(100) would truncate real
    # admin reasons, and the column is meant to stay TEXT.
    pass
