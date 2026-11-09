"""Distinguish "no YouTube choice recorded" from an explicit off.

Revision ID: 182
Revises: 181
"""

from __future__ import annotations

from alembic import op

revision = "182"
down_revision = "181"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE batches ALTER COLUMN auto_upload_youtube DROP NOT NULL")
    # Rows written before the flag existed carry the column default (false),
    # which the desktop would read as "the user turned uploads off". Clearing
    # them restores the old behaviour: fall back to the app setting.
    op.execute("UPDATE batches SET auto_upload_youtube = NULL")


def downgrade() -> None:
    op.execute("UPDATE batches SET auto_upload_youtube = FALSE WHERE auto_upload_youtube IS NULL")
    op.execute("ALTER TABLE batches ALTER COLUMN auto_upload_youtube SET NOT NULL")
