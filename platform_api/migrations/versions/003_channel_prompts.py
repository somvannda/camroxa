"""Add channel_prompts table for onboarding wizard prompts.

Stores admin-configured prompts used by the channel setup wizard
to generate channel names, logos, covers, descriptions, keywords, and tags.
"""

from alembic import op

revision = "003_channel_prompts"
down_revision = "003_add_youtube_upload_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE channel_prompts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            content TEXT NOT NULL
                CHECK (char_length(content) BETWEEN 1 AND 5000),
            category VARCHAR(50) NOT NULL,
            genre VARCHAR(100) NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(name, category)
        )
    """)
    op.execute("""
        CREATE INDEX idx_channel_prompts_category ON channel_prompts(category)
    """)
    op.execute("""
        CREATE INDEX idx_channel_prompts_genre ON channel_prompts(genre)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS channel_prompts")
