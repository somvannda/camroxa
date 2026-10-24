"""Private full-length masters for free-tier previews.

A preview is delivered as a 60-second file, but the full track is kept in a
private Backblaze object so a user who buys a credit pack can unlock the
existing generation instantly instead of regenerating it.

Revision ID: 145_web_music_preview_masters
Revises: 144_web_music_free_previews
Create Date: 2026-10-21
"""

from __future__ import annotations

from alembic import op

revision: str = "145_web_music_preview_masters"
down_revision: str | None = "144_web_music_free_previews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in (
        "b2_full_storage_key_ok",
        "b2_full_storage_key_alt",
        "b2_full_wav_storage_key_ok",
        "b2_full_wav_storage_key_alt",
    ):
        op.execute(
            f"ALTER TABLE suno_tasks ADD COLUMN IF NOT EXISTS {column} TEXT"
        )


def downgrade() -> None:
    for column in (
        "b2_full_storage_key_ok",
        "b2_full_storage_key_alt",
        "b2_full_wav_storage_key_ok",
        "b2_full_wav_storage_key_alt",
    ):
        op.execute(
            f"ALTER TABLE suno_tasks DROP COLUMN IF EXISTS {column}"
        )
