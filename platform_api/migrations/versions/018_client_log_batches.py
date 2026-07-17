"""Create client_log_batches for desktop diagnostic log uploads."""

from alembic import op

revision = "018_client_log_batches"
down_revision = "017_profile_video_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS client_log_batches (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            client_id VARCHAR(128),
            client_label VARCHAR(64),
            app_version VARCHAR(64),
            line_count INTEGER NOT NULL DEFAULT 0,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_client_log_batches_user_created
        ON client_log_batches(user_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS client_log_batches")
