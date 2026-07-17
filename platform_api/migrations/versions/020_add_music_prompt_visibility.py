"""Add visibility flags to music prompt catalogs.

Revision ID: 020_add_music_prompt_visibility
Revises: 019_user_music_prompts
"""

from alembic import op


revision = "020_add_music_prompt_visibility"
down_revision = "019_user_music_prompts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE music_descriptions
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
        """
    )
    op.execute(
        """
        ALTER TABLE music_structures
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_music_descriptions_user_active
        ON music_descriptions(user_id, is_active, name)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_music_structures_user_active
        ON music_structures(user_id, is_active, name)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_music_structures_user_active")
    op.execute("DROP INDEX IF EXISTS idx_music_descriptions_user_active")
    op.execute("ALTER TABLE music_structures DROP COLUMN IF EXISTS is_active")
    op.execute("ALTER TABLE music_descriptions DROP COLUMN IF EXISTS is_active")
