"""Remember the Suno clip a Studio upload was mirrored to.

Uploads live in our storage; a mirrored Suno project can only reference Suno
assets. The first time an upload is pushed to Suno we record the resulting clip
id here, so later saves reuse it instead of uploading the same audio again.

Revision ID: 199
Revises: 198
"""

from __future__ import annotations

from alembic import op

revision = "199"
down_revision = "198"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE studio_uploads ADD COLUMN IF NOT EXISTS suno_clip_id TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE studio_uploads DROP COLUMN IF EXISTS suno_clip_id")
