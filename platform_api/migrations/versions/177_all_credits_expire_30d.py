"""Every credit lot must expire within 30 days.

Migration 174 rebuilt free-user grant lots (and the two reset users) with
``expires_at = NULL``. That contradicts the rule that every credit expires
within 30 days. This migration stamps all live non-expiring lots with a
30-day expiry.

Revision ID: 177
Revises: 176
"""

from __future__ import annotations

from alembic import op

revision = "177"
down_revision = "176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE credit_wallet_lots
        SET expires_at = NOW() + INTERVAL '30 days'
        WHERE remaining_units > 0
          AND expires_at IS NULL
        """
    )


def downgrade() -> None:
    # Expiry is one-way; restore from a backup if the old NULLs are needed.
    pass
