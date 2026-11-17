"""Admin-curated image prompt styles and per-job prompt provenance.

Revision ID: 205
Revises: 204
Create Date: 2026-11-16

Adds the prompt library used by desktop image generation, the per-job fields
that make prompt selection and thumbnail mode deterministic across retries, and
the ``last_batch_id`` rotation hint used to avoid repeating a style on the
immediately following batch.
"""

from __future__ import annotations

from alembic import op

revision = "205"
down_revision = "204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_prompt_styles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind TEXT NOT NULL CHECK (kind IN ('background', 'thumbnail')),
            name TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            text_template TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_image_prompt_styles_kind_name
        ON image_prompt_styles(kind, lower(name))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_prompt_styles_kind_active
        ON image_prompt_styles(kind, is_active, sort_order)
        """
    )
    op.execute(
        """
        ALTER TABLE image_jobs
            ADD COLUMN IF NOT EXISTS prompt_style_id UUID
                REFERENCES image_prompt_styles(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS source_mode TEXT,
            ADD COLUMN IF NOT EXISTS thumbnail_mode TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_jobs_prompt_style_id
        ON image_jobs(prompt_style_id)
        """
    )
    op.execute(
        """
        ALTER TABLE image_random_history
            ADD COLUMN IF NOT EXISTS last_batch_id UUID
        """
    )
    # The new image-to-image thumbnail mode replaces the old default. Only the
    # exact previous default is migrated; an explicitly chosen dual_reference or
    # another value is left alone.
    op.execute(
        """
        UPDATE system_settings
        SET value = 'background_text',
            updated_at = NOW()
        WHERE key = 'thumbnailReferenceMode'
          AND lower(value) = 'composite'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_image_jobs_prompt_style_id")
    op.execute(
        """
        ALTER TABLE image_jobs
            DROP COLUMN IF EXISTS thumbnail_mode,
            DROP COLUMN IF EXISTS source_mode,
            DROP COLUMN IF EXISTS prompt_style_id
        """
    )
    op.execute(
        """
        ALTER TABLE image_random_history
            DROP COLUMN IF EXISTS last_batch_id
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_image_prompt_styles_kind_active")
    op.execute("DROP INDEX IF EXISTS uq_image_prompt_styles_kind_name")
    op.execute("DROP TABLE IF EXISTS image_prompt_styles")
