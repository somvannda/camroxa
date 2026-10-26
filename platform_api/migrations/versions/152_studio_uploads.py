"""Durable user audio uploads for Studio.

Revision ID: 152_studio_uploads
Revises: 151_studio_stems_12_price_60
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "152_studio_uploads"
down_revision: str | None = "151_studio_stems_12_price_60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_uploads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            storage_key TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size_bytes BIGINT NOT NULL DEFAULT 0,
            duration_seconds DOUBLE PRECISION NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_uploads_user_created_idx
            ON studio_uploads (user_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_uploads")
