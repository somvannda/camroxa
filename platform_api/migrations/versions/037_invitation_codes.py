"""Add invitation codes and signup gating."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "037_invitation_codes"
down_revision = "036_slai_image_provider_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invitation_codes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("code_hint", sa.String(length=12), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_invitation_codes_is_active", "invitation_codes", ["is_active"])

    op.create_table(
        "invitation_code_redemptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invitation_code_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["invitation_code_id"], ["invitation_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("invitation_code_id", "user_id", name="uq_invitation_redemption_user_code"),
    )
    op.create_index(
        "ix_invitation_code_redemptions_code_id",
        "invitation_code_redemptions",
        ["invitation_code_id"],
    )
    op.create_index(
        "ix_invitation_code_redemptions_user_id",
        "invitation_code_redemptions",
        ["user_id"],
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO system_settings (key, value_type, value, updated_at)
            VALUES ('signup_mode', 'string', 'invite_only', NOW())
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'signup_mode'")
    op.drop_index("ix_invitation_code_redemptions_user_id", table_name="invitation_code_redemptions")
    op.drop_index("ix_invitation_code_redemptions_code_id", table_name="invitation_code_redemptions")
    op.drop_table("invitation_code_redemptions")
    op.drop_index("ix_invitation_codes_is_active", table_name="invitation_codes")
    op.drop_table("invitation_codes")
