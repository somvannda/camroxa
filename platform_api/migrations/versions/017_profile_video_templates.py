"""Create profile_video_templates for server-side video template storage."""

from alembic import op

revision = "017_profile_video_templates"
down_revision = "016_expand_youtube_upload_jobs_for_merge_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_video_templates (
            id VARCHAR(64) PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            profile_id UUID REFERENCES channel_profiles(id) ON DELETE SET NULL,
            kind VARCHAR(16) NOT NULL DEFAULT 'long',
            name VARCHAR(200) NOT NULL,
            template_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            source VARCHAR(32),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_profile_video_templates_user_id
        ON profile_video_templates(user_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_profile_video_templates_profile_id
        ON profile_video_templates(profile_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_profile_video_templates_user_kind
        ON profile_video_templates(user_id, kind)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile_video_templates")
