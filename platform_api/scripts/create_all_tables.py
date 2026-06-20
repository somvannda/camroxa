"""Create all missing tables for platform_db.

Applies the full schema from the migration, skipping tables that already exist.
Usage: python platform_api/scripts/create_all_tables.py
"""
import asyncio
import asyncpg

PLATFORM_DSN = "postgresql://postgres:postgres@localhost:5432/platform_db"

# Tables to create (in dependency order) — skip users, refresh_tokens, credit_wallets (already exist)
SCHEMA_SQL = """
-- Plans and Licenses
CREATE TABLE IF NOT EXISTS plans (
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
);

CREATE TABLE IF NOT EXISTS plan_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id),
    promo_price_cents INTEGER NOT NULL,
    max_redemptions INTEGER NOT NULL,
    current_redemptions INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS licenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    license_key VARCHAR(64) UNIQUE NOT NULL,
    plan_id UUID NOT NULL REFERENCES plans(id),
    user_id UUID REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'unassigned',
    activated_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Credit System (credit_wallets already exists)
CREATE TABLE IF NOT EXISTS credit_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    price_cents INTEGER NOT NULL,
    song_credits INTEGER NOT NULL,
    request_count INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS credit_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_identifier VARCHAR(100) NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    credits_per_operation INTEGER NOT NULL CHECK (credits_per_operation >= 1 AND credits_per_operation <= 10000),
    external_cost_cents INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(model_identifier, operation_type)
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    amount INTEGER NOT NULL,
    direction VARCHAR(10) NOT NULL,
    reason VARCHAR(100) NOT NULL,
    ref_id VARCHAR(255),
    pack_id UUID REFERENCES credit_packs(id),
    payment_ref VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_txn_user_created ON credit_transactions(user_id, created_at DESC);

-- Channel Profiles
CREATE TABLE IF NOT EXISTS channel_profiles (
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
);

-- Music Prompts
CREATE TABLE IF NOT EXISTS music_descriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    content TEXT NOT NULL CHECK (char_length(content) BETWEEN 1 AND 5000),
    match_key VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS music_structures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    content TEXT NOT NULL CHECK (char_length(content) BETWEEN 1 AND 5000),
    match_key VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Generation Pipeline
CREATE TABLE IF NOT EXISTS batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    ok_profile_id UUID REFERENCES channel_profiles(id),
    alt_profile_id UUID REFERENCES channel_profiles(id),
    song_count INTEGER NOT NULL CHECK (song_count BETWEEN 1 AND 50),
    language VARCHAR(20) NOT NULL DEFAULT 'en',
    creativity_level INTEGER NOT NULL DEFAULT 50 CHECK (creativity_level BETWEEN 0 AND 100),
    pairing_mode VARCHAR(20) NOT NULL DEFAULT 'match_key',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    ok_run_dir VARCHAR(500),
    alt_run_dir VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS songs (
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
);

CREATE TABLE IF NOT EXISTS suno_tasks (
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
);

CREATE TABLE IF NOT EXISTS image_jobs (
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
);

-- Application Settings
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    key VARCHAR(255) NOT NULL,
    value_type VARCHAR(20) NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, key)
);

CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(255) PRIMARY KEY,
    value_type VARCHAR(20) NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit and Rate Limiting
CREATE TABLE IF NOT EXISTS audit_logs (
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
);

CREATE INDEX IF NOT EXISTS idx_audit_actor_created ON audit_logs(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_created ON audit_logs(action_type, created_at DESC);

CREATE TABLE IF NOT EXISTS rate_limit_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint_type VARCHAR(50) NOT NULL UNIQUE,
    max_requests INTEGER NOT NULL DEFAULT 60,
    window_seconds INTEGER NOT NULL DEFAULT 60,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- WebSocket Notification Queue
CREATE TABLE IF NOT EXISTS notification_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    delivered BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_notif_user_pending ON notification_queue(user_id, delivered, created_at) WHERE delivered = false;

-- Plan Usage Tracking
CREATE TABLE IF NOT EXISTS plan_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    license_id UUID NOT NULL REFERENCES licenses(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    songs_used INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, license_id, period_start)
);
"""


async def main():
    conn = await asyncpg.connect(PLATFORM_DSN)
    try:
        await conn.execute(SCHEMA_SQL)
        print("[DB] All tables created successfully!")

        # Show what we have now
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        )
        print(f"\nTotal tables: {len(tables)}")
        for t in tables:
            print(f"  - {t['table_name']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
