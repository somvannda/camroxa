"""FastAPI dependency injection setup.

Provides database pool, Redis connection, repositories, services, and clients
as FastAPI dependencies (via Depends). All production dependencies are wired
as lazy singletons — created once on first access and shared across requests.

The lifespan in main.py is responsible for:
  - Creating the DB pool and Redis connection at startup
  - Cleaning them up at shutdown

Tests can override any dependency via `app.dependency_overrides[get_xxx] = ...`.
"""

from __future__ import annotations

import logging
from typing import Any

from platform_api.config import Settings, get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Singleton state (set during app lifespan startup, cleared on shutdown)
# ---------------------------------------------------------------------------

_db_pool: Any | None = None
_redis: Any | None = None


def set_db_pool(pool: Any) -> None:
    """Set the database connection pool (called during lifespan startup)."""
    global _db_pool
    _db_pool = pool


def set_redis(redis: Any) -> None:
    """Set the Redis connection (called during lifespan startup)."""
    global _redis
    _redis = redis


def clear_connections() -> None:
    """Clear connection references (called during lifespan shutdown)."""
    global _db_pool, _redis
    _db_pool = None
    _redis = None


# ---------------------------------------------------------------------------
# Core dependency providers
# ---------------------------------------------------------------------------


def get_config() -> Settings:
    """Dependency that returns the application settings."""
    return get_settings()


def get_db_pool() -> Any:
    """Dependency that returns the asyncpg connection pool.

    Raises RuntimeError if the pool hasn't been initialized (app not started).
    """
    if _db_pool is None:
        raise RuntimeError(
            "Database pool not initialized. Ensure the app lifespan has started."
        )
    return _db_pool


def get_redis() -> Any:
    """Dependency that returns the Redis connection.

    Raises RuntimeError if Redis hasn't been initialized (app not started).
    """
    if _redis is None:
        raise RuntimeError(
            "Redis connection not initialized. Ensure the app lifespan has started."
        )
    return _redis


# ---------------------------------------------------------------------------
# Repository providers
# ---------------------------------------------------------------------------


def get_user_repo():
    """Dependency that returns the UserRepository instance."""
    from platform_api.repositories.user_repo import UserRepository

    return UserRepository(pool=get_db_pool())


def get_license_repo():
    """Dependency that returns the LicenseRepository instance."""
    from platform_api.repositories.license_repo import LicenseRepository

    return LicenseRepository(pool=get_db_pool())


def get_plan_repo():
    """Dependency that returns the PlanRepository instance."""
    from platform_api.repositories.license_repo import PlanRepository

    return PlanRepository(pool=get_db_pool())


def get_credit_repo():
    """Dependency that returns the CreditRepository instance."""
    from platform_api.repositories.credit_repo import CreditRepository

    return CreditRepository(pool=get_db_pool())


def get_profile_repo():
    """Dependency that returns the ProfileRepository instance."""
    from platform_api.repositories.profile_repo import ProfileRepository

    return ProfileRepository(pool=get_db_pool())


def get_prompt_repo():
    """Dependency that returns the PromptRepository instance."""
    from platform_api.repositories.prompt_repo import PromptRepository

    return PromptRepository(pool=get_db_pool())


def get_batch_repo():
    """Dependency that returns the BatchRepository instance."""
    from platform_api.repositories.batch_repo import BatchRepository

    return BatchRepository(pool=get_db_pool())


def get_settings_repo():
    """Dependency that returns the SettingsRepository instance."""
    from platform_api.repositories.settings_repo import SettingsRepository

    return SettingsRepository(pool=get_db_pool())


def get_audit_repo():
    """Dependency that returns the AuditRepository instance."""
    from platform_api.repositories.audit_repo import AuditRepository

    return AuditRepository(db=get_db_pool())


def get_rate_limit_config_repo():
    """Dependency that returns the RateLimitConfigRepository instance."""
    from platform_api.repositories.rate_limit_repo import RateLimitConfigRepository

    return RateLimitConfigRepository(db=get_db_pool())


# ---------------------------------------------------------------------------
# Client providers
# ---------------------------------------------------------------------------


def get_suno_client():
    """Dependency that returns the SunoClient instance."""
    from platform_api.clients.suno_client import SunoClient

    return SunoClient(settings=get_settings())


def get_fal_client():
    """Dependency that returns the FalClient instance."""
    from platform_api.clients.fal_client import FalClient

    return FalClient(settings=get_settings())


def get_slai_client():
    """Dependency that returns the SlaiClient instance."""
    from platform_api.clients.slai_client import SlaiClient

    return SlaiClient(settings=get_settings())


def get_cala_client():
    """Dependency that returns the CalaClient instance."""
    from platform_api.clients.cala_client import CalaClient

    return CalaClient(settings=get_settings())


def get_llm_client():
    """Dependency that returns the LlmClient instance."""
    from platform_api.clients.llm_client import LlmClient

    return LlmClient(settings=get_settings())


# ---------------------------------------------------------------------------
# Service providers
# ---------------------------------------------------------------------------


def get_refresh_token_repo():
    """Dependency that returns the RefreshTokenRepository instance."""
    from platform_api.repositories.refresh_token_repo import RefreshTokenRepository

    return RefreshTokenRepository(pool=get_db_pool())


def get_lockout():
    """Dependency that returns the AccountLockout instance."""
    from platform_api.services.lockout import AccountLockout

    return AccountLockout(redis=get_redis())


def get_auth_service():
    """Dependency that returns the AuthService instance."""
    from platform_api.services.auth_service import AuthService

    return AuthService(
        config=get_settings(),
        user_repo=get_user_repo(),
        refresh_token_repo=get_refresh_token_repo(),
    )


def get_user_service():
    """Dependency that returns the UserService instance."""
    from platform_api.services.user_service import UserService

    return UserService(
        user_repo=get_user_repo(),
        auth_service=get_auth_service(),
    )


def get_license_service():
    """Dependency that returns the LicenseService instance."""
    from platform_api.services.license_service import LicenseService

    return LicenseService(
        license_repo=get_license_repo(),
        plan_repo=get_plan_repo(),
        credit_repo=get_credit_repo(),
    )


def get_credit_service():
    """Dependency that returns the CreditService instance."""
    from platform_api.services.credit_service import CreditService

    return CreditService(
        credit_repo=get_credit_repo(),
        license_repo=get_license_repo(),
        plan_repo=get_plan_repo(),
    )


def get_credit_pricing_service():
    """Dependency that returns the CreditPricingService instance."""
    from platform_api.services.credit_pricing_service import CreditPricingService

    return CreditPricingService(pricing_repo=get_credit_repo(), db_pool=get_db_pool())


def get_usage_tracking_repo():
    """Dependency that returns the UsageTrackingRepository instance."""
    from platform_api.repositories.usage_tracking_repo import UsageTrackingRepository

    return UsageTrackingRepository(pool=get_db_pool())


def get_usage_enforcement_service():
    """Dependency that returns the UsageEnforcementService instance."""
    from platform_api.services.usage_enforcement_service import UsageEnforcementService

    return UsageEnforcementService(
        credit_repo=get_credit_repo(),
        usage_repo=get_usage_tracking_repo(),
        plan_repo=get_plan_repo(),
        pricing_repo=get_credit_repo(),
        redis=get_redis(),
    )


def get_profile_service():
    """Dependency that returns the ProfileService instance."""
    from platform_api.services.profile_service import ProfileService

    return ProfileService(
        profile_repo=get_profile_repo(),
        license_repo=get_license_repo(),
        plan_repo=get_plan_repo(),
    )


def get_prompt_service():
    """Dependency that returns the PromptService instance."""
    from platform_api.services.prompt_service import PromptService

    return PromptService(prompt_repo=get_prompt_repo())


def get_generation_service():
    """Dependency that returns the GenerationService instance."""
    from platform_api.services.generation_service import GenerationService

    return GenerationService(
        credit_service=get_credit_service(),
        pricing_repo=get_credit_repo(),
        task_repo=get_batch_repo(),
        llm_client=get_llm_client(),
        suno_client=get_suno_client(),
        fal_client=get_fal_client(),
        slai_client=get_slai_client(),
        key_pool_service=get_key_pool_service(),
    )


def get_batch_service():
    """Dependency that returns the BatchService instance."""
    from platform_api.services.batch_service import BatchService

    return BatchService(
        batch_repo=get_batch_repo(),
        credit_service=get_credit_service(),
        pricing_service=get_credit_pricing_service(),
        generation_service=get_generation_service(),
        profile_repo=get_profile_repo(),
    )


def get_settings_service():
    """Dependency that returns the SettingsService instance."""
    from platform_api.services.settings_service import SettingsService

    return SettingsService(settings_repo=get_settings_repo())


def get_audit_service():
    """Dependency that returns the AuditService instance."""
    from platform_api.services.audit_service import AuditService

    return AuditService(audit_repo=get_audit_repo())


def get_notification_service():
    """Dependency that returns the NotificationService instance."""
    from platform_api.services.notification_service import (
        ConnectionRegistry,
        NotificationService,
    )

    return NotificationService(registry=_connection_registry)


def get_suno_balance_service():
    """Dependency that returns the SunoBalanceService instance."""
    from platform_api.services.suno_balance_service import SunoBalanceService

    return SunoBalanceService(
        redis=get_redis(),
        suno_client=get_suno_client(),
        reserve_threshold=get_settings().suno_reserve_threshold,
        cache_ttl_seconds=get_settings().suno_balance_cache_ttl_seconds,
    )


def get_data_scope_service():
    """Dependency that returns the DataScopeService instance."""
    from platform_api.services.data_scope_service import DataScopeService

    return DataScopeService(
        batch_repo=get_batch_repo(),
        profile_repo=get_profile_repo(),
        settings_repo=get_settings_repo(),
    )


def get_key_pool_service():
    """Dependency that returns the KeyPoolService instance.

    Returns None if the encryption master key is not configured, since
    the key pool feature requires it to encrypt/decrypt API key values.
    """
    from platform_api.services.key_pool_service import KeyPoolService
    from platform_api.repositories.key_pool_repo import KeyPoolRepository
    from platform_api.services.key_encryption import KeyEncryption

    settings = get_settings()

    if not settings.encryption_master_key:
        logger.warning(
            "PLATFORM_ENCRYPTION_MASTER_KEY not set — KeyPoolService unavailable."
        )
        return None

    repository = KeyPoolRepository(pool=get_db_pool())
    encryption = KeyEncryption(master_key=settings.encryption_master_key)
    redis = get_redis()

    return KeyPoolService(
        repository=repository,
        encryption=encryption,
        redis=redis,
    )


# ---------------------------------------------------------------------------
# ConnectionRegistry singleton (lives for the lifetime of the process)
# ---------------------------------------------------------------------------

from platform_api.services.notification_service import ConnectionRegistry

_connection_registry = ConnectionRegistry()


def get_connection_registry() -> ConnectionRegistry:
    """Dependency that returns the WebSocket ConnectionRegistry singleton."""
    return _connection_registry


def get_credit_operation_service():
    """Dependency that returns the CreditService instance with pricing support.

    This is the central credit service for all credit operations:
    - execute_with_credits() for AI generation (deduct-execute-refund)
    - purchase_pack() for credit pack purchases
    - admin_adjust() for admin balance adjustments
    - get_balance(), deduct(), refund() for direct operations
    """
    from platform_api.services.credit_service import CreditService

    return CreditService(
        credit_repo=get_credit_repo(),
        license_repo=get_license_repo(),
        plan_repo=get_plan_repo(),
        pack_repo=get_credit_repo(),  # CreditRepo doubles as pack repo
        pricing_service=get_credit_pricing_service(),
    )


def get_channel_prompt_repo():
    """Dependency that returns the ChannelPromptRepository instance."""
    from platform_api.repositories.channel_prompt_repo import ChannelPromptRepository

    return ChannelPromptRepository(pool=get_db_pool())


def get_channel_prompt_service():
    """Dependency that returns the ChannelPromptService instance."""
    from platform_api.services.channel_prompt_service import ChannelPromptService

    return ChannelPromptService(repo=get_channel_prompt_repo())
