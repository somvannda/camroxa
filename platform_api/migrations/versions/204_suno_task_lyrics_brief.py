"""Keep a Simple-mode song's lyrics brief so a failed song can be retried

Revision ID: 204
Revises: 203
Create Date: 2026-11-15

Simple mode queues a song with no lyrics and writes them in the worker from a
``lyrics_brief`` (prompt, theme, structure, title). That brief only travelled in
the job payload, so once the row failed and was refunded, nothing could rebuild
the song: "Retry this song" (which the desktop Create page already offers) needs
the same description back. Store it on the row.

Nullable on purpose: advanced-mode songs, sounds and every row created before
this migration have no brief, and are retried through the Create form instead.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "204"
down_revision = "203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suno_tasks",
        sa.Column("lyrics_brief", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("suno_tasks", "lyrics_brief")
