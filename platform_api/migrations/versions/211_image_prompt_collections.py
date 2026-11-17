"""Image prompt tags and a background collection selector.

Revision ID: 211
Revises: 210
Create Date: 2026-11-18

Adds lightweight tags to prompt styles so the admin can restrict background
rotation to a collection (for example the JBL portable-speaker set) without
deactivating the rest of the library.
"""

from __future__ import annotations

from alembic import op

revision = "211"
down_revision = "210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS image_prompt_style_tags (
            style_id UUID NOT NULL REFERENCES image_prompt_styles(id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            PRIMARY KEY (style_id, tag)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_image_prompt_style_tags_tag
        ON image_prompt_style_tags(tag)
        """
    )
    # Portable speaker backgrounds with JBL branding.
    op.execute(
        """
        INSERT INTO image_prompt_style_tags (style_id, tag)
        SELECT id, 'jbl_speaker'
        FROM image_prompt_styles
        WHERE kind = 'background'
          AND prompt_text ILIKE '%portable%'
          AND prompt_text ILIKE '%JBL%'
        ON CONFLICT DO NOTHING
        """
    )
    # Broader speaker collection.
    op.execute(
        """
        INSERT INTO image_prompt_style_tags (style_id, tag)
        SELECT id, 'speaker'
        FROM image_prompt_styles
        WHERE kind = 'background'
          AND (prompt_text ILIKE '%speaker%' OR prompt_text ILIKE '%subwoofer%')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS image_prompt_style_tags")
