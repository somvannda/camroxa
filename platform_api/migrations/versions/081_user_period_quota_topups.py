"""Admin period-scoped plan quota top-ups (limit bumps for current billing period).

Revision ID: 081_user_period_quota_topups
Revises: 080_job_queue
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "081_user_period_quota_topups"
down_revision = "080_job_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_period_quota_topups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("license_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column("extra_units", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["license_id"], ["licenses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("extra_units > 0", name="ck_user_period_quota_topups_extra_positive"),
        sa.CheckConstraint(
            "quota_kind IN ('draft', 'music', 'image', 'video', 'merge')",
            name="ck_user_period_quota_topups_kind",
        ),
    )
    op.create_index(
        "idx_user_period_quota_topups_lookup",
        "user_period_quota_topups",
        ["user_id", "period_start", "quota_kind"],
    )
    op.create_index(
        "idx_user_period_quota_topups_user_id",
        "user_period_quota_topups",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_user_period_quota_topups_user_id",
        table_name="user_period_quota_topups",
    )
    op.drop_index(
        "idx_user_period_quota_topups_lookup",
        table_name="user_period_quota_topups",
    )
    op.drop_table("user_period_quota_topups")
