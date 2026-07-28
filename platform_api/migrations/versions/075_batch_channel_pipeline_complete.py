"""Add conclusive desktop pipeline completion flag on batch_channel_assets.

Revision ID: 075_batch_channel_pipeline_complete
Revises: 074_suno_audio_ids
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "075_batch_channel_pipeline_complete"
down_revision = "074_suno_audio_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "batch_channel_assets",
        sa.Column(
            "pipeline_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "batch_channel_assets",
        sa.Column("pipeline_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("batch_channel_assets", "pipeline_completed_at")
    op.drop_column("batch_channel_assets", "pipeline_complete")
