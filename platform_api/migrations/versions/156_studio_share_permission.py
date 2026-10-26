"""Add view/edit permission to Studio share links.

Revision ID: 156_studio_share_permission
Revises: 155_studio_project_comments
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "156_studio_share_permission"
down_revision: str | None = "155_studio_project_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_project_shares
            ADD COLUMN IF NOT EXISTS permission TEXT NOT NULL DEFAULT 'view'
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE studio_project_shares DROP COLUMN IF EXISTS permission"
    )
