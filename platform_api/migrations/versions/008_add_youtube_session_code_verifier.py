"""Persist PKCE code verifier for YouTube OAuth sessions."""

from alembic import op

revision = "008_youtube_code_verifier"
down_revision = "007_add_youtube_connection_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE youtube_connect_sessions
        ADD COLUMN IF NOT EXISTS code_verifier TEXT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE youtube_connect_sessions
        DROP COLUMN IF EXISTS code_verifier
        """
    )
