"""Clip-scoped comments on Studio projects

Revision ID: 202
Revises: 201
Create Date: 2026-11-14

The reference's S55 panel is per clip ("Comments and notes" at the bottom of the
clip inspector). The comments table already exists for project threads, so a
nullable clip_id scopes a note to one local clip while project-level comments
keep clip_id NULL.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "202"
down_revision = "201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "studio_project_comments",
        sa.Column("clip_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "studio_project_comments_clip_idx",
        "studio_project_comments",
        ["project_id", "clip_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("studio_project_comments_clip_idx", table_name="studio_project_comments")
    op.drop_column("studio_project_comments", "clip_id")
