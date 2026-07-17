"""Track least-used rotation for image sample paths."""

from alembic import op

revision = "035_image_random_history"
down_revision = "034_auth_session_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_random_history (
            kind TEXT NOT NULL,
            value TEXT NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            used_at TIMESTAMPTZ,
            PRIMARY KEY (kind, value)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_random_history_kind_used
        ON image_random_history (kind, used_count ASC, used_at ASC NULLS FIRST)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS image_random_history")
