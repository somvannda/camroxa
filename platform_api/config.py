"""Application settings loaded from environment variables via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    )

    # --- Application ---
    app_name: str = "Platform API"
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
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    # --- External API Keys ---
    suno_api_key: str = ""
    suno_api_base_url: str = "https://apibox.erweima.ai"
    suno_callback_base_url: str = ""
    suno_callback_hmac_secret: str = ""

    fal_api_key: str = ""
    fal_api_base_url: str = "https://fal.run"

    slai_api_key: str = ""
    slai_api_base_url: str = ""

    deepseek_api_key: str = ""
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
    llm_timeout_seconds: int = 15
    image_timeout_seconds: int = 60
    callback_timeout_seconds: int = 300

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


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return Settings()
