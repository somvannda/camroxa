"""Allow song_count=0 for manual image-only batches.

Revision ID: 082_batch_song_count_allow_zero
Revises: 081_user_period_quota_topups
Create Date: 2026-08-05
"""

from __future__ import annotations

from alembic import op

revision = "082_batch_song_count_allow_zero"
down_revision = "081_user_period_quota_topups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE batches DROP CONSTRAINT IF EXISTS batches_song_count_check")
    op.execute(
        "ALTER TABLE batches ADD CONSTRAINT batches_song_count_check "
        "CHECK (song_count BETWEEN 0 AND 50)"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE batches SET song_count = 1 WHERE song_count < 1"
    )
    op.execute("ALTER TABLE batches DROP CONSTRAINT IF EXISTS batches_song_count_check")
    op.execute(
        "ALTER TABLE batches ADD CONSTRAINT batches_song_count_check "
        "CHECK (song_count BETWEEN 1 AND 50)"
    )
