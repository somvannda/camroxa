"""Let a user supply their own Google OAuth client for YouTube.

Revision ID: 183
Revises: 182
"""

from __future__ import annotations

from alembic import op

revision = "183"
down_revision = "182"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = platform-managed app (admin console); a value = that user's own app.
    op.execute(
        "ALTER TABLE youtube_oauth_apps ADD COLUMN IF NOT EXISTS owner_user_id UUID "
        "REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_oauth_apps_owner "
        "ON youtube_oauth_apps(owner_user_id) WHERE owner_user_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_youtube_oauth_apps_owner")
    op.execute("ALTER TABLE youtube_oauth_apps DROP COLUMN IF EXISTS owner_user_id")
