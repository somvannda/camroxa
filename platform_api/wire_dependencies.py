"""Wire all router placeholder dependencies to real implementations.

This module provides `wire_all_dependencies(app)` which overrides every
placeholder `_get_*` function in the router modules with real providers
from `dependencies.py`.
"""
from __future__ import annotations

from fastapi import FastAPI, Header, Request

from platform_api.dependencies import (
    get_auth_service,
    get_audit_service,
    get_batch_repo,
    get_batch_service,
    get_channel_prompt_service,
    get_credit_pricing_service,
    get_credit_repo,
    get_generation_service,
    get_image_job_service,
    get_job_queue_repo,
    get_key_pool_service,
    get_license_repo,
    get_invitation_code_service,
    get_lockout,
    get_model_cost_repo,
    get_notification_service,
    get_plan_repo,
    get_profile_service,
    get_prompt_service,
    get_rate_limit_config_repo,
    get_reset_service,
    get_settings_service,
    get_image_sample_pack_repo,
    get_suno_balance_service,
    get_provider_key_balance_service,
    get_turnstile_service,
    get_usage_enforcement_service,
    get_usage_tracking_repo,
    get_user_repo,
    get_user_service,
    get_v2_subscription_service,
    get_v2_credit_service,
    get_v2_topup_service,
)


def wire_all_dependencies(app: FastAPI) -> None:
    """Override all router placeholder dependencies with real providers."""

    # --- auth.py ---
    from platform_api.routers.auth import (
        _get_auth_service as auth_get_auth,
        _get_invitation_code_service as auth_get_invitation_code_service,
        _get_lockout as auth_get_lockout,
        _get_turnstile_service as auth_get_turnstile,
        _get_current_user_id as auth_get_current_user_id,
    )

    async def real_auth_service():
        return get_auth_service()

    async def real_lockout():
        return get_lockout()

    async def real_invitation_code_service():
        return get_invitation_code_service()

    async def real_turnstile_service():
        return get_turnstile_service()

    async def real_current_user_id(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> str:
        from platform_api.exceptions import AuthenticationError
        from platform_api.middleware.auth import _resolve_access_cookie_name
        token: str | None = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer "):]
        else:
            token = request.cookies.get(_resolve_access_cookie_name(request))
        if not token:
            raise AuthenticationError("Missing or invalid Authorization header.")
        auth_svc = get_auth_service()
        payload = await auth_svc.validate_token(token)
        return payload.user_id

    app.dependency_overrides[auth_get_auth] = real_auth_service
    app.dependency_overrides[auth_get_invitation_code_service] = real_invitation_code_service
    app.dependency_overrides[auth_get_lockout] = real_lockout
    app.dependency_overrides[auth_get_turnstile] = real_turnstile_service
    app.dependency_overrides[auth_get_current_user_id] = real_current_user_id

    # --- users.py ---
    from platform_api.routers.users import (
        _get_user_service as users_get_user_service,
        _get_usage_enforcement_service as users_get_enforcement,
    )

    async def real_user_service():
        return get_user_service()

    async def real_users_enforcement():
        return get_usage_enforcement_service()

    app.dependency_overrides[users_get_user_service] = real_user_service
    app.dependency_overrides[users_get_enforcement] = real_users_enforcement

    # --- admin.py ---
    from platform_api.routers.admin import (
        _get_audit_service as admin_get_audit,
        _get_suno_balance_service as admin_get_suno,
        _get_provider_key_balance_service as admin_get_provider_balances,
        _get_rate_limit_repo as admin_get_rate_limit,
        _get_settings_repo as admin_get_settings_repo,
        _get_credit_repo as admin_get_credit_repo,
        _get_user_spend_service as admin_get_user_spend_service,
        _get_user_repo as admin_get_user_repo,
        _get_batch_repo as admin_get_batch_repo,
        _get_youtube_oauth_app_repo as admin_get_youtube_oauth_repo,
        _get_youtube_oauth_encryption as admin_get_youtube_oauth_encryption,
        _get_reset_service as admin_get_reset_service,
    )

    async def real_admin_audit():
        return get_audit_service()

    async def real_admin_suno():
        return get_suno_balance_service()

    async def real_admin_provider_balances():
        return get_provider_key_balance_service()

    async def real_admin_rate_limit():
        return get_rate_limit_config_repo()

    async def real_admin_settings_repo():
        from platform_api.dependencies import get_settings_repo

        return get_settings_repo()

    async def real_admin_credit_repo():
        return get_credit_repo()

    async def real_admin_user_spend_service():
        from platform_api.services.user_spend_service import UserSpendService

        return UserSpendService(
            credit_repo=get_credit_repo(),
            model_cost_repo=get_model_cost_repo(),
            settings_service=get_settings_service(),
        )

    async def real_admin_user_repo():
        return get_user_repo()

    async def real_admin_batch_repo():
        return get_batch_repo()

    async def real_admin_youtube_oauth_repo():
        from platform_api.dependencies import get_youtube_oauth_app_repo

        return get_youtube_oauth_app_repo()

    async def real_admin_youtube_oauth_encryption():
        from platform_api.dependencies import get_youtube_oauth_encryption

        return get_youtube_oauth_encryption()

    app.dependency_overrides[admin_get_audit] = real_admin_audit
    app.dependency_overrides[admin_get_suno] = real_admin_suno
    app.dependency_overrides[admin_get_provider_balances] = real_admin_provider_balances
    app.dependency_overrides[admin_get_rate_limit] = real_admin_rate_limit
    app.dependency_overrides[admin_get_settings_repo] = real_admin_settings_repo
    app.dependency_overrides[admin_get_credit_repo] = real_admin_credit_repo
    app.dependency_overrides[admin_get_user_spend_service] = real_admin_user_spend_service
    app.dependency_overrides[admin_get_user_repo] = real_admin_user_repo
    app.dependency_overrides[admin_get_batch_repo] = real_admin_batch_repo
    app.dependency_overrides[admin_get_youtube_oauth_repo] = real_admin_youtube_oauth_repo
    app.dependency_overrides[
        admin_get_youtube_oauth_encryption
    ] = real_admin_youtube_oauth_encryption

    async def real_admin_reset_service():
        return get_reset_service()

    app.dependency_overrides[admin_get_reset_service] = real_admin_reset_service

    # --- admin_pipeline.py ---
    from platform_api.routers.admin_pipeline import (
        _get_audit_service as admin_pipeline_get_audit,
        _get_batch_service as admin_pipeline_get_batch,
        _get_image_job_service as admin_pipeline_get_image,
        _get_job_queue_repo as admin_pipeline_get_job_queue,
    )

    async def real_admin_pipeline_batch():
        return get_batch_service()

    async def real_admin_pipeline_image():
        return get_image_job_service()

    async def real_admin_pipeline_audit():
        return get_audit_service()

    async def real_admin_pipeline_job_queue():
        return get_job_queue_repo()

    app.dependency_overrides[admin_pipeline_get_batch] = real_admin_pipeline_batch
    app.dependency_overrides[admin_pipeline_get_image] = real_admin_pipeline_image
    app.dependency_overrides[admin_pipeline_get_audit] = real_admin_pipeline_audit
    app.dependency_overrides[admin_pipeline_get_job_queue] = real_admin_pipeline_job_queue

    # --- admin_invitations.py ---
    from platform_api.routers.admin_invitations import (
        _get_invitation_code_service as admin_invitations_get_service,
    )

    async def real_admin_invitation_code_service():
        return get_invitation_code_service()

    app.dependency_overrides[
        admin_invitations_get_service
    ] = real_admin_invitation_code_service

    # --- client_logs.py ---
    from platform_api.routers.client_logs import (
        _get_client_log_service as client_logs_get_svc,
    )
    from platform_api.dependencies import get_client_log_service

    async def real_client_log_service():
        return get_client_log_service()

    app.dependency_overrides[client_logs_get_svc] = real_client_log_service

    # --- youtube.py ---
    from platform_api.routers.youtube import (
        _get_youtube_connection_service as youtube_get_service,
        _get_job_queue_repo as youtube_get_job_queue,
    )

    async def real_youtube_connection_service():
        from platform_api.dependencies import get_youtube_connection_service

        return get_youtube_connection_service()

    app.dependency_overrides[youtube_get_service] = real_youtube_connection_service

    # --- batch.py ---
    from platform_api.routers.batch import (
        _get_batch_service as batch_get_svc,
        _get_job_queue_repo as batch_get_job_queue,
    )

    async def real_batch_service():
        return get_batch_service()

    async def real_job_queue_repo():
        return get_job_queue_repo()

    app.dependency_overrides[batch_get_svc] = real_batch_service
    app.dependency_overrides[batch_get_job_queue] = real_job_queue_repo
    app.dependency_overrides[youtube_get_job_queue] = real_job_queue_repo

    # --- image_jobs.py ---
    from platform_api.routers.image_jobs import (
        _get_batch_service as image_jobs_get_batch_svc,
        _get_image_job_service as image_jobs_get_svc,
        _get_job_queue_repo as image_jobs_get_job_queue,
    )
    from platform_api.routers.music_downloads import (
        _get_batch_service as music_downloads_get_batch_svc,
    )

    async def real_image_job_service():
        return get_image_job_service()

    app.dependency_overrides[image_jobs_get_svc] = real_image_job_service
    app.dependency_overrides[image_jobs_get_batch_svc] = real_batch_service
    app.dependency_overrides[image_jobs_get_job_queue] = real_job_queue_repo
    app.dependency_overrides[music_downloads_get_batch_svc] = real_batch_service

    from platform_api.routers.progress import _get_batch_service as progress_get_batch_svc

    app.dependency_overrides[progress_get_batch_svc] = real_batch_service

    # --- music_history.py ---
    from platform_api.routers.music_history import (
        _get_batch_service as music_history_get_batch_svc,
    )

    app.dependency_overrides[music_history_get_batch_svc] = real_batch_service

    # --- callbacks.py ---
    from platform_api.routers.callbacks import (
        _get_suno_task_repo as cb_get_task_repo,
        _get_notification_port as cb_get_notif,
        _get_batch_service as cb_get_batch_service,
        _get_image_job_service as cb_get_image_jobs,
    )

    async def real_suno_task_repo():
        return get_batch_repo()

    async def real_notification_port():
        return get_notification_service()

    async def real_callback_batch_service():
        return get_batch_service()

    app.dependency_overrides[cb_get_task_repo] = real_suno_task_repo
    app.dependency_overrides[cb_get_notif] = real_notification_port
    app.dependency_overrides[cb_get_batch_service] = real_callback_batch_service
    app.dependency_overrides[cb_get_image_jobs] = real_image_job_service

    # --- image_sample_packs.py ---
    from platform_api.routers.image_sample_packs import (
        _get_image_sample_pack_repo as image_packs_get_repo,
    )

    async def real_image_packs_repo():
        return get_image_sample_pack_repo()

    app.dependency_overrides[image_packs_get_repo] = real_image_packs_repo

    # --- admin_image_sample_packs.py ---
    from platform_api.routers.admin_image_sample_packs import (
        _get_image_sample_pack_repo as admin_image_packs_get_repo,
    )

    app.dependency_overrides[admin_image_packs_get_repo] = real_image_packs_repo

    from platform_api.routers.admin_image_sample_packs import (
        _get_image_sample_pack_service as admin_image_packs_get_service,
    )
    from platform_api.dependencies import get_image_sample_pack_service

    async def real_image_sample_pack_service():
        return get_image_sample_pack_service()

    app.dependency_overrides[admin_image_packs_get_service] = real_image_sample_pack_service

    # --- credits.py ---
    from platform_api.routers.credits import (
        _get_credit_repo as credits_get_repo,
        _get_pricing_service as credits_get_pricing,
        _get_credit_pack_service as credits_get_pack_service,
        _get_pack_repo as credits_get_pack,
        _get_settings_service as credits_get_settings,
        _get_credit_service as credits_get_credit_svc,
        _get_ai_routing_service as credits_get_ai_routing,
        _get_model_cost_service as credits_get_model_cost,
        _get_pricing_generator_service as credits_get_pricing_generator,
    )

    async def real_credit_repo():
        return get_credit_repo()

    async def real_pricing_service():
        return get_credit_pricing_service()

    async def real_credit_pack_service():
        from platform_api.dependencies import get_credit_pack_service
        return get_credit_pack_service()

    async def real_pack_repo():
        return get_credit_repo()

    async def real_credits_settings_service():
        return get_settings_service()

    async def real_credits_credit_service():
        from platform_api.dependencies import get_credit_operation_service
        return get_credit_operation_service()

    async def real_credits_ai_routing_service():
        from platform_api.dependencies import get_ai_routing_service
        return get_ai_routing_service()

    async def real_model_cost_service():
        from platform_api.dependencies import get_model_cost_service
        return get_model_cost_service()

    async def real_pricing_generator_service():
        from platform_api.dependencies import get_pricing_generator_service
        return get_pricing_generator_service()

    app.dependency_overrides[credits_get_repo] = real_credit_repo
    app.dependency_overrides[credits_get_pricing] = real_pricing_service
    app.dependency_overrides[credits_get_pack_service] = real_credit_pack_service
    app.dependency_overrides[credits_get_pack] = real_pack_repo
    app.dependency_overrides[credits_get_settings] = real_credits_settings_service
    app.dependency_overrides[credits_get_credit_svc] = real_credits_credit_service
    app.dependency_overrides[credits_get_ai_routing] = real_credits_ai_routing_service
    app.dependency_overrides[credits_get_model_cost] = real_model_cost_service
    app.dependency_overrides[credits_get_pricing_generator] = real_pricing_generator_service

    # --- generation.py ---
    from platform_api.routers.generation import (
        _get_generation_service as gen_get_svc,
        _get_enforcement_service as gen_get_enforcement,
        _get_batch_service as gen_get_batch_svc,
        _get_job_queue_repo as gen_get_job_queue,
        _get_task_lookup as gen_get_task,
        _get_ai_routing_service as gen_get_ai_routing,
        _get_prompt_service as gen_get_prompt_svc,
        _get_profile_service as gen_get_profile_svc,
    )

    async def real_generation_service():
        return get_generation_service()

    async def real_enforcement_service():
        return get_usage_enforcement_service()

    async def real_task_lookup():
        return get_batch_repo()

    async def real_gen_ai_routing_service():
        from platform_api.dependencies import get_ai_routing_service
        svc = get_ai_routing_service()
        if svc is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="AI routing service unavailable. Key pool is not configured.",
            )
        return svc

    async def real_gen_prompt_service():
        return get_prompt_service()

    async def real_gen_profile_service():
        return get_profile_service()

    async def real_gen_batch_service():
        return get_batch_service()

    app.dependency_overrides[gen_get_svc] = real_generation_service
    app.dependency_overrides[gen_get_enforcement] = real_enforcement_service
    app.dependency_overrides[gen_get_batch_svc] = real_gen_batch_service
    app.dependency_overrides[gen_get_job_queue] = real_job_queue_repo
    app.dependency_overrides[gen_get_task] = real_task_lookup
    app.dependency_overrides[gen_get_ai_routing] = real_gen_ai_routing_service
    app.dependency_overrides[gen_get_prompt_svc] = real_gen_prompt_service
    app.dependency_overrides[gen_get_profile_svc] = real_gen_profile_service

    # --- licenses.py ---
    from platform_api.routers.licenses import (
        _get_license_repo as lic_get_repo,
        _get_plan_repo as lic_get_plan,
        _get_credit_repo as lic_get_credit,
    )

    async def real_license_repo():
        return get_license_repo()

    async def real_lic_plan_repo():
        return get_plan_repo()

    app.dependency_overrides[lic_get_repo] = real_license_repo
    app.dependency_overrides[lic_get_plan] = real_lic_plan_repo

    async def real_lic_credit_repo():
        return get_credit_repo()

    app.dependency_overrides[lic_get_credit] = real_lic_credit_repo

    # --- plans.py ---
    from platform_api.routers.plans import _get_plan_repo as plans_get_repo

    async def real_plans_repo():
        return get_plan_repo()

    app.dependency_overrides[plans_get_repo] = real_plans_repo

    from platform_api.routers.web_music_plans_admin import (
        _get_credit_repo as wm_plans_get_credit_repo,
        _get_plan_repo as wm_plans_get_plan_repo,
    )

    async def real_wm_plans_repo():
        return get_plan_repo()

    async def real_wm_credit_repo():
        return get_credit_repo()

    app.dependency_overrides[wm_plans_get_plan_repo] = real_wm_plans_repo
    app.dependency_overrides[wm_plans_get_credit_repo] = real_wm_credit_repo

    # --- profiles.py ---
    from platform_api.routers.profiles import (
        _get_profile_service as prof_get_svc,
        _get_profile_stats_port as prof_get_stats,
    )

    async def real_profile_service():
        return get_profile_service()

    async def real_profile_stats():
        # The stats port may be the batch repo or a dedicated service
        return get_batch_repo()

    app.dependency_overrides[prof_get_svc] = real_profile_service
    app.dependency_overrides[prof_get_stats] = real_profile_stats

    # --- prompts.py ---
    from platform_api.routers.prompts import _get_prompt_service as prompts_get_svc

    async def real_prompt_service():
        return get_prompt_service()

    app.dependency_overrides[prompts_get_svc] = real_prompt_service

    # --- settings_router.py ---
    from platform_api.routers.settings_router import _get_settings_service as settings_get_svc

    async def real_settings_service():
        return get_settings_service()

    app.dependency_overrides[settings_get_svc] = real_settings_service

    # --- key_pool.py ---
    from platform_api.routers.key_pool import _get_key_pool_service as kp_get_svc

    async def real_key_pool_service():
        svc = get_key_pool_service()
        if svc is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="Key pool service unavailable. Set PLATFORM_ENCRYPTION_MASTER_KEY to enable.",
            )
        return svc

    app.dependency_overrides[kp_get_svc] = real_key_pool_service

    # --- channel_prompts.py ---
    from platform_api.routers.channel_prompts import _get_channel_prompt_service as cp_get_svc

    async def real_channel_prompt_service():
        return get_channel_prompt_service()

    app.dependency_overrides[cp_get_svc] = real_channel_prompt_service

    # --- ai_routing.py ---
    from platform_api.routers.ai_routing import _get_ai_routing_service as ai_routing_get_svc

    async def real_ai_routing_service():
        from platform_api.dependencies import get_ai_routing_service
        svc = get_ai_routing_service()
        if svc is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="AI routing service unavailable. Key pool is not configured.",
            )
        return svc

    app.dependency_overrides[ai_routing_get_svc] = real_ai_routing_service

    # --- marketplace.py ---
    from platform_api.routers.marketplace import (
        _get_marketplace_service as marketplace_get_svc,
    )

    async def real_marketplace_service():
        from platform_api.dependencies import get_db_pool
        from platform_api.repositories.marketplace_repo import MarketplaceRepository
        from platform_api.services.marketplace_service import MarketplaceService
        from platform_api.config import get_settings as _get_settings

        settings = _get_settings()
        pool = get_db_pool()
        repo = MarketplaceRepository(pool=pool)
        return MarketplaceService(repo=repo, storage_path=settings.marketplace_storage_path)

    app.dependency_overrides[marketplace_get_svc] = real_marketplace_service

    # --- channel_setup.py (ai routing) ---
    from platform_api.routers.channel_setup import _get_ai_routing_service as cs_get_ai_routing

    async def real_cs_ai_routing_service():
        from platform_api.dependencies import get_ai_routing_service
        svc = get_ai_routing_service()
        if svc is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="AI routing service unavailable. Key pool is not configured.",
            )
        return svc

    app.dependency_overrides[cs_get_ai_routing] = real_cs_ai_routing_service

    # --- streaming_public.py / streaming_admin.py / streaming_library.py ---
    from platform_api.routers.streaming_public import _get_catalog_service as streaming_public_catalog
    from platform_api.routers.streaming_admin import _get_catalog_service as streaming_admin_catalog
    from platform_api.routers.streaming_library import _get_catalog_service as streaming_library_catalog
    from platform_api.services.streaming_catalog_service import StreamingCatalogService

    async def real_streaming_catalog_service() -> StreamingCatalogService:
        from platform_api.dependencies import get_db_pool

        return StreamingCatalogService(get_db_pool())

    app.dependency_overrides[streaming_public_catalog] = real_streaming_catalog_service
    app.dependency_overrides[streaming_admin_catalog] = real_streaming_catalog_service
    app.dependency_overrides[streaming_library_catalog] = real_streaming_catalog_service

    from platform_api.routers.web_music import _get_web_music_service as web_music_get_svc
    from platform_api.services.web_music_service import WebMusicService

    async def real_web_music_service() -> WebMusicService:
        from platform_api.dependencies import (
            get_ai_routing_service,
            get_credit_pricing_service,
            get_db_pool,
            get_redis,
        )

        return WebMusicService(
            get_db_pool(), 
            get_generation_service(),
            credit_service=get_v2_credit_service(),
            ai_routing_service=get_ai_routing_service(),
            pricing_service=get_credit_pricing_service(),
            redis=get_redis(),
        )

    app.dependency_overrides[web_music_get_svc] = real_web_music_service

    # --- v2_subscriptions.py ---
    from platform_api.routers.v2_subscriptions import _get_subscription_service as v2_sub_get_svc
    from platform_api.dependencies import get_v2_subscription_service

    async def real_v2_subscription_service():
        return get_v2_subscription_service()

    app.dependency_overrides[v2_sub_get_svc] = real_v2_subscription_service

    # --- v2_credits.py ---
    from platform_api.routers.v2_credits import _get_credit_service as v2_credit_get_svc
    from platform_api.dependencies import get_v2_credit_service

    async def real_v2_credit_service():
        return get_v2_credit_service()

    app.dependency_overrides[v2_credit_get_svc] = real_v2_credit_service

    # --- v2_topups.py ---
    from platform_api.routers.v2_topups import _get_topup_service as v2_topup_get_svc
    from platform_api.dependencies import get_v2_topup_service

    async def real_v2_topup_service():
        return get_v2_topup_service()

    app.dependency_overrides[v2_topup_get_svc] = real_v2_topup_service

    # --- webhooks_cutluy.py ---
    from platform_api.routers.webhooks_cutluy import (
        _get_subscription_service as webhook_sub_get_svc,
        _get_topup_service as webhook_topup_get_svc
    )

    app.dependency_overrides[webhook_sub_get_svc] = real_v2_subscription_service
    app.dependency_overrides[webhook_topup_get_svc] = real_v2_topup_service
