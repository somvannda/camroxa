"""Snapshot DistroKid + Short automation flags on batches."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "077_batch_auto_distrokid"
down_revision = "076_distrokid_wav"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batches",
        sa.Column(
            "auto_distrokid",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "auto_reel_after_video",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("batches", "auto_reel_after_video")
    op.drop_column("batches", "auto_distrokid")
