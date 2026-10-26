"""Add Studio personas.

Revision ID: 158_studio_personas
Revises: 157_studio_presence
"""

from __future__ import annotations

from alembic import op

revision: str = "158_studio_personas"
down_revision: str | None = "157_studio_presence"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_personas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            styles TEXT NULL,
            description TEXT NULL,
            source_task_id UUID NULL,
            source_clip_id TEXT NULL,
            provider_persona_id TEXT NULL,
            musicapi_job_id TEXT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            error_message TEXT NULL,
            result_json JSONB NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS studio_personas_user_created_idx
            ON studio_personas (user_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS studio_personas")
