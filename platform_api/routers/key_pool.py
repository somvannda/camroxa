"""Key Pool admin router for managing API keys across providers.

Provides Admin-only endpoints for:
  - Listing, adding, updating, and removing API keys per provider
  - Enabling/disabling keys
  - Configuring provider selection strategy and cooldown
  - Viewing provider health summaries and status events

All endpoints require Admin role authentication.

Requirements: 1.2, 1.3, 1.4, 1.5, 2.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.3
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.models.schemas import (
    AddKeyRequest,
    AllProvidersHealthResponse,
    KeyEntryResponse,
    KeyStatusEventResponse,
    ProviderConfigRequest,
    ProviderConfigResponse,
    ProviderHealthResponse,
    UpdateKeyRequest,
)
from platform_api.services.key_pool_service import KeyPoolService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/admin/key-pool", tags=["key-pool"])


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_key_pool_service() -> KeyPoolService:
    """Placeholder dependency for KeyPoolService — override via app.dependency_overrides."""
    raise NotImplementedError(
        "KeyPoolService dependency not configured. Wire via app.dependency_overrides."
    )


# ---------------------------------------------------------------------------
# Type aliases for dependency injection
# ---------------------------------------------------------------------------

AdminDep = Annotated[AuthContext, Depends(require_admin)]
KeyPoolServiceDep = Annotated[KeyPoolService, Depends(_get_key_pool_service)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_key(decrypted_key: str | None) -> str:
    """Mask an API key value, showing first 4 and last 4 characters.

    If the key is shorter than 8 characters, returns '****'.
    """
    if decrypted_key is None:
        return "****"
    if len(decrypted_key) < 8:
        return "****"
    return f"{decrypted_key[:4]}...{decrypted_key[-4:]}"


# ---------------------------------------------------------------------------
# All-providers health endpoint (MUST be before /{provider}/... routes to avoid
# "health" being captured as a path parameter)
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=AllProvidersHealthResponse,
    summary="Get all providers health summary",
)
async def get_all_providers_health(
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> AllProvidersHealthResponse:
    """Get health summaries for all providers that have key entries.

    Requirement 7.1: All-providers health overview.
    """
    providers = await key_pool_service._repo.get_all_providers()
    results: list[ProviderHealthResponse] = []
    for provider in providers:
        status = await key_pool_service.get_pool_status(provider)
        results.append(ProviderHealthResponse(**status))
    return AllProvidersHealthResponse(providers=results)


# ---------------------------------------------------------------------------
# Key-level endpoints (no {provider} prefix — uses /keys/{key_id})
# These MUST be before /{provider}/... routes to avoid "keys" being captured.
# ---------------------------------------------------------------------------


@router.patch(
    "/keys/{key_id}",
    response_model=KeyEntryResponse,
    summary="Update key label/priority/value",
)
async def update_key(
    key_id: UUID,
    request: UpdateKeyRequest,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> KeyEntryResponse:
    """Update an existing key's label, priority, or encrypted value.

    All fields are optional — only provided fields are updated.

    Requirement 6.5: Edit key metadata.
    """
    entry = await key_pool_service._repo.get_by_id(key_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Key not found.")

    await key_pool_service.update_key(
        key_id,
        label=request.label,
        priority=request.priority,
        key_value=request.key_value,
    )

    # Fetch updated entry
    updated_entry = await key_pool_service._repo.get_by_id(key_id)
    if updated_entry is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated key.")

    try:
        decrypted = key_pool_service._encryption.decrypt(updated_entry.encrypted_key_value)
        masked = _mask_key(decrypted)
    except Exception:
        masked = "****"

    return KeyEntryResponse(
        id=updated_entry.id,
        provider=updated_entry.provider,
        label=updated_entry.label,
        masked_key=masked,
        priority=updated_entry.priority,
        status=updated_entry.status.value,
        total_requests=updated_entry.total_requests,
        daily_requests=updated_entry.daily_requests,
        success_count=updated_entry.success_count,
        failure_count=updated_entry.failure_count,
        rate_limit_hits=updated_entry.rate_limit_hits,
        last_used_at=updated_entry.last_used_at,
        last_failure_at=updated_entry.last_failure_at,
        cooldown_remaining_seconds=None,
        created_at=updated_entry.created_at,
    )


@router.delete(
    "/keys/{key_id}",
    status_code=204,
    summary="Remove key from pool",
)
async def delete_key(
    key_id: UUID,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> Response:
    """Remove an API key from the pool entirely.

    Requirement 6.6: Remove key with confirmation.
    """
    entry = await key_pool_service._repo.get_by_id(key_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Key not found.")

    await key_pool_service.remove_key(key_id)
    return Response(status_code=204)


@router.post(
    "/keys/{key_id}/enable",
    response_model=KeyEntryResponse,
    summary="Enable a key (set status to active)",
)
async def enable_key(
    key_id: UUID,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> KeyEntryResponse:
    """Set a key's status to active.

    Requirement 6.3: Enable/disable keys manually.
    """
    entry = await key_pool_service._repo.get_by_id(key_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Key not found.")

    await key_pool_service.set_key_status(key_id, "active")

    updated_entry = await key_pool_service._repo.get_by_id(key_id)
    if updated_entry is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated key.")

    try:
        decrypted = key_pool_service._encryption.decrypt(updated_entry.encrypted_key_value)
        masked = _mask_key(decrypted)
    except Exception:
        masked = "****"

    return KeyEntryResponse(
        id=updated_entry.id,
        provider=updated_entry.provider,
        label=updated_entry.label,
        masked_key=masked,
        priority=updated_entry.priority,
        status=updated_entry.status.value,
        total_requests=updated_entry.total_requests,
        daily_requests=updated_entry.daily_requests,
        success_count=updated_entry.success_count,
        failure_count=updated_entry.failure_count,
        rate_limit_hits=updated_entry.rate_limit_hits,
        last_used_at=updated_entry.last_used_at,
        last_failure_at=updated_entry.last_failure_at,
        cooldown_remaining_seconds=None,
        created_at=updated_entry.created_at,
    )


@router.post(
    "/keys/{key_id}/disable",
    response_model=KeyEntryResponse,
    summary="Disable a key (set status to disabled)",
)
async def disable_key(
    key_id: UUID,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> KeyEntryResponse:
    """Set a key's status to disabled.

    Requirement 6.4: Disable key manually.
    """
    entry = await key_pool_service._repo.get_by_id(key_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Key not found.")

    await key_pool_service.set_key_status(key_id, "disabled")

    updated_entry = await key_pool_service._repo.get_by_id(key_id)
    if updated_entry is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated key.")

    try:
        decrypted = key_pool_service._encryption.decrypt(updated_entry.encrypted_key_value)
        masked = _mask_key(decrypted)
    except Exception:
        masked = "****"

    return KeyEntryResponse(
        id=updated_entry.id,
        provider=updated_entry.provider,
        label=updated_entry.label,
        masked_key=masked,
        priority=updated_entry.priority,
        status=updated_entry.status.value,
        total_requests=updated_entry.total_requests,
        daily_requests=updated_entry.daily_requests,
        success_count=updated_entry.success_count,
        failure_count=updated_entry.failure_count,
        rate_limit_hits=updated_entry.rate_limit_hits,
        last_used_at=updated_entry.last_used_at,
        last_failure_at=updated_entry.last_failure_at,
        cooldown_remaining_seconds=None,
        created_at=updated_entry.created_at,
    )


# ---------------------------------------------------------------------------
# Provider-scoped endpoints (/{provider}/...)
# ---------------------------------------------------------------------------


@router.get(
    "/{provider}/keys",
    response_model=list[KeyEntryResponse],
    summary="List all keys for a provider",
)
async def list_keys(
    provider: str,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> list[KeyEntryResponse]:
    """Return all API key entries for the specified provider.

    Keys are returned with masked values (first 4 + last 4 chars visible).

    Requirement 6.1: List keys per provider with masked values.
    """
    entries = await key_pool_service._repo.list_by_provider(provider)

    results: list[KeyEntryResponse] = []
    for entry in entries:
        # Decrypt key to build masked version
        try:
            decrypted = key_pool_service._encryption.decrypt(entry.encrypted_key_value)
            masked = _mask_key(decrypted)
        except Exception:
            masked = "****"

        # Check cooldown remaining for rate-limited keys
        cooldown_remaining: int | None = None
        if entry.status.value == "rate_limited":
            try:
                ttl = await key_pool_service._redis.ttl(
                    f"key_pool:{provider}:cooldown:{entry.id}"
                )
                if ttl > 0:
                    cooldown_remaining = ttl
            except Exception:
                pass

        results.append(
            KeyEntryResponse(
                id=entry.id,
                provider=entry.provider,
                label=entry.label,
                masked_key=masked,
                priority=entry.priority,
                status=entry.status.value,
                total_requests=entry.total_requests,
                daily_requests=entry.daily_requests,
                success_count=entry.success_count,
                failure_count=entry.failure_count,
                rate_limit_hits=entry.rate_limit_hits,
                last_used_at=entry.last_used_at,
                last_failure_at=entry.last_failure_at,
                cooldown_remaining_seconds=cooldown_remaining,
                created_at=entry.created_at,
            )
        )
    return results


@router.post(
    "/{provider}/keys",
    response_model=KeyEntryResponse,
    status_code=201,
    summary="Add a new key to provider pool",
)
async def add_key(
    provider: str,
    request: AddKeyRequest,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> KeyEntryResponse:
    """Add a new API key to the specified provider's pool.

    Validates the input, encrypts the key value, and stores with
    initial status of active.

    Requirement 6.2: Add key with label, value, priority.
    """
    key_id = await key_pool_service.add_key(
        provider=provider,
        key_value=request.key_value,
        label=request.label,
        priority=request.priority,
    )

    # Fetch the created entry to return full response
    entry = await key_pool_service._repo.get_by_id(key_id)
    if entry is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created key.")

    masked = _mask_key(request.key_value)

    return KeyEntryResponse(
        id=entry.id,
        provider=entry.provider,
        label=entry.label,
        masked_key=masked,
        priority=entry.priority,
        status=entry.status.value,
        total_requests=entry.total_requests,
        daily_requests=entry.daily_requests,
        success_count=entry.success_count,
        failure_count=entry.failure_count,
        rate_limit_hits=entry.rate_limit_hits,
        last_used_at=entry.last_used_at,
        last_failure_at=entry.last_failure_at,
        cooldown_remaining_seconds=None,
        created_at=entry.created_at,
    )


@router.get(
    "/{provider}/config",
    response_model=ProviderConfigResponse,
    summary="Get provider pool configuration",
)
async def get_provider_config(
    provider: str,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> ProviderConfigResponse:
    """Get the current key pool configuration for a provider.

    Returns the selection strategy and cooldown seconds. If no configuration
    has been set, returns defaults (priority strategy, 60s cooldown).

    Requirement 6.7: View provider configuration.
    """
    config = await key_pool_service._repo.get_provider_config(provider)
    if config is None:
        return ProviderConfigResponse(
            provider=provider,
            selection_strategy="priority",
            cooldown_seconds=60,
        )

    return ProviderConfigResponse(
        provider=config.provider,
        selection_strategy=config.selection_strategy.value,
        cooldown_seconds=config.cooldown_seconds,
    )


@router.put(
    "/{provider}/config",
    response_model=ProviderConfigResponse,
    summary="Update provider pool configuration",
)
async def update_provider_config(
    provider: str,
    request: ProviderConfigRequest,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> ProviderConfigResponse:
    """Update the selection strategy and cooldown for a provider.

    Requirement 2.4, 6.7: Configure strategy and cooldown.
    """
    await key_pool_service.configure_provider(
        provider,
        strategy=request.selection_strategy,
        cooldown_seconds=request.cooldown_seconds,
    )

    return ProviderConfigResponse(
        provider=provider,
        selection_strategy=request.selection_strategy,
        cooldown_seconds=request.cooldown_seconds,
    )


@router.get(
    "/{provider}/health",
    response_model=ProviderHealthResponse,
    summary="Get provider health summary",
)
async def get_provider_health(
    provider: str,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
) -> ProviderHealthResponse:
    """Get the health summary for a single provider's key pool.

    Requirement 7.1: Per-provider health indicator.
    """
    status = await key_pool_service.get_pool_status(provider)
    return ProviderHealthResponse(**status)


@router.get(
    "/{provider}/events",
    response_model=list[KeyStatusEventResponse],
    summary="Get recent status events for a provider",
)
async def get_provider_events(
    provider: str,
    ctx: AdminDep,
    key_pool_service: KeyPoolServiceDep,
    limit: int = Query(default=50, ge=1, le=200, description="Max events to return"),
) -> list[KeyStatusEventResponse]:
    """Get recent key status transition events for a provider.

    Requirement 7.3: Status transition event log.
    """
    events = await key_pool_service._repo.get_recent_events(provider, limit=limit)
    return [
        KeyStatusEventResponse(
            id=event["id"],
            key_label=event["key_label"],
            previous_status=event["previous_status"],
            new_status=event["new_status"],
            trigger_reason=event["trigger_reason"],
            http_status_code=event["http_status_code"],
            created_at=event["created_at"],
        )
        for event in events
    ]
