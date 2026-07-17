"""Store invitation codes encrypted for admin display."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "039_invitation_code_encrypted_storage"
down_revision = "038_batch_channel_albums"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invitation_codes", sa.Column("encrypted_code", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("invitation_codes", "encrypted_code")
