"""Studio operations (stems and future Suno edits).

Revision ID: 149_studio_operations
Revises: 148_studio_projects
Create Date: 2026-10-26
"""

from __future__ import annotations

from alembic import op

revision: str = "149_studio_operations"
down_revision: str | None = "148_studio_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_operations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id UUID NULL REFERENCES studio_projects(id) ON DELETE SET NULL,
            task_id UUID NOT NULL,
            variant TEXT NOT NULL DEFAULT 'ok',
            provider_clip_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'vocal',
            status TEXT NOT NULL DEFAULT 'queued',
            musicapi_job_id TEXT NULL,
            result_json JSONB NULL,
            credits_charged INTEGER NOT NULL DEFAULT 0,
            error_message TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_operations_user_created_idx
            ON studio_operations (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_operations_active_idx
            ON studio_operations (user_id, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_operations")
