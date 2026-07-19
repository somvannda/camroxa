"""Daily quota bank for unused per-channel daily allowance accrual."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "064_daily_quota_bank"
down_revision = "063_music_genre_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_quota_bank",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("banked_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_accrual_date", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["channel_profile_id"], ["channel_profiles.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "uq_daily_quota_bank_user_channel_op",
        "daily_quota_bank",
        ["user_id", "channel_profile_id", "operation_type"],
        unique=True,
    )
    op.create_index(
        "idx_daily_quota_bank_user_id",
        "daily_quota_bank",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_daily_quota_bank_user_id", table_name="daily_quota_bank")
    op.drop_index("uq_daily_quota_bank_user_channel_op", table_name="daily_quota_bank")
    op.drop_table("daily_quota_bank")
