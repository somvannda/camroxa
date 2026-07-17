"""AI Structure mode on batches and streaming catalog metadata columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "060_ai_structure_and_streaming_metadata"
down_revision = "059_channel_prompt_match_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column("structure_mode", sa.String(length=20), nullable=False, server_default="template"),
    )

    op.add_column("stream_albums", sa.Column("genre", sa.String(length=120), nullable=True))
    op.add_column("stream_tracks", sa.Column("genre", sa.String(length=120), nullable=True))
    op.add_column("stream_tracks", sa.Column("track_number", sa.SmallInteger(), nullable=True))
    op.add_column("stream_tracks", sa.Column("cover_storage_key", sa.String(length=1024), nullable=True))
    op.add_column("stream_tracks", sa.Column("suno_image_url", sa.String(length=1000), nullable=True))
    op.add_column("stream_tracks", sa.Column("tags", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("stream_tracks", "tags")
    op.drop_column("stream_tracks", "suno_image_url")
    op.drop_column("stream_tracks", "cover_storage_key")
    op.drop_column("stream_tracks", "track_number")
    op.drop_column("stream_tracks", "genre")
    op.drop_column("stream_albums", "genre")
    op.drop_column("batches", "structure_mode")
