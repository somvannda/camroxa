"""Normalize web-music instrumental flags.

Suno can return ``[Instrumental]`` in the lyrics payload for a simple-mode
request even when the client did not set the instrumental toggle. The task was
then stored with ``instrumental = FALSE`` and a vocal gender, while every other
consumer (downloads, timed lyrics, detail UI) treated it as instrumental.

This backfills existing rows. New generations are normalized in
``WebMusicService.generate``.

Revision ID: 147_web_music_instrumental_flag
Revises: 146_topup_purchase_subscription_nullable
Create Date: 2026-10-25
"""

from __future__ import annotations

from alembic import op

revision: str = "147_web_music_instrumental_flag"
down_revision: str | None = "146_topup_purchase_subscription_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE suno_tasks
        SET instrumental = TRUE,
            vocal_gender = NULL
        WHERE instrumental = FALSE
          AND lower(btrim(coalesce(lyrics, ''))) = '[instrumental]'
        """
    )


def downgrade() -> None:
    # The original flag cannot be reconstructed safely; keep normalized rows.
    pass
