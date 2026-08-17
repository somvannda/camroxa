"""Merge credit refund head with parallel web music merge head.

Revision ID: 103_merge_credit_refund_heads
Revises: 102_credit_refund_idempotency, 1f0ad008d202
Create Date: 2026-08-17
"""

from __future__ import annotations

from alembic import op

revision = "103_merge_credit_refund_heads"
down_revision = ("102_credit_refund_idempotency", "1f0ad008d202")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
