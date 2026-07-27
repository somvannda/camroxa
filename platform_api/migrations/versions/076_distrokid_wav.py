"""Add DistroKid WAV jobs, monthly usage, and upload history."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "076_distrokid_wav"
down_revision = "075_distrokid_addon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "distrokid_wav_jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("suno_task_id", sa.Text(), nullable=False),
        sa.Column("audio_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("wav_task_id", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("audio_wav_url", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("song_id", sa.UUID(), sa.ForeignKey("songs.id", ondelete="SET NULL")),
        sa.Column("batch_id", sa.UUID(), sa.ForeignKey("batches.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_distrokid_wav_jobs_user_created", "distrokid_wav_jobs", ["user_id", "created_at"])
    op.create_table(
        "distrokid_wav_usage",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "period_key", name="uq_distrokid_wav_usage_user_period"),
    )
    op.create_table(
        "distrokid_upload_history",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("album_name", sa.Text(), nullable=False),
        sa.Column("directory_path", sa.Text()),
        sa.Column("batch_id", sa.Text()),
        sa.Column("track_title", sa.Text(), nullable=False),
        sa.Column("track_role", sa.Text()),
        sa.Column("wav_byte_size", sa.BigInteger()),
        sa.Column("wav_sha256", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="success"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_distrokid_history_user_album", "distrokid_upload_history", ["user_id", "album_name"])
    op.create_index("ix_distrokid_history_user_sha", "distrokid_upload_history", ["user_id", "wav_sha256"])
    op.create_index("ix_distrokid_history_user_title_size", "distrokid_upload_history", ["user_id", "track_title", "wav_byte_size"])


def downgrade() -> None:
    op.drop_table("distrokid_upload_history")
    op.drop_table("distrokid_wav_usage")
    op.drop_table("distrokid_wav_jobs")
