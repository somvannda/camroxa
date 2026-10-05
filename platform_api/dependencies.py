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


def get_client_log_repo():
    """Dependency that returns the ClientLogRepository instance."""
    from platform_api.repositories.client_log_repo import ClientLogRepository

    return ClientLogRepository(db=get_db_pool())


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


def get_kie_client():
    """Dependency that returns the KieClient instance (kie.ai Market API)."""
    from platform_api.clients.kie_client import KieClient

    return KieClient(settings=get_settings())


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


def get_credit_pack_service():
    """Dependency that returns the CreditPackService instance."""
    from platform_api.services.credit_pack_service import CreditPackService

    return CreditPackService(pack_repo=get_credit_repo())


def get_model_cost_repo():
    from platform_api.repositories.model_cost_repo import ModelCostRepository

    return ModelCostRepository(pool=get_db_pool())


def get_model_cost_service():
    from platform_api.services.model_cost_service import ModelCostService

    return ModelCostService(repo=get_model_cost_repo())


def get_suno_blocklist_repo():
    from platform_api.repositories.suno_blocklist_repo import SunoBlocklistRepository

    return SunoBlocklistRepository(pool=get_db_pool())


def get_suno_blocklist_service():
    from platform_api.services.suno_blocklist_service import SunoBlocklistService

    return SunoBlocklistService(repo=get_suno_blocklist_repo())


def get_pricing_generator_service():
    from platform_api.services.pricing_generator_service import PricingGeneratorService

    return PricingGeneratorService(
        model_cost_repo=get_model_cost_repo(),
        pricing_repo=get_credit_repo(),
    )


def get_usage_tracking_repo():
    """Dependency that returns the UsageTrackingRepository instance."""
    from platform_api.repositories.usage_tracking_repo import UsageTrackingRepository

    return UsageTrackingRepository(pool=get_db_pool())


def get_daily_quota_bank_repo():
    """Dependency that returns the DailyQuotaBankRepository instance."""
    from platform_api.repositories.daily_quota_bank_repo import DailyQuotaBankRepository

    return DailyQuotaBankRepository(pool=get_db_pool())


def get_daily_quota_bank_service():
    """Dependency that returns the DailyQuotaBankService instance."""
    from platform_api.services.daily_quota_bank_service import DailyQuotaBankService

    return DailyQuotaBankService(
        bank_repo=get_daily_quota_bank_repo(),
        usage_repo=get_usage_tracking_repo(),
    )


def get_quota_topup_repo():
    """Dependency that returns the QuotaTopupRepository instance."""
    from platform_api.repositories.quota_topup_repo import QuotaTopupRepository

    return QuotaTopupRepository(pool=get_db_pool())


def get_quota_topup_service():
    """Dependency that returns the QuotaTopupService instance."""
    from platform_api.services.quota_topup_service import QuotaTopupService

    return QuotaTopupService(
        topup_repo=get_quota_topup_repo(),
        plan_repo=get_plan_repo(),
        usage_repo=get_usage_tracking_repo(),
    )


def get_usage_enforcement_service():
    """Dependency that returns the UsageEnforcementService instance."""
    from platform_api.services.usage_enforcement_service import UsageEnforcementService

    return UsageEnforcementService(
        credit_repo=get_credit_repo(),
        usage_repo=get_usage_tracking_repo(),
        plan_repo=get_plan_repo(),
        pricing_repo=get_credit_repo(),
        redis=get_redis(),
        license_repo=get_license_repo(),
        daily_quota_bank_service=get_daily_quota_bank_service(),
        quota_topup_service=get_quota_topup_service(),
        settings_repo=get_settings_repo(),
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

    return PromptService(prompt_repo=get_prompt_repo(), pool=get_db_pool())


def get_generation_service():
    """Dependency that returns the GenerationService instance."""
    from platform_api.services.generation_service import GenerationService

    return GenerationService(
        credit_service=get_credit_service(),
        pricing_repo=get_credit_pricing_service(),
        task_repo=get_batch_repo(),
        llm_client=get_llm_client(),
        suno_client=get_suno_client(),
        fal_client=get_fal_client(),
        slai_client=get_slai_client(),
        kie_client=get_kie_client(),
        key_pool_service=get_key_pool_service(),
        ai_routing_service=get_ai_routing_service(),
    )


def get_job_queue_repo():
    """Dependency that returns the JobQueueRepository instance."""
    from platform_api.repositories.job_queue_repo import JobQueueRepository

    return JobQueueRepository(pool=get_db_pool())


def get_batch_service():
    """Dependency that returns the BatchService instance."""
    from platform_api.services.batch_service import BatchService

    return BatchService(
        batch_repo=get_batch_repo(),
        credit_service=get_credit_service(),
        pricing_service=get_credit_pricing_service(),
        generation_service=get_generation_service(),
        profile_repo=get_profile_repo(),
        ai_routing_service=get_ai_routing_service(),
        prompt_service=get_prompt_service(),
        settings_service=get_settings_service(),
        enforcement_service=get_usage_enforcement_service(),
        image_job_service=get_image_job_service(),
        image_sample_rotation=get_image_sample_rotation_service(),
    )


def get_image_sample_repo():
    from platform_api.repositories.image_sample_repo import ImageSampleRepository

    return ImageSampleRepository(pool=get_db_pool())


def get_image_sample_rotation_service():
    from platform_api.services.image_sample_rotation import ImageSampleRotationService

    return ImageSampleRotationService(
        repo=get_image_sample_repo(),
        pack_repo=get_image_sample_pack_repo(),
    )


def get_image_job_service():
    from platform_api.services.image_job_service import ImageJobService

    return ImageJobService(
        repo=get_batch_repo(),
        settings_service=get_settings_service(),
        settings_repo=get_settings_repo(),
        routing_service=get_ai_routing_service(),
        enforcement_service=get_usage_enforcement_service(),
        generation_service=get_generation_service(),
        image_sample_rotation=get_image_sample_rotation_service(),
    )


def get_settings_service():
    """Dependency that returns the SettingsService instance."""
    from platform_api.services.settings_service import SettingsService

    return SettingsService(settings_repo=get_settings_repo())


def get_invitation_code_encryption():
    """Dependency that returns the encryption helper for invitation codes."""
    from platform_api.services.key_encryption import KeyEncryption

    settings = get_settings()
    if not settings.encryption_master_key:
        logger.warning(
            "PLATFORM_ENCRYPTION_MASTER_KEY not set — invitation code display will be limited to hints."
        )
        return None

    return KeyEncryption(master_key=settings.encryption_master_key)


def get_invitation_code_service():
    """Dependency that returns the InvitationCodeService instance."""
    from platform_api.services.invitation_code_service import InvitationCodeService

    return InvitationCodeService(
        pool=get_db_pool(),
        encryption=get_invitation_code_encryption(),
    )


def get_audit_service():
    """Dependency that returns the AuditService instance."""
    from platform_api.services.audit_service import AuditService

    return AuditService(audit_repo=get_audit_repo())


def get_client_log_service():
    """Dependency that returns the ClientLogService instance."""
    from platform_api.services.client_log_service import ClientLogService

    return ClientLogService(repo=get_client_log_repo())


def get_desktop_release_upload_service(request: Any | None = None):
    """Return the desktop installer upload service."""
    from platform_api.services.desktop_release_upload_service import DesktopReleaseUploadService

    settings = get_settings()
    api_download_base_url = ""
    if request is not None:
        api_download_base_url = (
            f"{str(request.base_url).rstrip('/')}/api/v3/public/desktop-release/files"
        )
    return DesktopReleaseUploadService(
        storage_root=settings.desktop_release_storage_path,
        public_base_url=settings.desktop_release_public_base_url,
        api_download_base_url=api_download_base_url,
        max_bytes=settings.desktop_release_max_upload_mb * 1024 * 1024,
    )


async def get_desktop_release_upload_service_resolved(
    pool: Any,
    request: Any | None = None,
) -> Any:
    """Installer service with absolute public download URLs when possible."""
    from platform_api.services.desktop_release_upload_service import DesktopReleaseUploadService
    from platform_api.services.public_url_service import resolve_public_api_base_url

    settings = get_settings()
    service = get_desktop_release_upload_service(request)
    if settings.desktop_release_public_base_url.strip():
        return service

    api_base = await resolve_public_api_base_url(pool, settings=settings)
    files_base = f"{api_base.rstrip('/')}/api/v3/public/desktop-release/files"
    return service.with_download_bases(api_download_base_url=files_base)


def get_notification_service():
    """Dependency that returns the NotificationService instance."""
    from platform_api.services.notification_service import (
        PGNotificationQueueRepository,
        NotificationService,
    )

    return NotificationService(
        registry=_connection_registry,
        queue_repo=PGNotificationQueueRepository(pool=get_db_pool()),
    )


def get_suno_balance_service():
    """Dependency that returns the SunoBalanceService instance."""
    from platform_api.services.suno_balance_service import SunoBalanceService

    return SunoBalanceService(
        redis=get_redis(),
        suno_client=get_suno_client(),
        reserve_threshold=get_settings().suno_reserve_threshold,
        cache_ttl_seconds=get_settings().suno_balance_cache_ttl_seconds,
    )


def get_provider_key_balance_service():
    """Dependency that returns the ProviderKeyBalanceService instance."""
    from platform_api.services.provider_key_balance_service import ProviderKeyBalanceService

    redis = None
    try:
        redis = get_redis()
    except Exception:
        redis = None
    return ProviderKeyBalanceService(
        redis=redis,
        key_pool=get_key_pool_service(),
        settings=get_settings(),
        cache_ttl_seconds=max(15, int(get_settings().suno_balance_cache_ttl_seconds or 30)),
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


def get_youtube_oauth_app_repo():
    """Dependency that returns the YouTube OAuth app repository instance."""
    from platform_api.repositories.youtube_oauth_app_repo import YouTubeOAuthAppRepository

    return YouTubeOAuthAppRepository(db=get_db_pool())


def get_youtube_oauth_encryption():
    """Dependency that returns the encryption helper for YouTube OAuth secrets."""
    from platform_api.services.key_encryption import KeyEncryption

    settings = get_settings()
    if not settings.encryption_master_key:
        logger.warning(
            "PLATFORM_ENCRYPTION_MASTER_KEY not set — YouTube OAuth app secret storage unavailable."
        )
        return None

    return KeyEncryption(master_key=settings.encryption_master_key)


def get_youtube_connection_repo():
    """Dependency that returns the YouTube connection repository instance."""
    from platform_api.repositories.youtube_connection_repo import YouTubeConnectionRepository

    return YouTubeConnectionRepository(db=get_db_pool())


def get_image_sample_pack_repo():
    from platform_api.repositories.image_sample_pack_repo import ImageSamplePackRepository

    return ImageSamplePackRepository(db=get_db_pool())


def get_image_sample_pack_service():
    from platform_api.config import get_settings
    from platform_api.services.image_sample_pack_service import ImageSamplePackService

    return ImageSamplePackService(
        storage_root=get_settings().sample_pack_storage_path,
        repo=get_image_sample_pack_repo(),
    )


def get_youtube_connection_service():
    """Dependency that returns the backend-mediated YouTube connection service."""
    from platform_api.services.youtube_connection_service import YouTubeConnectionService

    return YouTubeConnectionService(
        db=get_db_pool(),
        oauth_app_repo=get_youtube_oauth_app_repo(),
        connection_repo=get_youtube_connection_repo(),
        encryption=get_youtube_oauth_encryption(),
        settings_service=get_settings_service(),
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


def get_reset_service():
    """Dependency that returns the ResetService instance.

    Wires together pool, redis, audit_service, and backup_dir from settings
    for the admin user-data reset/backup/restore functionality.
    """
    from platform_api.services.reset_service import ResetService

    settings = get_settings()
    return ResetService(
        pool=get_db_pool(),
        redis=get_redis(),
        audit_service=get_audit_service(),
        backup_dir=settings.backup_dir,
    )


def get_ai_routing_service():
    """Dependency that returns the AIRoutingService instance."""
    from platform_api.services.ai_routing_service import AIRoutingService

    key_pool_svc = get_key_pool_service()
    if key_pool_svc is None:
        return None

    return AIRoutingService(
        settings_repo=get_settings_repo(),
        key_pool_service=key_pool_svc,
        model_cost_repo=get_model_cost_repo(),
    )


# ---------------------------------------------------------------------------
# Shared Services (Turnstile, CutLuy, etc.)
# ---------------------------------------------------------------------------


def get_turnstile_service():
    """Dependency that returns the TurnstileService instance."""
    from platform_api.services.shared.turnstile_service import TurnstileService
    
    return TurnstileService(get_settings())


# ---------------------------------------------------------------------------
# V2 Services (web music subscriptions and credits)
# ---------------------------------------------------------------------------


def get_v2_subscription_service():
    """Dependency that returns the v2 SubscriptionService instance."""
    from platform_api.db.asyncpg_adapter import wrap_pool
    from platform_api.services.v2.subscription_service import SubscriptionService
    from platform_api.services.shared.cutluy_service import get_cutluy_service

    return SubscriptionService(
        db=wrap_pool(get_db_pool()),
        cutluy=get_cutluy_service()
    )


def get_v2_credit_service():
    """Dependency that returns the v2 CreditService instance."""
    from platform_api.db.asyncpg_adapter import wrap_pool
    from platform_api.services.v2.credit_service import CreditService

    return CreditService(db=wrap_pool(get_db_pool()))


def get_v2_topup_service():
    """Dependency that returns the v2 TopupService instance."""
    from platform_api.db.asyncpg_adapter import wrap_pool
    from platform_api.services.v2.topup_service import TopupService
    from platform_api.services.shared.cutluy_service import get_cutluy_service
    from platform_api.services.v2.credit_service import CreditService

    db = wrap_pool(get_db_pool())
    return TopupService(
        db=db,
        cutluy=get_cutluy_service(),
        credit_service=CreditService(db=db),
    )


def get_v3_store():
    """Shared-DB store for credits-only v3 columns/tables."""
    from platform_api.services.v3.store import V3BillingStore

    return V3BillingStore(pool=get_db_pool())


def get_v3_billing_service():
    """Credits-only quote/charge/refund on the v1 wallet and Credits page."""
    from platform_api.services.v3.credits_only_billing_service import CreditsOnlyBillingService

    return CreditsOnlyBillingService(
        store=get_v3_store(),
        credit_repo=get_credit_repo(),
        pricing_service=get_credit_pricing_service(),
        enforcement=get_usage_enforcement_service(),
        ai_routing_service=get_ai_routing_service(),
    )


def get_v3_grant_service():
    from platform_api.services.v3.period_grant_service import PeriodGrantService

    return PeriodGrantService(
        store=get_v3_store(),
        credit_repo=get_credit_repo(),
        plan_repo=get_plan_repo(),
    )


def get_v3_conversion_service():
    from platform_api.services.v3.quota_conversion_service import QuotaConversionService

    return QuotaConversionService(
        store=get_v3_store(),
        credit_repo=get_credit_repo(),
        plan_repo=get_plan_repo(),
        usage_repo=get_usage_tracking_repo(),
        topup_repo=get_quota_topup_repo(),
    )


def get_v3_web_ledger_service():
    from platform_api.services.v3.web_ledger_conversion import WebLedgerConversionService

    return WebLedgerConversionService(
        store=get_v3_store(),
        credit_repo=get_credit_repo(),
    )
