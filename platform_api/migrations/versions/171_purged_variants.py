"""Track permanently deleted versions separately from trashed ones.

Trashing is recoverable (`trashed_variants`). Deleting one version forever must
not remove the other, so a purged version is recorded in `purged_variants` and
hidden from the library while the sibling stays playable. The row is removed
once both versions are purged.

Revision ID: 171_purged_variants
Revises: 170_trash_variants
"""

from __future__ import annotations

from alembic import op

revision: str = "171_purged_variants"
down_revision: str | None = "170_trash_variants"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS purged_variants TEXT[] NOT NULL DEFAULT '{}'
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS purged_variants")
