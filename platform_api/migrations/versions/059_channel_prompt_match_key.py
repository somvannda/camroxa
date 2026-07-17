"""Add match_key to channel_prompts for music description pairing."""

from alembic import op

revision = "059_channel_prompt_match_key"
down_revision = "058_email_verifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE channel_prompts
        ADD COLUMN IF NOT EXISTS match_key VARCHAR(100)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_channel_prompts_match_key
        ON channel_prompts(match_key)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_channel_prompts_match_key")
    op.execute("ALTER TABLE channel_prompts DROP COLUMN IF EXISTS match_key")
