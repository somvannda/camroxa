"""Initial database schema.

Revision ID: 001_initial_schema
Revises: None
Create Date: 2024-01-01 00:00:00.000000+00:00

Creates all tables for the Platform API:
- users, refresh_tokens
- plans, plan_offers, licenses
- credit_wallets, credit_packs, credit_pricing, credit_transactions
- channel_profiles
- music_descriptions, music_structures
- batches, songs, suno_tasks, image_jobs
- user_settings, system_settings
- audit_logs, rate_limit_config
- notification_queue, plan_usage
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Users and Authentication ───────────────────────────────────────────
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            display_name VARCHAR(50) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            suspension_reason TEXT,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE refresh_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            token_hash VARCHAR(64) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── Plans and Licenses ─────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(50) NOT NULL UNIQUE,
            price_cents INTEGER NOT NULL,
            billing_cycle_days INTEGER,
            profile_allowance INTEGER NOT NULL,
            monthly_song_quota INTEGER,
            daily_song_limit_per_channel INTEGER NOT NULL DEFAULT 7,
            is_active BOOLEAN NOT NULL DEFAULT true,
            effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE plan_offers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id UUID NOT NULL REFERENCES plans(id),
            promo_price_cents INTEGER NOT NULL,
            max_redemptions INTEGER NOT NULL,
            current_redemptions INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE licenses (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            license_key VARCHAR(64) UNIQUE NOT NULL,
            plan_id UUID NOT NULL REFERENCES plans(id),
            user_id UUID REFERENCES users(id),
            status VARCHAR(20) NOT NULL DEFAULT 'unassigned',
            activated_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── Credit System ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE credit_wallets (
            user_id UUID PRIMARY KEY REFERENCES users(id),
            balance INTEGER NOT NULL DEFAULT 0
                CHECK (balance >= 0 AND balance <= 10000000),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE credit_packs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            price_cents INTEGER NOT NULL,
            song_credits INTEGER NOT NULL,
            request_count INTEGER NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE credit_pricing (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_identifier VARCHAR(100) NOT NULL,
            operation_type VARCHAR(50) NOT NULL,
            credits_per_operation INTEGER NOT NULL
                CHECK (credits_per_operation >= 1 AND credits_per_operation <= 10000),
            external_cost_cents INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(model_identifier, operation_type)
        )
    """)

    op.execute("""
        CREATE TABLE credit_transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            amount INTEGER NOT NULL,
            direction VARCHAR(10) NOT NULL,
            reason VARCHAR(100) NOT NULL,
            ref_id VARCHAR(255),
            pack_id UUID REFERENCES credit_packs(id),
            payment_ref VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX idx_credit_txn_user_created
            ON credit_transactions(user_id, created_at DESC)
    """)

    # ─── Channel Profiles ───────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE channel_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            name VARCHAR(100) NOT NULL,
            folder_name VARCHAR(100),
            run_prefix VARCHAR(64),
            logo_path VARCHAR(500),
            video_template_id VARCHAR(64),
            reel_template_id VARCHAR(64),
            output_resolution VARCHAR(20) DEFAULT '1920x1080',
            image_config JSONB NOT NULL DEFAULT '{}',
            youtube_config JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, name)
        )
    """)

    # ─── Music Prompts (Admin-managed) ──────────────────────────────────────
    op.execute("""
        CREATE TABLE music_descriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL UNIQUE,
            content TEXT NOT NULL
                CHECK (char_length(content) BETWEEN 1 AND 5000),
            match_key VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE music_structures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL UNIQUE,
            content TEXT NOT NULL
                CHECK (char_length(content) BETWEEN 1 AND 5000),
            match_key VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── Generation Pipeline ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE batches (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            ok_profile_id UUID REFERENCES channel_profiles(id),
            alt_profile_id UUID REFERENCES channel_profiles(id),
            song_count INTEGER NOT NULL
                CHECK (song_count BETWEEN 1 AND 50),
            language VARCHAR(20) NOT NULL DEFAULT 'en',
            creativity_level INTEGER NOT NULL DEFAULT 50
                CHECK (creativity_level BETWEEN 0 AND 100),
            pairing_mode VARCHAR(20) NOT NULL DEFAULT 'match_key',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            ok_run_dir VARCHAR(500),
            alt_run_dir VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE songs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            batch_id UUID NOT NULL REFERENCES batches(id),
            batch_index INTEGER NOT NULL,
            user_id UUID NOT NULL REFERENCES users(id),
            title VARCHAR(255),
            album VARCHAR(255),
            lyrics TEXT,
            description_id UUID REFERENCES music_descriptions(id),
            structure_id UUID REFERENCES music_structures(id),
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE suno_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            song_id UUID REFERENCES songs(id),
            user_id UUID NOT NULL REFERENCES users(id),
            batch_id UUID REFERENCES batches(id),
            request_hash VARCHAR(64) NOT NULL,
            model VARCHAR(20) NOT NULL,
            title VARCHAR(255) NOT NULL,
            lyrics TEXT,
            style VARCHAR(255),
            instrumental BOOLEAN NOT NULL DEFAULT false,
            external_task_id VARCHAR(100),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            audio_url_ok VARCHAR(1000),
            audio_url_alt VARCHAR(1000),
            output_dir_ok VARCHAR(500),
            output_dir_alt VARCHAR(500),
            downloaded_ok BOOLEAN NOT NULL DEFAULT false,
            downloaded_alt BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, request_hash)
        )
    """)

    op.execute("""
        CREATE TABLE image_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            song_id UUID REFERENCES songs(id),
            user_id UUID NOT NULL REFERENCES users(id),
            batch_id UUID REFERENCES batches(id),
            profile_id UUID REFERENCES channel_profiles(id),
            kind VARCHAR(20) NOT NULL,
            channel_role VARCHAR(10) NOT NULL,
            prompt TEXT,
            provider VARCHAR(20),
            resolution VARCHAR(20) DEFAULT '1920x1080',
            style_strength NUMERIC(3,2) DEFAULT 0.6,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            output_image_path VARCHAR(500),
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── Application Settings ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE user_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            key VARCHAR(255) NOT NULL,
            value_type VARCHAR(20) NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, key)
        )
    """)

    op.execute("""
        CREATE TABLE system_settings (
            key VARCHAR(255) PRIMARY KEY,
            value_type VARCHAR(20) NOT NULL,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── Audit and Rate Limiting ────────────────────────────────────────────
    op.execute("""
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_id UUID REFERENCES users(id),
            action_type VARCHAR(100) NOT NULL,
            target_resource VARCHAR(255),
            outcome VARCHAR(20) NOT NULL,
            credit_impact INTEGER NOT NULL DEFAULT 0,
            source_ip VARCHAR(45),
            client_id VARCHAR(100),
            endpoint_path VARCHAR(255),
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE INDEX idx_audit_actor_created
            ON audit_logs(actor_id, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_audit_action_created
            ON audit_logs(action_type, created_at DESC)
    """)

    op.execute("""
        CREATE TABLE rate_limit_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            endpoint_type VARCHAR(50) NOT NULL UNIQUE,
            max_requests INTEGER NOT NULL DEFAULT 60,
            window_seconds INTEGER NOT NULL DEFAULT 60,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # ─── WebSocket Notification Queue ───────────────────────────────────────
    op.execute("""
        CREATE TABLE notification_queue (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            event_type VARCHAR(50) NOT NULL,
            payload JSONB NOT NULL,
            delivered BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
        )
    """)

    op.execute("""
        CREATE INDEX idx_notif_user_pending
            ON notification_queue(user_id, delivered, created_at)
            WHERE delivered = false
    """)

    # ─── Plan Usage Tracking ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE plan_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            license_id UUID NOT NULL REFERENCES licenses(id),
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            songs_used INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, license_id, period_start)
        )
    """)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.execute("DROP TABLE IF EXISTS plan_usage CASCADE")
    op.execute("DROP TABLE IF EXISTS notification_queue CASCADE")
    op.execute("DROP TABLE IF EXISTS rate_limit_config CASCADE")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS system_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS user_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS image_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS suno_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS songs CASCADE")
    op.execute("DROP TABLE IF EXISTS batches CASCADE")
    op.execute("DROP TABLE IF EXISTS music_structures CASCADE")
    op.execute("DROP TABLE IF EXISTS music_descriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS channel_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_pricing CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_packs CASCADE")
    op.execute("DROP TABLE IF EXISTS credit_wallets CASCADE")
    op.execute("DROP TABLE IF EXISTS licenses CASCADE")
    op.execute("DROP TABLE IF EXISTS plan_offers CASCADE")
    op.execute("DROP TABLE IF EXISTS plans CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
