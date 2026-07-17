"""Add YouTube connected account and OAuth session tables."""

from alembic import op

revision = "007_add_youtube_connection_flow"
down_revision = "006_add_youtube_oauth_apps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS youtube_connected_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            profile_id UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
            oauth_app_id UUID REFERENCES youtube_oauth_apps(id) ON DELETE SET NULL,
            channel_id TEXT NOT NULL,
            channel_title TEXT NOT NULL,
            encrypted_refresh_token BYTEA NOT NULL,
            scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(profile_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_youtube_connected_accounts_user_profile
            ON youtube_connected_accounts(user_id, profile_id)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS youtube_connect_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            profile_id UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
            oauth_app_id UUID NOT NULL REFERENCES youtube_oauth_apps(id) ON DELETE CASCADE,
            state_token TEXT NOT NULL UNIQUE,
            status VARCHAR(32) NOT NULL DEFAULT 'pending_browser',
            encrypted_refresh_token BYTEA,
            scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
            channels JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_message TEXT,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_youtube_connect_sessions_user_profile
            ON youtube_connect_sessions(user_id, profile_id, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_youtube_connect_sessions_state
            ON youtube_connect_sessions(state_token)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_youtube_connect_sessions_state")
    op.execute("DROP INDEX IF EXISTS idx_youtube_connect_sessions_user_profile")
    op.execute("DROP TABLE IF EXISTS youtube_connect_sessions CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_youtube_connected_accounts_user_profile")
    op.execute("DROP TABLE IF EXISTS youtube_connected_accounts CASCADE")
