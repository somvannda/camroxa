"""Trash individual versions, not the whole song.

`trashed_at` trashed a generation row (both variants). Songs are two clips
(v1 = ok, v2 = alt) and users expect to trash one of them, so the flag becomes
per-variant: `trashed_variants TEXT[]`.

Revision ID: 170_trash_variants
Revises: 169_suno_task_trash
"""

from __future__ import annotations

from alembic import op

revision: str = "170_trash_variants"
down_revision: str | None = "169_suno_task_trash"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS trashed_variants TEXT[] NOT NULL DEFAULT '{}'
        """
    )
    # A row that was trashed before this migration had both versions trashed.
    op.execute(
        """
        UPDATE suno_tasks
        SET trashed_variants = ARRAY['ok', 'alt']
        WHERE trashed_at IS NOT NULL AND cardinality(trashed_variants) = 0
        """
    )
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS trashed_at")
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_trashed")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suno_tasks_trashed_variants
            ON suno_tasks (user_id)
            WHERE cardinality(trashed_variants) > 0
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_suno_tasks_trashed_variants")
    op.execute("ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS trashed_at TIMESTAMPTZ NULL")
    op.execute(
        """
        UPDATE suno_tasks
        SET trashed_at = NOW()
        WHERE cardinality(trashed_variants) > 0
        """
    )
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS trashed_variants")
