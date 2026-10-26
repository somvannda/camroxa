"""Read-only Studio project share links.

Revision ID: 154_studio_project_shares
Revises: 153_studio_project_versions
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "154_studio_project_shares"
down_revision: str | None = "153_studio_project_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_project_shares (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES studio_projects(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NULL,
            revoked_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_project_shares_project_idx
            ON studio_project_shares (project_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_project_shares")
