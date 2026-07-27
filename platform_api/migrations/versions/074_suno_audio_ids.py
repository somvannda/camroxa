"""Persist Suno clip audio IDs for timestamped lyrics fetch."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "074_suno_audio_ids"
down_revision = "073_stream_track_likes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suno_tasks",
        sa.Column("audio_id_ok", sa.Text(), nullable=True),
    )
    op.add_column(
        "suno_tasks",
        sa.Column("audio_id_alt", sa.Text(), nullable=True),
    )
    op.add_column(
        "stream_tracks",
        sa.Column("suno_audio_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stream_tracks", "suno_audio_id")
    op.drop_column("suno_tasks", "audio_id_alt")
    op.drop_column("suno_tasks", "audio_id_ok")
