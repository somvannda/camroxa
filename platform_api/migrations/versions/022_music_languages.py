"""Create music_languages table for admin-managed generation language options."""

from alembic import op

revision = "022_music_languages"
down_revision = "021_user_prompt_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS music_languages (
            code VARCHAR(20) PRIMARY KEY,
            label VARCHAR(80) NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_music_languages_enabled_sort
        ON music_languages (enabled, sort_order, code)
        """
    )
    op.execute(
        """
        INSERT INTO music_languages (code, label, enabled, sort_order)
        VALUES
            ('en', 'English', TRUE, 0),
            ('km', 'Khmer', FALSE, 1),
            ('de', 'German', FALSE, 2),
            ('es', 'Spanish', FALSE, 3),
            ('fr', 'French', FALSE, 4)
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS music_languages")
