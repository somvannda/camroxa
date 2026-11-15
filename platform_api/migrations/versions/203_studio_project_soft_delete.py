"""Soft-delete Studio projects (S04 "Recently Deleted")

Revision ID: 203
Revises: 202
Create Date: 2026-11-14

Spec 56, behaviour note 3: "`Recently Deleted` is a first-class tab — deletion is soft,
with recovery." Deleting used to remove the row, so the tab had nothing to offer. A
nullable `deleted_at` keeps the document for restore and hides it from every list.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "203"
down_revision = "202"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "studio_projects",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "studio_projects_deleted_idx",
        "studio_projects",
        ["user_id", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("studio_projects_deleted_idx", table_name="studio_projects")
    op.drop_column("studio_projects", "deleted_at")
