"""suno_tasks.reference_audio_urls: sample/reference audio for a generation

Revision ID: 201
Revises: 200
Create Date: 2026-11-14

"Sample this song" reuses musicapi's existing audio-reference path: the source
clip's audio URL is stored with the queued task and forwarded as `audioUrls` when
the task is submitted, so the reference survives a worker restart.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "201"
down_revision = "200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suno_tasks",
        sa.Column(
            "reference_audio_urls",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("suno_tasks", "reference_audio_urls")
