"""Remember which pooled Suno key owns a task.

Suno's record-info endpoint is account-scoped: only the key that created a task
can read it, and every other key answers 401/403. Polls used to try every active
key in order, so each poll cost one request per account. Recording the owner lets
a poll hit that account directly (and re-pin if the key was rotated).

Revision ID: 185
Revises: 184
"""

from __future__ import annotations

from alembic import op

revision = "185"
down_revision = "184"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS suno_key_id UUID")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_suno_tasks_suno_key_id "
        "ON suno_tasks (suno_key_id) WHERE suno_key_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_suno_key_id")
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS suno_key_id")
