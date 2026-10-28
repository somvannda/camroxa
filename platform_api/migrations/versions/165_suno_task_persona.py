"""Add voice persona to web-music generations.

Revision ID: 165_suno_task_persona
Revises: 164_reference_images
"""

from __future__ import annotations

from alembic import op

revision: str = "165_suno_task_persona"
down_revision: str | None = "164_reference_images"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
            ADD COLUMN IF NOT EXISTS persona_id TEXT
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE suno_tasks DROP COLUMN IF EXISTS persona_id")
