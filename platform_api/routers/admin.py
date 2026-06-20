"""Admin router for audit log, rate limits, and external balance monitoring.

Provides Admin-only endpoints for:
  - GET /admin/suno-balance: External Suno API credit balance
  - GET /admin/audit-log: Paginated, filtered audit log query
  - GET /admin/rate-limits: Current rate limit configuration
  - PUT /admin/rate-limits: Update rate limit configuration

All endpoints require Admin role authentication.

Requirements: 15.1, 19.4, 20.2
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.rate_limit_repo import (
    RateLimitConfigRepository,
)
from platform_api.services.audit_service import AuditService
from platform_api.services.suno_balance_service import SunoBalanceService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_audit_service() -> AuditService:
    """Placeholder dependency for AuditService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "AuditService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_suno_balance_service() -> SunoBalanceService:
    """Placeholder dependency for SunoBalanceService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "SunoBalanceService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_rate_limit_repo() -> RateLimitConfigRepository:
    """Placeholder dependency for RateLimitConfigRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "RateLimitConfigRepository dependency not configured. Wire via app.dependency_overrides."
    )


# ---------------------------------------------------------------------------
# Type aliases for dependency injection
# ---------------------------------------------------------------------------

AdminDep = Annotated[AuthContext, Depends(require_admin)]
AuditServiceDep = Annotated[AuditService, Depends(_get_audit_service)]
SunoBalanceDep = Annotated[SunoBalanceService, Depends(_get_suno_balance_service)]
RateLimitRepoDep = Annotated[RateLimitConfigRepository, Depends(_get_rate_limit_repo)]


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    """A single audit log entry in the response."""

    id: str
    actor_id: str | None = None
    action_type: str
    target_resource: str | None = None
    outcome: str
    credit_impact: int = 0
    source_ip: str | None = None
    client_id: str | None = None
    endpoint_path: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str  # ISO 8601 timestamp


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""

    entries: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    total_pages: int


class SunoBalanceResponse(BaseModel):
    """External Suno API credit balance response."""

    credits: int | None = None
    status: str  # "ok", "cached", or "unknown"
    raw: dict[str, Any] | None = None


class RateLimitConfigEntry(BaseModel):
    """A rate limit configuration entry."""

    id: str | None = None
    endpoint_type: str
    max_requests: int
    window_seconds: int
    updated_at: str | None = None


class RateLimitConfigListResponse(BaseModel):
    """List of all rate limit configurations."""

    configs: list[RateLimitConfigEntry]


class RateLimitUpdateRequest(BaseModel):
    """Request body to update a rate limit configuration."""

    endpoint_type: str = Field(min_length=1, max_length=50)
    max_requests: int = Field(ge=1, le=100000)
    window_seconds: int = Field(ge=1, le=86400)


class RateLimitUpdateResponse(BaseModel):
    """Response after updating a rate limit configuration."""

    endpoint_type: str
    max_requests: int
    window_seconds: int
    updated_at: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/suno-balance",
    response_model=SunoBalanceResponse,
    summary="Get external Suno API credit balance",
)
async def get_suno_balance(
    ctx: AdminDep,
    suno_balance_service: SunoBalanceDep,
) -> SunoBalanceResponse:
    """Query the platform's external Suno API credit balance.

    Returns the current balance (cached for 30s) or 'unknown' if unreachable.

    Requirement 15.1: Admin endpoint for external Suno balance monitoring.
    """
    balance_data = await suno_balance_service.get_balance()
    return SunoBalanceResponse(
        credits=balance_data.get("credits"),
        status=balance_data.get("status", "unknown"),
        raw=balance_data.get("raw"),
    )


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Query audit log with filters",
)
async def get_audit_log(
    ctx: AdminDep,
    audit_service: AuditServiceDep,
    actor_id: str | None = Query(default=None, description="Filter by actor UUID"),
    action_type: str | None = Query(default=None, description="Filter by action type"),
    resource_type: str | None = Query(default=None, description="Filter by resource type prefix"),
    from_date: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    to_date: datetime | None = Query(default=None, description="Filter to date (ISO 8601)"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Entries per page (max 200)"),
) -> AuditLogResponse:
    """Query the audit log with optional filters and pagination.

    Returns the first page of results within 2 seconds.

    Requirement 20.2: Paginated audit log with filters (default 50, max 200).
    """
    result = await audit_service.query(
        actor_id=actor_id,
        action_type=action_type,
        resource_type=resource_type,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )

    entries = [
        AuditLogEntry(
            id=str(entry.id),
            actor_id=str(entry.actor_id) if entry.actor_id else None,
            action_type=entry.action_type,
            target_resource=entry.target_resource,
            outcome=entry.outcome,
            credit_impact=entry.credit_impact,
            source_ip=entry.source_ip,
            client_id=entry.client_id,
            endpoint_path=entry.endpoint_path,
            metadata=entry.metadata,
            created_at=entry.created_at.isoformat() + "Z"
            if entry.created_at
            else "",
        )
        for entry in result.entries
    ]

    return AuditLogResponse(
        entries=entries,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@router.get(
    "/rate-limits",
    response_model=RateLimitConfigListResponse,
    summary="Get all rate limit configurations",
)
async def get_rate_limits(
    ctx: AdminDep,
    rate_limit_repo: RateLimitRepoDep,
) -> RateLimitConfigListResponse:
    """Return all configured rate limit records.

    Requirement 19.4: Admin can view rate limit configuration.
    """
    records = await rate_limit_repo.get_all()
    configs = [
        RateLimitConfigEntry(
            id=record.id if record.id else None,
            endpoint_type=record.endpoint_type,
            max_requests=record.max_requests,
            window_seconds=record.window_seconds,
            updated_at=record.updated_at.isoformat() + "Z"
            if record.updated_at
            else None,
        )
        for record in records
    ]
    return RateLimitConfigListResponse(configs=configs)


@router.put(
    "/rate-limits",
    response_model=RateLimitUpdateResponse,
    summary="Update rate limit configuration",
)
async def update_rate_limits(
    request: RateLimitUpdateRequest,
    ctx: AdminDep,
    rate_limit_repo: RateLimitRepoDep,
) -> RateLimitUpdateResponse:
    """Update rate limit configuration for an endpoint type.

    The new limit applies within 5 seconds (Redis cache TTL).

    Requirement 19.4: Admin live-update of rate limit config.
    """
    record = await rate_limit_repo.upsert(
        endpoint_type=request.endpoint_type,
        max_requests=request.max_requests,
        window_seconds=request.window_seconds,
    )
    return RateLimitUpdateResponse(
        endpoint_type=record.endpoint_type,
        max_requests=record.max_requests,
        window_seconds=record.window_seconds,
        updated_at=record.updated_at.isoformat() + "Z"
        if record.updated_at
        else None,
    )


# ---------------------------------------------------------------------------
# System Settings (API Keys, Model Config)
# ---------------------------------------------------------------------------


class SystemSettingEntry(BaseModel):
    """A single system setting key-value pair."""
    key: str
    value: str
    value_type: str = "string"
    updated_at: str | None = None


class SystemSettingsResponse(BaseModel):
    """Response for system settings list."""
    settings: list[SystemSettingEntry]


class UpsertSettingRequest(BaseModel):
    """Request for creating/updating a system setting."""
    key: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=0)
    value_type: str = Field(default="string", description="Type: string, number, boolean, json")


@router.get(
    "/system-settings",
    response_model=SystemSettingsResponse,
    summary="Get all system settings (Admin)",
)
async def get_system_settings(ctx: AdminDep) -> SystemSettingsResponse:
    """Return all system settings (API keys, model configs, etc.)."""
    from platform_api.dependencies import get_db_pool
    pool = get_db_pool()
    rows = await pool.fetch(
        "SELECT key, value, value_type, updated_at FROM system_settings ORDER BY key"
    )
    settings = [
        SystemSettingEntry(
            key=row["key"],
            value=row["value"],
            value_type=row["value_type"],
            updated_at=row["updated_at"].isoformat() + "Z" if row["updated_at"] else None,
        )
        for row in rows
    ]
    return SystemSettingsResponse(settings=settings)


@router.put(
    "/system-settings",
    response_model=SystemSettingEntry,
    summary="Create or update a system setting (Admin)",
)
async def upsert_system_setting(
    request: UpsertSettingRequest,
    ctx: AdminDep,
) -> SystemSettingEntry:
    """Create or update a system setting. Used for API keys, model configs, etc."""
    from platform_api.dependencies import get_db_pool
    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE SET value = $2, value_type = $3, updated_at = NOW()
        RETURNING key, value, value_type, updated_at
        """,
        request.key,
        request.value,
        request.value_type,
    )
    return SystemSettingEntry(
        key=row["key"],
        value=row["value"],
        value_type=row["value_type"],
        updated_at=row["updated_at"].isoformat() + "Z" if row["updated_at"] else None,
    )


@router.delete(
    "/system-settings/{key}",
    status_code=200,
    summary="Delete a system setting (Admin)",
)
async def delete_system_setting(key: str, ctx: AdminDep) -> dict[str, str]:
    """Delete a system setting by key."""
    from platform_api.dependencies import get_db_pool
    pool = get_db_pool()
    await pool.execute("DELETE FROM system_settings WHERE key = $1", key)
    return {"message": f"Setting '{key}' deleted."}
