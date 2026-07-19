"""Music description genres and streaming catalog genre arrays."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "062_music_description_genres"
down_revision = "061_image_sample_pack_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "music_descriptions",
        sa.Column(
            "genres",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "stream_albums",
        sa.Column(
            "genres",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "stream_tracks",
        sa.Column(
            "genres",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("stream_tracks", "genres")
    op.drop_column("stream_albums", "genres")
    op.drop_column("music_descriptions", "genres")
