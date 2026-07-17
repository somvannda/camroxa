"""Streaming catalog tables for music.camxora.com."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "043_streaming_catalog"
down_revision = "042_marketplace_add_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stream_albums",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("album_name", sa.String(length=255), nullable=False),
        sa.Column("album_slug", sa.String(length=255), nullable=False),
        sa.Column("channel_role", sa.String(length=10), nullable=False, server_default="ok"),
        sa.Column("cover_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("publish_status", sa.String(length=20), nullable=False, server_default="published"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("user_id", "album_slug", name="uq_stream_albums_user_slug"),
    )
    op.create_index("idx_stream_albums_publish_status", "stream_albums", ["publish_status"])
    op.create_index("idx_stream_albums_user_id", "stream_albums", ["user_id"])

    op.create_table(
        "stream_tracks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("album_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stream_albums.id", ondelete="CASCADE"), nullable=False),
        sa.Column("song_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("songs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suno_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suno_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("lyrics", sa.Text(), nullable=True),
        sa.Column("variant", sa.String(length=10), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False, server_default="audio/mpeg"),
        sa.Column("publish_status", sa.String(length=20), nullable=False, server_default="published"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("suno_task_id", "variant", name="uq_stream_tracks_suno_variant"),
    )
    op.create_index("idx_stream_tracks_album_id", "stream_tracks", ["album_id"])
    op.create_index("idx_stream_tracks_publish_status", "stream_tracks", ["publish_status"])
    op.create_index("idx_stream_tracks_user_id", "stream_tracks", ["user_id"])

    op.create_table(
        "stream_upload_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("song_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("songs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suno_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suno_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("album_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stream_albums.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_stream_upload_jobs_status", "stream_upload_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("stream_upload_jobs")
    op.drop_table("stream_tracks")
    op.drop_table("stream_albums")
