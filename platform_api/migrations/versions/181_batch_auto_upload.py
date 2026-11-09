"""Persist the per-batch YouTube upload choice.

Revision ID: 181
Revises: 180
"""

from __future__ import annotations

from alembic import op

revision = "181"
down_revision = "180"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE batches ADD COLUMN IF NOT EXISTS "
        "auto_upload_youtube BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE batches DROP COLUMN IF EXISTS auto_upload_youtube")
