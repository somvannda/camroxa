"""Wire all router placeholder dependencies to real implementations.

This module provides `wire_all_dependencies(app)` which overrides every
placeholder `_get_*` function in the router modules with real providers
from `dependencies.py`.
"""
from __future__ import annotations

from fastapi import FastAPI, Header

from platform_api.dependencies import (
    get_auth_service,
    get_audit_service,
    get_batch_repo,
    get_batch_service,
    get_channel_prompt_service,
    get_credit_pricing_service,
    get_credit_repo,
    get_generation_service,
    get_key_pool_service,
    get_license_repo,
    get_lockout,
    get_notification_service,
    get_plan_repo,
    get_profile_service,
    get_prompt_service,
    get_rate_limit_config_repo,
    get_settings_service,
    get_suno_balance_service,
    get_usage_enforcement_service,
    get_usage_tracking_repo,
    get_user_service,
)


def wire_all_dependencies(app: FastAPI) -> None:
    """Override all router placeholder dependencies with real providers."""

    # --- auth.py ---
    from platform_api.routers.auth import (
        _get_auth_service as auth_get_auth,
        _get_lockout as auth_get_lockout,
        _get_current_user_id as auth_get_current_user_id,
    )

    async def real_auth_service():
        return get_auth_service()

    async def real_lockout():
        return get_lockout()

    async def real_current_user_id(authorization: str = Header(...)) -> str:
        from platform_api.exceptions import AuthenticationError
        if not authorization.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid Authorization header.")
        token = authorization[len("Bearer "):]
        auth_svc = get_auth_service()
        payload = await auth_svc.validate_token(token)
        return payload.user_id

    app.dependency_overrides[auth_get_auth] = real_auth_service
    app.dependency_overrides[auth_get_lockout] = real_lockout
    app.dependency_overrides[auth_get_current_user_id] = real_current_user_id

    # --- users.py ---
    from platform_api.routers.users import _get_user_service as users_get_user_service

    async def real_user_service():
        return get_user_service()

    app.dependency_overrides[users_get_user_service] = real_user_service

    # --- admin.py ---
    from platform_api.routers.admin import (
        _get_audit_service as admin_get_audit,
        _get_suno_balance_service as admin_get_suno,
        _get_rate_limit_repo as admin_get_rate_limit,
    )

    async def real_admin_audit():
        return get_audit_service()

    async def real_admin_suno():
        return get_suno_balance_service()

    async def real_admin_rate_limit():
        return get_rate_limit_config_repo()

    app.dependency_overrides[admin_get_audit] = real_admin_audit
    app.dependency_overrides[admin_get_suno] = real_admin_suno
    app.dependency_overrides[admin_get_rate_limit] = real_admin_rate_limit

    # --- batch.py ---
    from platform_api.routers.batch import _get_batch_service as batch_get_svc

    async def real_batch_service():
        return get_batch_service()

    app.dependency_overrides[batch_get_svc] = real_batch_service

    # --- callbacks.py ---
    from platform_api.routers.callbacks import (
        _get_suno_task_repo as cb_get_task_repo,
        _get_notification_port as cb_get_notif,
    )

    async def real_suno_task_repo():
        return get_batch_repo()

    async def real_notification_port():
        return get_notification_service()

    app.dependency_overrides[cb_get_task_repo] = real_suno_task_repo
    app.dependency_overrides[cb_get_notif] = real_notification_port

    # --- credits.py ---
    from platform_api.routers.credits import (
        _get_credit_repo as credits_get_repo,
        _get_pricing_service as credits_get_pricing,
        _get_pack_repo as credits_get_pack,
        _get_settings_service as credits_get_settings,
        _get_credit_service as credits_get_credit_svc,
    )

    async def real_credit_repo():
        return get_credit_repo()

    async def real_pricing_service():
        return get_credit_pricing_service()

    async def real_pack_repo():
        return get_credit_repo()

    async def real_credits_settings_service():
        return get_settings_service()

    async def real_credits_credit_service():
        from platform_api.dependencies import get_credit_operation_service
        return get_credit_operation_service()

    app.dependency_overrides[credits_get_repo] = real_credit_repo
    app.dependency_overrides[credits_get_pricing] = real_pricing_service
    app.dependency_overrides[credits_get_pack] = real_pack_repo
    app.dependency_overrides[credits_get_settings] = real_credits_settings_service
    app.dependency_overrides[credits_get_credit_svc] = real_credits_credit_service

    # --- generation.py ---
    from platform_api.routers.generation import (
        _get_generation_service as gen_get_svc,
        _get_task_lookup as gen_get_task,
    )

    async def real_generation_service():
        return get_generation_service()

    async def real_task_lookup():
        return get_batch_repo()

    app.dependency_overrides[gen_get_svc] = real_generation_service
    app.dependency_overrides[gen_get_task] = real_task_lookup

    # --- licenses.py ---
    from platform_api.routers.licenses import (
        _get_license_repo as lic_get_repo,
        _get_plan_repo as lic_get_plan,
    )

    async def real_license_repo():
        return get_license_repo()

    async def real_lic_plan_repo():
        return get_plan_repo()

    app.dependency_overrides[lic_get_repo] = real_license_repo
    app.dependency_overrides[lic_get_plan] = real_lic_plan_repo

    # --- plans.py ---
    from platform_api.routers.plans import _get_plan_repo as plans_get_repo

    async def real_plans_repo():
        return get_plan_repo()

    app.dependency_overrides[plans_get_repo] = real_plans_repo

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
