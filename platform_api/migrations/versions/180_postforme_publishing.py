"""Post for Me publishing: account links, job provider fields, results.

Revision ID: 180
Revises: 179

Phase 1 of docs/postforme-publishing-integration-plan.md. The existing
``youtube_upload_jobs`` table stays the single source of truth for upload
status so Progress, Music History, and Admin Pipeline keep working. Post for
Me rows are additive and default the new provider columns to the legacy
direct-YouTube provider.

Renumbered from 178: main already owns 178 (credit reason) and 179 (the
re-assert), and a tree can only have one migration per revision id.
"""

from __future__ import annotations

from alembic import op

revision = "180"
down_revision = "179"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Generalize the upload job table -------------------------------------
    op.execute(
        """
        ALTER TABLE youtube_upload_jobs
            ADD COLUMN IF NOT EXISTS provider VARCHAR(32) NOT NULL DEFAULT 'youtube_direct',
            ADD COLUMN IF NOT EXISTS platform VARCHAR(32) NOT NULL DEFAULT 'youtube',
            ADD COLUMN IF NOT EXISTS social_account_id TEXT,
            ADD COLUMN IF NOT EXISTS postforme_post_id TEXT,
            ADD COLUMN IF NOT EXISTS postforme_result_id TEXT,
            ADD COLUMN IF NOT EXISTS media_url TEXT,
            ADD COLUMN IF NOT EXISTS upload_url TEXT,
            ADD COLUMN IF NOT EXISTS upload_expires_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,
            ADD COLUMN IF NOT EXISTS file_checksum TEXT,
            ADD COLUMN IF NOT EXISTS thumbnail_path TEXT,
            ADD COLUMN IF NOT EXISTS thumbnail_media_url TEXT,
            ADD COLUMN IF NOT EXISTS profile_config JSONB,
            ADD COLUMN IF NOT EXISTS credits_charged_units BIGINT NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS credit_ref_id TEXT,
            ADD COLUMN IF NOT EXISTS error_code VARCHAR(64),
            ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS result_payload JSONB
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_youtube_upload_jobs_provider_status
            ON youtube_upload_jobs(provider, status, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_youtube_upload_jobs_credit_ref
            ON youtube_upload_jobs(credit_ref_id)
            WHERE credit_ref_id IS NOT NULL
        """
    )

    # --- Post for Me connected accounts --------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_social_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            profile_id UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
            provider VARCHAR(32) NOT NULL DEFAULT 'postforme',
            platform VARCHAR(32) NOT NULL,
            postforme_account_id TEXT NOT NULL,
            external_id TEXT,
            username TEXT,
            display_name TEXT,
            avatar_url TEXT,
            status VARCHAR(24) NOT NULL DEFAULT 'connected',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, profile_id, postforme_account_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_social_accounts_user_profile
            ON publish_social_accounts(user_id, profile_id, platform)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_social_accounts_provider_account
            ON publish_social_accounts(provider, postforme_account_id)
        """
    )

    # --- OAuth connect attempts ----------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_connect_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            profile_id UUID NOT NULL REFERENCES channel_profiles(id) ON DELETE CASCADE,
            platform VARCHAR(32) NOT NULL,
            status VARCHAR(32) NOT NULL DEFAULT 'pending_browser',
            account_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_message TEXT,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_connect_sessions_user_profile
            ON publish_connect_sessions(user_id, profile_id, updated_at DESC)
        """
    )

    # --- Per-platform post results -------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_job_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES youtube_upload_jobs(id) ON DELETE CASCADE,
            platform VARCHAR(32) NOT NULL,
            social_account_id TEXT NOT NULL,
            postforme_result_id TEXT,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            platform_post_id TEXT,
            platform_url TEXT,
            error_message TEXT,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_publish_job_results_postforme_result
            ON publish_job_results(postforme_result_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_job_results_job
            ON publish_job_results(job_id)
        """
    )

    # --- Raw webhook ledger (idempotency + debugging) ------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_webhook_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type VARCHAR(64) NOT NULL,
            postforme_post_id TEXT,
            payload JSONB NOT NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ,
            error_message TEXT
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publish_webhook_events_post
            ON publish_webhook_events(postforme_post_id, received_at DESC)
        """
    )

    # --- Default 5-credit upload price ---------------------------------------
    # credit_pricing stores micro-credit units: 5 credits = 50_000 units.
    # external_cost_cents is a legacy name; it stores cost micro-units
    # (1 credit ~= $0.01 Post for Me COGS at the $10 / 1,000-post tier).
    # ON CONFLICT DO NOTHING keeps an admin override intact.
    op.execute(
        """
        INSERT INTO credit_pricing (
            ai_service,
            operation_type,
            sub_model,
            credits_per_operation,
            external_cost_cents,
            needs_review
        )
        VALUES ('postforme', 'upload', '', 50000, 10000, FALSE)
        ON CONFLICT (ai_service, operation_type, sub_model) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM credit_pricing WHERE ai_service = 'postforme' AND operation_type = 'upload'"
    )
    op.execute("DROP TABLE IF EXISTS publish_webhook_events CASCADE")
    op.execute("DROP TABLE IF EXISTS publish_job_results CASCADE")
    op.execute("DROP TABLE IF EXISTS publish_connect_sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS publish_social_accounts CASCADE")
    op.execute("DROP INDEX IF EXISTS uq_youtube_upload_jobs_credit_ref")
    op.execute("DROP INDEX IF EXISTS idx_youtube_upload_jobs_provider_status")
    op.execute(
        """
        ALTER TABLE youtube_upload_jobs
            DROP COLUMN IF EXISTS result_payload,
            DROP COLUMN IF EXISTS scheduled_at,
            DROP COLUMN IF EXISTS error_code,
            DROP COLUMN IF EXISTS credit_ref_id,
            DROP COLUMN IF EXISTS credits_charged_units,
            DROP COLUMN IF EXISTS thumbnail_path,
            DROP COLUMN IF EXISTS thumbnail_media_url,
            DROP COLUMN IF EXISTS profile_config,
            DROP COLUMN IF EXISTS file_checksum,
            DROP COLUMN IF EXISTS file_size_bytes,
            DROP COLUMN IF EXISTS upload_expires_at,
            DROP COLUMN IF EXISTS upload_url,
            DROP COLUMN IF EXISTS media_url,
            DROP COLUMN IF EXISTS postforme_result_id,
            DROP COLUMN IF EXISTS postforme_post_id,
            DROP COLUMN IF EXISTS social_account_id,
            DROP COLUMN IF EXISTS platform,
            DROP COLUMN IF EXISTS provider
        """
    )
