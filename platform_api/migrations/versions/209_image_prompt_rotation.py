"""Per-user image-prompt rotation cycles.

Revision ID: 209
Revises: 208
Create Date: 2026-11-17

Prompt selection is now a per-user shuffle bag: every active prompt is used once
per cycle, in random order, then the next cycle starts. This replaces the global
least-used history for prompt styles (sample-image rotation is unchanged).
"""

from __future__ import annotations

from alembic import op

revision = "209"
down_revision = "208"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_prompt_rotation (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            style_id UUID NOT NULL REFERENCES image_prompt_styles(id) ON DELETE CASCADE,
            cycle_number INTEGER NOT NULL,
            batch_id UUID,
            used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, kind, style_id, cycle_number)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_prompt_rotation_user_kind_cycle
        ON image_prompt_rotation(user_id, kind, cycle_number)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_image_prompt_rotation_user_kind_cycle")
    op.execute("DROP TABLE IF EXISTS image_prompt_rotation")
