"""Protected playback tables, packaged storage columns, and content keys.

Revision ID: 107_protected_playback
Revises: 106_web_music_stream_ready
Create Date: 2026-08-20
"""

from __future__ import annotations

from alembic import op

revision = "107_protected_playback"
down_revision = "106_web_music_stream_ready"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            subject_type TEXT NOT NULL,
            subject_id UUID NOT NULL,
            variant TEXT NOT NULL,
            algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
            wrapped_key BYTEA NOT NULL,
            key_version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            retired_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_content_keys_subject_version
        ON content_keys (subject_type, subject_id, variant, key_version)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS playback_devices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_public_id TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'music_web',
            ua_hash TEXT,
            webcrypto_spki BYTEA,
            status TEXT NOT NULL DEFAULT 'active',
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_playback_devices_user_public
        ON playback_devices (user_id, device_public_id)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_license_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_id UUID REFERENCES playback_devices(id) ON DELETE SET NULL,
            purpose TEXT NOT NULL,
            subject_type TEXT NOT NULL,
            subject_id UUID NOT NULL,
            variant TEXT NOT NULL DEFAULT 'ok',
            content_key_id UUID REFERENCES content_keys(id) ON DELETE SET NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            wasm_hash TEXT,
            ip_hash TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_content_license_sessions_user
        ON content_license_sessions (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS playback_events (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID,
            device_id UUID,
            session_id UUID,
            subject_type TEXT,
            subject_id UUID,
            variant TEXT,
            event TEXT NOT NULL,
            bytes_served BIGINT NOT NULL DEFAULT 0,
            package_status TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_playback_events_user_created
        ON playback_events (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_playback_events_subject_created
        ON playback_events (subject_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS export_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            device_id UUID,
            suno_task_id UUID,
            variant TEXT,
            format TEXT NOT NULL,
            watermark_id UUID,
            actor TEXT NOT NULL DEFAULT 'owner',
            ip_hash TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_export_events_user_created
        ON export_events (user_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_watermarks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            export_event_id UUID REFERENCES export_events(id) ON DELETE SET NULL,
            user_id UUID,
            payload_hash TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'forensic_v1',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_package_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            subject_type TEXT NOT NULL,
            subject_id UUID NOT NULL,
            variant TEXT NOT NULL DEFAULT 'ok',
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audio_package_jobs_status
        ON audio_package_jobs (status, updated_at)
        """
    )
    op.execute(
        """
        ALTER TABLE stream_tracks
        ADD COLUMN IF NOT EXISTS encrypted_original_storage_key VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS packaged_storage_key VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS packaged_storage_key_b VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS package_status VARCHAR(20) NOT NULL DEFAULT 'none',
        ADD COLUMN IF NOT EXISTS content_key_id UUID,
        ADD COLUMN IF NOT EXISTS packaged_size_bytes BIGINT
        """
    )
    op.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS encrypted_original_key_ok VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS encrypted_original_key_alt VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS packaged_storage_key_ok VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS packaged_storage_key_alt VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS packaged_storage_key_ok_b VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS packaged_storage_key_alt_b VARCHAR(1024),
        ADD COLUMN IF NOT EXISTS package_status_ok VARCHAR(20) NOT NULL DEFAULT 'none',
        ADD COLUMN IF NOT EXISTS package_status_alt VARCHAR(20) NOT NULL DEFAULT 'none',
        ADD COLUMN IF NOT EXISTS content_key_id_ok UUID,
        ADD COLUMN IF NOT EXISTS content_key_id_alt UUID
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE suno_tasks
        DROP COLUMN IF EXISTS content_key_id_alt,
        DROP COLUMN IF EXISTS content_key_id_ok,
        DROP COLUMN IF EXISTS package_status_alt,
        DROP COLUMN IF EXISTS package_status_ok,
        DROP COLUMN IF EXISTS packaged_storage_key_alt_b,
        DROP COLUMN IF EXISTS packaged_storage_key_ok_b,
        DROP COLUMN IF EXISTS packaged_storage_key_alt,
        DROP COLUMN IF EXISTS packaged_storage_key_ok,
        DROP COLUMN IF EXISTS encrypted_original_key_alt,
        DROP COLUMN IF EXISTS encrypted_original_key_ok
        """
    )
    op.execute(
        """
        ALTER TABLE stream_tracks
        DROP COLUMN IF EXISTS packaged_size_bytes,
        DROP COLUMN IF EXISTS content_key_id,
        DROP COLUMN IF EXISTS package_status,
        DROP COLUMN IF EXISTS packaged_storage_key_b,
        DROP COLUMN IF EXISTS packaged_storage_key,
        DROP COLUMN IF EXISTS encrypted_original_storage_key
        """
    )
    op.execute("DROP TABLE IF EXISTS audio_package_jobs")
    op.execute("DROP TABLE IF EXISTS audio_watermarks")
    op.execute("DROP TABLE IF EXISTS export_events")
    op.execute("DROP TABLE IF EXISTS playback_events")
    op.execute("DROP TABLE IF EXISTS content_license_sessions")
    op.execute("DROP TABLE IF EXISTS playback_devices")
    op.execute("DROP TABLE IF EXISTS content_keys")
