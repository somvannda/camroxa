"""Studio project persistence.

The web Studio editor stores its arrangement as versioned JSON while the API
exposes project CRUD. Tracks, clips, takes, automation and mixer state live in
``data`` so the public project id and ownership model stay stable while the
payload evolves.

Revision ID: 148_studio_projects
Revises: 147_web_music_instrumental_flag
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "148_studio_projects"
down_revision: str | None = "147_web_music_instrumental_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL DEFAULT 'Untitled Project',
            major_version INTEGER NOT NULL DEFAULT 2,
            bpm INTEGER NOT NULL DEFAULT 120 CHECK (bpm BETWEEN 20 AND 300),
            time_signature TEXT NOT NULL DEFAULT '4/4',
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_projects_user_updated_idx
            ON studio_projects (user_id, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_projects_user_title_idx
            ON studio_projects (user_id, lower(title))
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_projects")
