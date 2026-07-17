"""Add per-channel album names on batches."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "038_batch_channel_albums"
down_revision = "037_invitation_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batches", sa.Column("ok_album", sa.String(length=255), nullable=True))
    op.add_column("batches", sa.Column("alt_album", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("batches", "alt_album")
    op.drop_column("batches", "ok_album")
