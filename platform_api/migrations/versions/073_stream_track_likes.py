"""Liked tracks for music portal library."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "073_stream_track_likes"
down_revision = "072_stream_track_play_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stream_track_likes",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "track_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stream_tracks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "track_id", name="pk_stream_track_likes"),
    )
    op.create_index(
        "idx_stream_track_likes_user_created",
        "stream_track_likes",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_stream_track_likes_user_created", table_name="stream_track_likes")
    op.drop_table("stream_track_likes")
