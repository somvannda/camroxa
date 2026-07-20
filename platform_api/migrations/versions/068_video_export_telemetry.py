"""Video export telemetry for desktop duration/hardware diagnostics."""

from __future__ import annotations

from alembic import op

revision = "068_video_export_telemetry"
down_revision = "067_song_suno_sanitize_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS video_export_telemetry (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            operation_type VARCHAR(32) NOT NULL,
            ref_id VARCHAR(255),
            track_count INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER,
            codec VARCHAR(64),
            resolution VARCHAR(32),
            fps INTEGER,
            export_tier VARCHAR(32),
            speed_mode VARCHAR(32),
            hw_cpu VARCHAR(255),
            hw_gpu VARCHAR(255),
            hw_encoder VARCHAR(64),
            app_version VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_video_export_telemetry_user_created
        ON video_export_telemetry (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_video_export_telemetry_op_created
        ON video_export_telemetry (operation_type, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_video_export_telemetry_op_created")
    op.execute("DROP INDEX IF EXISTS idx_video_export_telemetry_user_created")
    op.execute("DROP TABLE IF EXISTS video_export_telemetry")
