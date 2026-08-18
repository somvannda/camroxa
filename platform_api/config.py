"""Application settings loaded from environment variables via pydantic-settings."""

from functools import lru_cache
import hashlib
import os

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Digests produced by normalize_jwt_secret for known insecure seeds.
_INSECURE_JWT_DIGESTS = frozenset(
    {
        hashlib.sha256(b"camxora-jwt::change-me-in-production").hexdigest(),
        hashlib.sha256(b"camxora-jwt::camxora-platform-jwt-dev").hexdigest(),
        hashlib.sha256(b"camxora-jwt::").hexdigest(),
    }
)
_INSECURE_JWT_SEEDS = frozenset(
    {
        "",
        "change-me-in-production",
        "camxora-platform-jwt-dev",
    }
)


class Settings(BaseSettings):
    """Platform API configuration.

    All values are loaded from environment variables (or a .env file).
    Prefix: PLATFORM_ for namespacing in shared environments.
    """

    model_config = SettingsConfigDict(
        env_file=("platform_api/.env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="PLATFORM_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Platform API"
    # development | staging | production (also accepts prod)
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Database (PostgreSQL) ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/platform_db"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT / Auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    # Phase 3: shorter access TTL reduces stolen JWT window (H8).
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
    ]

    # --- External API Keys ---
    suno_api_base_url: str = "https://apibox.erweima.ai"
    suno_callback_base_url: str = ""
    suno_callback_hmac_secret: str = ""
    # Comma-separated IPs allowed when HMAC is not configured (dev/staging only).
    suno_callback_allowed_ips: str = ""

    fal_api_base_url: str = "https://fal.run"

    slai_api_base_url: str = ""

    cala_api_base_url: str = "http://localhost:3000"

    deepseek_api_base_url: str = "https://api.deepseek.com"

    # --- Rate Limiting ---
    default_rate_limit: int = 60
    default_rate_window_seconds: int = 60
    suno_rate_limit: int = 20
    suno_rate_window_seconds: int = 10

    # --- External Balance Monitoring ---
    suno_reserve_threshold: int = 100
    suno_balance_cache_ttl_seconds: int = 30

    # --- Generation Timeouts ---
    suno_timeout_seconds: int = 30
    llm_timeout_seconds: int = 120
    image_timeout_seconds: int = 120
    callback_timeout_seconds: int = 300

    # --- SLAI image throttling / retry (stick with cheapest provider) ---
    slai_image_min_interval_seconds: float = 5.0
    slai_image_max_concurrent: int = 1
    slai_image_provider_retries: int = 5
    slai_image_retry_base_delay_seconds: float = 5.0
    slai_image_retry_max_delay_seconds: float = 45.0
    image_fallback_provider_retries: int = 1

    # --- Encryption (Key Pool) ---
    # Required when using the API Key Pool feature.
    # Set env var PLATFORM_ENCRYPTION_MASTER_KEY to a strong random string.
    # Used to derive AES-256 encryption keys for API key values stored at rest.
    encryption_master_key: str = ""

    # --- Email (SMTP) ---
    # Dev: use MailHog at localhost:1025 (no auth needed)
    # Production: set these to your SMTP provider
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    email_from_name: str = "CAMXORA"
    email_from_address: str = "noreply@camxora.com"
    email_verification_expire_minutes: int = 15

    # --- Backup / User Data Reset ---
    backup_dir: str = "./backups/user_data"

    # --- Marketplace ---
    marketplace_storage_path: str = "./marketplace_storage"
    sample_pack_storage_path: str = "./sample_pack_storage"
    sample_pack_url_import_max_mb: int = 1024
    image_output_cache_dir: str = "./image_output_cache"

    # --- Desktop release installer uploads (admin portal) ---
    desktop_release_storage_path: str = "./desktop_release_storage"
    desktop_release_public_base_url: str = ""
    desktop_release_max_upload_mb: int = 500

    # --- Billing / CutLuy ---
    cutluy_api_base_url: str = "https://cutluy.com"
    cutluy_secret_key: str = ""
    cutluy_payment_link_id: str = ""
    # Signing secret from CutLuy Dashboard → Webhooks (distinct from ck_live_…).
    cutluy_webhook_secret: str = ""

    # --- Cloudflare Turnstile (Bot Protection) ---
    # These use CLOUDFLARE_* env names (not PLATFORM_*) to match Cloudflare dashboard naming.
    cloudflare_turnstile_site_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLOUDFLARE_TURNSTILE_SITE_KEY",
            "PLATFORM_CLOUDFLARE_TURNSTILE_SITE_KEY",
        ),
    )
    cloudflare_turnstile_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLOUDFLARE_TURNSTILE_SECRET_KEY",
            "PLATFORM_CLOUDFLARE_TURNSTILE_SECRET_KEY",
        ),
    )
    cloudflare_turnstile_hostnames: str = Field(
        default="",
        validation_alias=AliasChoices(
            "CLOUDFLARE_TURNSTILE_HOSTNAMES",
            "PLATFORM_CLOUDFLARE_TURNSTILE_HOSTNAMES",
        ),
    )  # Comma-separated list of allowed frontend hostnames

    # --- Admin dual-control (Phase 3 / H6) ---
    # Absolute display credits; adjusts at/above this need a second admin.
    # Default 0 = disabled (single-admin ops apply credit adjusts immediately).
    # Set >0 (e.g. 1000) when multiple admins should co-approve large wallets.
    admin_adjust_dual_control_credits: float = 0.0

    # --- Abuse alert thresholds (Phase 3) ---
    abuse_absorb_alert_threshold: int = 20
    abuse_polish_probe_threshold: int = 10
    abuse_redeem_burst_threshold: int = 5
    abuse_redeem_burst_window_seconds: int = 300

    # --- Music web geo / generation freeze ---
    # Empty = auto (on for sandbox/production, off for local). "true"/"false" override.
    music_web_geo_enforce: str = ""
    music_web_geo_allowed_country: str = "KH"
    music_web_gen_freeze_hours: int = 6

    # --- Pipeline stuck-batch housekeeping alert (PLATFORM_WORKERS_REQUIREMENTS.md §8) ---
    # A batch/channel with no draft/Suno/image/asset activity for this long, and not
    # yet fully complete on every configured channel role, is considered "stuck".
    pipeline_stuck_threshold_seconds: int = 900
    # How often the in-process housekeeping loop re-scans for stuck batches.
    pipeline_stuck_scan_interval_seconds: int = 120
    # Per-batch cooldown before the same still-stuck batch alerts admins again.
    pipeline_stuck_alert_cooldown_seconds: int = 1800

    # --- Music streaming (Backblaze B2) ---
    streaming_b2_key_id: str = ""
    streaming_b2_application_key: str = ""
    streaming_b2_bucket: str = "camxora-media"
    streaming_b2_region: str = "us-west-004"
    streaming_b2_endpoint: str = ""
    streaming_cdn_base_url: str = ""
    streaming_stream_url_ttl_seconds: int = 3600

    # --- Fail / absorb budgets (H2) ---
    # After this many platform_absorb failure events per user per UTC day,
    # further AI quota reservations are blocked until the next day.
    daily_fail_absorb_budget: int = 25

    # Auto-retry failed image jobs in the background runner (attempt_count < this).
    # First try is attempt 0→1; with max=3 the job can fail twice then succeed on 3rd, or stop at FAILED.
    image_job_max_attempts: int = 3

    @field_validator("jwt_secret")
    @classmethod
    def normalize_jwt_secret(cls, value: str) -> str:
        """Ensure the effective HS256 secret meets the recommended minimum length.

        Older local environments may still carry short secrets (including the
        original default placeholder). To avoid runtime warnings while keeping
        startup deterministic, short inputs are expanded into a stable SHA-256
        digest rather than using the raw short string directly.
        """
        secret = (value or "").strip()
        if len(secret) >= 32:
            return secret

        seed = secret or "camxora-platform-jwt-dev"
        return hashlib.sha256(f"camxora-jwt::{seed}".encode("utf-8")).hexdigest()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return Settings()


def is_production(settings: Settings | None = None) -> bool:
    """Return True when PLATFORM_ENVIRONMENT is production/prod."""
    resolved = settings or get_settings()
    return (resolved.environment or "").strip().lower() in {"production", "prod"}


def is_sandbox_or_production(settings: Settings | None = None) -> bool:
    """Return True for sandbox/staging/production (fail-closed geo environments)."""
    resolved = settings or get_settings()
    raw = (resolved.environment or "").strip().lower()
    return raw in {"production", "prod", "staging", "sandbox"}


def is_music_web_geo_enforced(settings: Settings | None = None) -> bool:
    """Whether music-web KH-only geo is on.

    Local/dev is off unless PLATFORM_MUSIC_WEB_GEO_ENFORCE=true.
    Sandbox and production fail closed unless explicitly set to false.
    """
    resolved = settings or get_settings()
    raw = (resolved.music_web_geo_enforce or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return is_sandbox_or_production(resolved)


def environment_display_label(settings: Settings | None = None) -> str:
    """Human-facing environment label for ops UI (admin health / status).

    Maps PLATFORM_ENVIRONMENT values to product language:
    production/prod → Production, staging/sandbox → Sandbox, etc.
    """
    resolved = settings or get_settings()
    raw = (resolved.environment or "").strip().lower()
    if raw in {"production", "prod"}:
        return "Production"
    if raw in {"staging", "sandbox"}:
        return "Sandbox"
    if raw in {"development", "dev"}:
        return "Development"
    if raw in {"local", "localhost"}:
        return "Local"
    if raw:
        return raw.replace("_", " ").title()
    return "Unknown"


def validate_production_settings(settings: Settings | None = None) -> None:
    """Fail fast when production would run with unsafe billing/auth settings.

    Raises:
        RuntimeError: When production config is unsafe. Do not swallow at startup.
    """
    resolved = settings or get_settings()
    if not is_production(resolved):
        return

    errors: list[str] = []

    if resolved.debug:
        errors.append(
            "PLATFORM_DEBUG must be false in production "
            "(mock checkout and unauthenticated callback fallbacks require debug)."
        )

    raw_jwt = (os.environ.get("PLATFORM_JWT_SECRET") or "").strip()
    if (
        raw_jwt in _INSECURE_JWT_SEEDS
        or len(raw_jwt) < 32
        or resolved.jwt_secret in _INSECURE_JWT_DIGESTS
    ):
        errors.append(
            "PLATFORM_JWT_SECRET must be set to a unique value of at least 32 characters "
            "(not the default change-me-in-production placeholder)."
        )

    if not (resolved.suno_callback_hmac_secret or "").strip():
        errors.append(
            "PLATFORM_SUNO_CALLBACK_HMAC_SECRET must be set in production "
            "so Suno callbacks cannot forge status/refunds."
        )

    if errors:
        raise RuntimeError(
            "Unsafe production configuration — refusing to start:\n- "
            + "\n- ".join(errors)
        )
