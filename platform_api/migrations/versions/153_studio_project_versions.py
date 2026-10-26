"""Manual Studio project version snapshots.

Revision ID: 153_studio_project_versions
Revises: 152_studio_uploads
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "153_studio_project_versions"
down_revision: str | None = "152_studio_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_project_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            label TEXT NULL,
            title TEXT NOT NULL,
            bpm INTEGER NOT NULL,
            time_signature TEXT NOT NULL,
            data JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_project_versions_project_created_idx
            ON studio_project_versions (project_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_project_versions")
