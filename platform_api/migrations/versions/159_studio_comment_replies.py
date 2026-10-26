"""Add parent replies to Studio project comments.

Revision ID: 159_studio_comment_replies
Revises: 158_studio_personas
"""

from __future__ import annotations

from alembic import op

revision: str = "159_studio_comment_replies"
down_revision: str | None = "158_studio_personas"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE studio_project_comments
            ADD COLUMN IF NOT EXISTS parent_id UUID NULL
            REFERENCES studio_project_comments(id) ON DELETE CASCADE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_project_comments_parent_idx
            ON studio_project_comments (parent_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS studio_project_comments_parent_idx")
    op.execute(
        "ALTER TABLE studio_project_comments DROP COLUMN IF EXISTS parent_id"
    )
