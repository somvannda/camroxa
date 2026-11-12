"""Studio project presence for the polled collaborator cursors.

The reference uses a realtime transport; this product already has the project
membership and cookie auth, so presence can be a small, durable row per editor
session that the editor refreshes while it is open. Rows older than the lease are
ignored by the query. `client_id` identifies the tab/session, so two tabs of the
same account can see each other.

Revision ID: 198
Revises: 197
"""

from __future__ import annotations

from alembic import op

revision = "198"
down_revision = "197"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_editor_presence (
            project_id UUID NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
            client_id TEXT NOT NULL,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            display_name VARCHAR(120) NOT NULL DEFAULT '',
            color VARCHAR(16) NOT NULL DEFAULT '#38bdf8',
            cursor_time DOUBLE PRECISION NOT NULL DEFAULT 0,
            playhead DOUBLE PRECISION NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (project_id, client_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_studio_editor_presence_updated "
        "ON studio_editor_presence (project_id, updated_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_studio_editor_presence_updated")
    op.execute("DROP TABLE IF EXISTS studio_editor_presence")
