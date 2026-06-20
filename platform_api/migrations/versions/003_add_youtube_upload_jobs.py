"""Add youtube_upload_jobs table for tracking YouTube uploads."""

from alembic import op


def upgrade() -> None:
    op.execute("""
        CREATE TABLE youtube_upload_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            song_id UUID REFERENCES songs(id),
            title VARCHAR(500) NOT NULL,
            description TEXT,
            tags VARCHAR(1000),
            privacy_status VARCHAR(20) NOT NULL DEFAULT 'private',
            youtube_video_id VARCHAR(100),
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX idx_youtube_upload_jobs_user_id
        ON youtube_upload_jobs(user_id)
    """)
    op.execute("""
        CREATE INDEX idx_youtube_upload_jobs_status
        ON youtube_upload_jobs(user_id, status)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS youtube_upload_jobs CASCADE")
