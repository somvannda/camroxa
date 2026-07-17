"""Add vocal_profile to descriptions and secondary_language to batches."""

from alembic import op

revision = "033_description_vocal_profile"
down_revision = "032_onboarding_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE music_descriptions
        ADD COLUMN IF NOT EXISTS vocal_profile JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE batches
        ADD COLUMN IF NOT EXISTS secondary_language VARCHAR(20)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE batches DROP COLUMN IF EXISTS secondary_language")
    op.execute("ALTER TABLE music_descriptions DROP COLUMN IF EXISTS vocal_profile")
