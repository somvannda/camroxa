"""Merge heads and add token_version for session invalidation."""

from alembic import op

revision = "034_auth_session_hardening"
down_revision = ("033_description_vocal_profile", "033_redeem_codes")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        DROP COLUMN IF EXISTS token_version
        """
    )
