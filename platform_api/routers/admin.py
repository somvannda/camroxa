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

import asyncio
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from platform_api.config import get_settings
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.utils.datetime_utils import format_utc_iso
from platform_api.models.enums import UserRole
from platform_api.models.reset_models import (
    BackupListResponse,
    BackupMetadataResponse,
    ResetRequest,
    ResetResponse,
    RestoreRequest,
    RestoreResponse,
)
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.repositories.rate_limit_repo import (
    RateLimitConfigRepository,
)
from platform_api.repositories.user_repo import UserRepository
from platform_api.services.audit_service import AuditService
from platform_api.services.billing_config_service import (
    CHMABA_API_BASE_URL_KEY,
    CHMABA_API_KEY_SETTING,
    CHMABA_STORE_ID_KEY,
    CHMABA_WEBHOOK_SECRET_KEY,
    CUTLUY_API_BASE_URL_KEY,
    CUTLUY_PAYMENT_LINK_ID_KEY,
    CUTLUY_SECRET_KEY_SETTING,
    CUTLUY_WEBHOOK_SECRET_KEY,
    mask_secret_value,
    normalize_cutluy_payment_link_id,
    resolve_chmaba_config,
    resolve_cutluy_config,
)
from platform_api.services.credit_units import units_to_credits
from platform_api.services.key_encryption import KeyEncryption
from platform_api.services.reset_service import ResetService
from platform_api.services.provider_key_balance_service import ProviderKeyBalanceService
from platform_api.services.suno_balance_service import SunoBalanceService
from platform_api.services.usage_transaction_labels import enrich_transaction_for_api
from platform_api.repositories.youtube_oauth_app_repo import YouTubeOAuthAppRepository

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


async def _get_provider_key_balance_service() -> ProviderKeyBalanceService:
    """Placeholder dependency for ProviderKeyBalanceService — override in wire_dependencies."""
    raise NotImplementedError(
        "ProviderKeyBalanceService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_rate_limit_repo() -> RateLimitConfigRepository:
    """Placeholder dependency for RateLimitConfigRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "RateLimitConfigRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_settings_repo():
    """Placeholder dependency for SettingsRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "SettingsRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_youtube_oauth_app_repo() -> YouTubeOAuthAppRepository:
    """Placeholder dependency for YouTubeOAuthAppRepository."""
    raise NotImplementedError(
        "YouTubeOAuthAppRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_youtube_oauth_encryption() -> KeyEncryption | None:
    """Placeholder dependency for YouTube OAuth secret encryption."""
    raise NotImplementedError(
        "YouTube OAuth encryption dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_credit_repo() -> CreditRepository:
    """Placeholder dependency for CreditRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "CreditRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_user_spend_service() -> Any:
    """Placeholder dependency for UserSpendService — override in wire_dependencies."""
    raise NotImplementedError(
        "UserSpendService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_user_repo() -> UserRepository:
    """Placeholder dependency for UserRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "UserRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_batch_repo():
    """Placeholder dependency for BatchRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "BatchRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_reset_service() -> ResetService:
    """Placeholder dependency for ResetService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "ResetService dependency not configured. Wire via app.dependency_overrides."
    )


# ---------------------------------------------------------------------------
# Type aliases for dependency injection
# ---------------------------------------------------------------------------

AdminDep = Annotated[AuthContext, Depends(require_admin)]
AuditServiceDep = Annotated[AuditService, Depends(_get_audit_service)]
SunoBalanceDep = Annotated[SunoBalanceService, Depends(_get_suno_balance_service)]
ProviderKeyBalanceDep = Annotated[
    ProviderKeyBalanceService, Depends(_get_provider_key_balance_service)
]
RateLimitRepoDep = Annotated[RateLimitConfigRepository, Depends(_get_rate_limit_repo)]
SettingsRepoDep = Annotated[Any, Depends(_get_settings_repo)]
YouTubeOAuthAppRepoDep = Annotated[
    YouTubeOAuthAppRepository, Depends(_get_youtube_oauth_app_repo)
]
YouTubeOAuthEncryptionDep = Annotated[
    KeyEncryption | None, Depends(_get_youtube_oauth_encryption)
]
CreditRepoDep = Annotated[CreditRepository, Depends(_get_credit_repo)]
UserSpendServiceDep = Annotated[Any, Depends(_get_user_spend_service)]
UserRepoDep = Annotated[UserRepository, Depends(_get_user_repo)]
BatchRepoDep = Annotated[Any, Depends(_get_batch_repo)]
ResetServiceDep = Annotated[ResetService, Depends(_get_reset_service)]


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    """A single audit log entry in the response."""

    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    actor_display_name: str | None = None
    actor_role: str | None = None
    actor_label: str | None = None
    action_type: str
    target_resource: str | None = None
    outcome: str
    credit_impact: int = 0
    credits_involved: bool = False
    credit_summary: str = "No recorded credit involvement."
    credit_direction: str | None = None
    credit_reason: str | None = None
    credit_reference: str | None = None
    payment_reference: str | None = None
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


class UsageLineItemResponse(BaseModel):
    operation: str
    provider: str | None = None
    model: str | None = None
    amount_units: int | None = None
    amount: float | None = None


class UsageEntryResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_display_name: str
    amount: float
    amount_units: int
    direction: str
    reason: str
    purpose: str
    provider: str | None = None
    model: str | None = None
    operation: str | None = None
    category: str | None = None
    line_items_summary: str | None = None
    line_items: list[UsageLineItemResponse] = Field(default_factory=list)
    ref_id: str | None = None
    batch_id: str | None = None
    song_id: str | None = None
    batch_index: int | None = None
    attempts_used: int | None = None
    llm_calls_title: int | None = None
    llm_calls_album: int | None = None
    llm_calls_lyric: int | None = None
    source: str | None = None
    billing: str | None = None
    list_credit_units: int | None = None
    charged_credit_units: int | None = None
    coverage: str | None = None
    metadata: dict[str, Any] | None = None
    legacy: bool = False
    created_at: str | None = None


class UsageFiltersResponse(BaseModel):
    providers: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)


class UsageSummaryResponse(BaseModel):
    billable_events: int = 0
    credit_cost: float = 0
    refund_total: float = 0
    refund_events: int = 0
    net_credit_cost: float = 0
    wallet_charged: float = 0
    plan_included_list: float = 0
    plan_allowance_events: int = 0
    plan_draft_list: float = 0
    plan_song_list: float = 0
    plan_image_list: float = 0
    platform_absorb_events: int = 0
    platform_absorb_list: float = 0
    subscription_revenue_cents: int = 0
    subscription_payment_count: int = 0
    credit_pack_revenue_cents: int = 0
    credit_pack_payment_count: int = 0
    grant_issued: float = 0
    grant_issued_events: int = 0
    by_operation: list[dict[str, Any]] = Field(default_factory=list)


class UsageListResponse(BaseModel):
    items: list[UsageEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    summary: UsageSummaryResponse


class UserSpendMeterResponse(BaseModel):
    used: int = 0
    limit: int | None = None
    pct: float | None = None
    hot: bool = False


class UserSpendCogResponse(BaseModel):
    provider: str = ""
    operation: str
    model: str = ""
    events: int = 0
    plan_included_usd: float = 0
    wallet_usd: float = 0
    est_cogs_usd: float | None = None
    coverage: str = "none"


class UserSpendAlertsResponse(BaseModel):
    over_allowance: bool = False
    margin_risk: bool = False
    meters_hot: list[str] = Field(default_factory=list)


class UserSpendItemResponse(BaseModel):
    user_id: str
    email: str
    display_name: str | None = None
    plan_id: str | None = None
    plan_name: str = "Free"
    plan_price_cents: int = 0
    billing_cycle_days: int | None = None
    plan_revenue_usd: float = 0
    est_cogs_usd: float = 0
    wallet_charged_usd: float = 0
    plan_included_usd: float = 0
    soft_overage_events: int = 0
    meters: dict[str, UserSpendMeterResponse] = Field(default_factory=dict)
    alerts: UserSpendAlertsResponse = Field(default_factory=UserSpendAlertsResponse)
    by_cog: list[UserSpendCogResponse] = Field(default_factory=list)


class UserSpendSummaryResponse(BaseModel):
    users_over_allowance: int = 0
    users_margin_risk: int = 0
    total_est_cogs_usd: float = 0
    total_wallet_usd: float = 0
    gcv: float = 0.01


class UserSpendListResponse(BaseModel):
    items: list[UserSpendItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    summary: UserSpendSummaryResponse


class AdminBatchSongSummary(BaseModel):
    id: str
    batch_index: int
    title: str | None = None
    album: str | None = None
    status: str


class AdminBatchSummaryResponse(BaseModel):
    id: str
    user_id: str
    user_email: str = ""
    user_display_name: str = ""
    status: str
    song_count: int
    language: str = "en"
    created_at: str | None = None
    updated_at: str | None = None
    songs: list[AdminBatchSongSummary] = Field(default_factory=list)


class AdminStuckBatchItem(BaseModel):
    batch_id: str
    user_id: str | None = None
    user_email: str | None = None
    status: str
    last_activity_at: str | None = None
    age_seconds: int


class AdminStuckBatchesResponse(BaseModel):
    items: list[AdminStuckBatchItem] = Field(default_factory=list)
    threshold_seconds: int


class AdminSongSummaryResponse(BaseModel):
    id: str
    batch_id: str
    batch_index: int
    user_id: str
    user_email: str = ""
    user_display_name: str = ""
    title: str | None = None
    album: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class SunoBalanceResponse(BaseModel):
    """External Suno API credit balance response."""

    credits: int | None = None
    status: str  # "ok", "cached", or "unknown"
    raw: dict[str, Any] | None = None


class ProviderKeyBalanceItem(BaseModel):
    """Balance for one key-pool entry."""

    key_id: str
    label: str
    key_status: str
    priority: int = 50
    balance: float | None = None
    currency: str | None = None
    unit: str = "credits"
    display: str | None = None
    fetch_status: str
    error: str | None = None
    checked_at: str | None = None
    used_today: float | None = None
    day_start_balance: float | None = None


class ProviderKeyBalanceGroup(BaseModel):
    provider: str
    keys: list[ProviderKeyBalanceItem] = Field(default_factory=list)
    error: str | None = None


class ProviderKeyBalancesResponse(BaseModel):
    providers: list[ProviderKeyBalanceGroup]
    checked_at: str


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


class SlaiImageProviderConfigResponse(BaseModel):
    """SLAI image throttling and retry settings (admin-managed)."""

    min_interval_seconds: float = Field(ge=0.0, le=120.0)
    max_concurrent: int = Field(ge=1, le=8)
    provider_retries: int = Field(ge=1, le=20)
    retry_base_delay_seconds: float = Field(ge=0.0, le=120.0)
    retry_max_delay_seconds: float = Field(ge=1.0, le=300.0)
    fallback_provider_retries: int = Field(ge=1, le=5)


class YouTubeOAuthAppEntry(BaseModel):
    """Metadata for a stored YouTube OAuth application."""

    id: str
    name: str
    client_id: str
    is_default: bool
    has_client_secret: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class YouTubeOAuthAppsResponse(BaseModel):
    """List response for admin-managed YouTube OAuth apps."""

    apps: list[YouTubeOAuthAppEntry]


class CreateYouTubeOAuthAppRequest(BaseModel):
    """Create a new YouTube OAuth app."""

    name: str = Field(..., min_length=1, max_length=120)
    client_id: str = Field(..., min_length=1, max_length=2048)
    client_secret: str = Field(..., min_length=1, max_length=4096)
    is_default: bool = False


class UpdateYouTubeOAuthAppRequest(BaseModel):
    """Update an existing YouTube OAuth app."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    client_id: str | None = Field(default=None, min_length=1, max_length=2048)
    client_secret: str | None = Field(default=None, min_length=1, max_length=4096)
    is_default: bool | None = None


def _format_iso_timestamp(value: datetime | None) -> str | None:
    return format_utc_iso(value)


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    normalized = str(value).strip()
    return normalized or None


def _normalize_role(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, UserRole):
        return value.value
    return _normalize_text(getattr(value, "value", value))


def _extract_credit_context(entry) -> tuple[bool, str, str | None, str | None, str | None, str | None]:
    metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
    reason = _normalize_text(
        metadata.get("credit_reason")
        or metadata.get("reason")
        or metadata.get("usage_reason")
    )
    reference = _normalize_text(
        metadata.get("ref_id")
        or metadata.get("reference_id")
        or metadata.get("batch_id")
        or metadata.get("song_id")
    )
    payment_reference = _normalize_text(
        metadata.get("payment_ref")
        or metadata.get("payment_reference")
        or metadata.get("checkout_session_id")
    )

    impact = int(entry.credit_impact or 0)
    action_type = entry.action_type or ""
    target_resource = entry.target_resource or ""
    credits_involved = False
    direction: str | None = None
    summary: str

    if impact > 0:
        credits_involved = True
        direction = "debit"
        summary = f"Deducted {impact} credits."
    elif impact < 0:
        credits_involved = True
        direction = "refund"
        summary = f"Refunded {abs(impact)} credits."
    elif action_type.startswith("credit.redeem"):
        credits_involved = True
        direction = "credit"
        summary = "Redeem code credited wallet."
    elif action_type.startswith("credit.pack"):
        credits_involved = True
        direction = "credit"
        summary = "Credit pack purchase credited wallet."
    elif action_type.startswith("credit.purchase"):
        credits_involved = True
        direction = "credit"
        summary = "Credit purchase activity recorded."
    elif action_type.startswith("credit.adjust"):
        credits_involved = True
        direction = "adjustment"
        summary = "Credit adjustment activity recorded."
    elif action_type.startswith("credit.pricing"):
        credits_involved = True
        summary = "Credit pricing configuration changed."
    elif target_resource.startswith("credit"):
        credits_involved = True
        summary = "Credit-related resource activity recorded."
    else:
        summary = "No recorded credit involvement."

    if reason:
        summary = f"{summary} Reason: {reason}."
    elif payment_reference:
        summary = f"{summary} Payment reference captured."
    elif reference:
        summary = f"{summary} Reference: {reference}."

    return (
        credits_involved,
        summary,
        direction,
        reason,
        reference,
        payment_reference,
    )


async def _resolve_actor_lookup(entries: list[Any], user_repo: UserRepository) -> dict[str, dict[str, str | None]]:
    actor_ids: list[UUID] = []
    seen: set[UUID] = set()

    for entry in entries:
        if not entry.actor_id:
            continue
        try:
            actor_uuid = UUID(str(entry.actor_id))
        except (TypeError, ValueError):
            continue
        if actor_uuid in seen:
            continue
        seen.add(actor_uuid)
        actor_ids.append(actor_uuid)

    if not actor_ids:
        return {}

    users = await asyncio.gather(*(user_repo.get_by_id(actor_id) for actor_id in actor_ids))
    lookup: dict[str, dict[str, str | None]] = {}

    for actor_uuid, user in zip(actor_ids, users):
        actor_key = str(actor_uuid)
        if user is None:
            lookup[actor_key] = {
                "actor_email": None,
                "actor_display_name": None,
                "actor_role": None,
                "actor_label": actor_key,
            }
            continue

        actor_email = _normalize_text(getattr(user, "email", None))
        actor_display_name = _normalize_text(getattr(user, "display_name", None))
        actor_role = _normalize_role(getattr(user, "role", None))
        actor_label = actor_display_name or actor_email or actor_key

        lookup[actor_key] = {
            "actor_email": actor_email,
            "actor_display_name": actor_display_name,
            "actor_role": actor_role,
            "actor_label": actor_label,
        }

    return lookup


def _to_youtube_oauth_app_entry(record) -> YouTubeOAuthAppEntry:
    return YouTubeOAuthAppEntry(
        id=record.id,
        name=record.name,
        client_id=record.client_id,
        is_default=record.is_default,
        has_client_secret=bool(record.encrypted_client_secret),
        created_at=_format_iso_timestamp(record.created_at),
        updated_at=_format_iso_timestamp(record.updated_at),
    )


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
    "/provider-key-balances",
    response_model=ProviderKeyBalancesResponse,
    summary="Get remaining credits/money for each key-pool entry",
)
async def get_provider_key_balances(
    ctx: AdminDep,
    balance_service: ProviderKeyBalanceDep,
    refresh: bool = Query(default=False, description="Bypass Redis cache"),
) -> ProviderKeyBalancesResponse:
    """List remaining provider balances by key label for dashboard top-up monitoring."""
    data = await balance_service.get_all_balances(force_refresh=refresh)
    providers = []
    for group in data.get("providers") or []:
        providers.append(
            ProviderKeyBalanceGroup(
                provider=str(group.get("provider") or ""),
                error=group.get("error"),
                keys=[
                    ProviderKeyBalanceItem(
                        key_id=str(item.get("key_id") or ""),
                        label=str(item.get("label") or ""),
                        key_status=str(item.get("key_status") or ""),
                        priority=int(item.get("priority") or 50),
                        balance=item.get("balance"),
                        currency=item.get("currency"),
                        unit=str(item.get("unit") or "credits"),
                        display=item.get("display"),
                        fetch_status=str(item.get("fetch_status") or "unknown"),
                        error=item.get("error"),
                        checked_at=item.get("checked_at"),
                        used_today=item.get("used_today"),
                        day_start_balance=item.get("day_start_balance"),
                    )
                    for item in (group.get("keys") or [])
                ],
            )
        )
    return ProviderKeyBalancesResponse(
        providers=providers,
        checked_at=str(data.get("checked_at") or ""),
    )


@router.get(
    "/audit-log",
    response_model=AuditLogResponse,
    summary="Query audit log with filters",
)
async def get_audit_log(
    ctx: AdminDep,
    audit_service: AuditServiceDep,
    user_repo: UserRepoDep,
    actor_id: str | None = Query(default=None, description="Filter by actor UUID"),
    action_type: str | None = Query(default=None, description="Filter by action type"),
    resource_type: str | None = Query(default=None, description="Filter by resource type prefix"),
    outcome: str | None = Query(default=None, description="Filter by outcome"),
    endpoint_path: str | None = Query(default=None, description="Filter by endpoint path"),
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
        outcome=outcome,
        endpoint_path=endpoint_path,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )

    actor_lookup = await _resolve_actor_lookup(result.entries, user_repo)
    entries: list[AuditLogEntry] = []
    for entry in result.entries:
        actor_key = str(entry.actor_id) if entry.actor_id else None
        actor_data = actor_lookup.get(actor_key, {}) if actor_key else {}
        (
            credits_involved,
            credit_summary,
            credit_direction,
            credit_reason,
            credit_reference,
            payment_reference,
        ) = _extract_credit_context(entry)

        entries.append(
            AuditLogEntry(
                id=str(entry.id),
                actor_id=actor_key,
                actor_email=actor_data.get("actor_email"),
                actor_display_name=actor_data.get("actor_display_name"),
                actor_role=actor_data.get("actor_role"),
                actor_label=actor_data.get("actor_label") if actor_key else "System",
                action_type=entry.action_type,
                target_resource=entry.target_resource,
                outcome=entry.outcome,
                credit_impact=entry.credit_impact,
                credits_involved=credits_involved,
                credit_summary=credit_summary,
                credit_direction=credit_direction,
                credit_reason=credit_reason,
                credit_reference=credit_reference,
                payment_reference=payment_reference,
                source_ip=entry.source_ip,
                client_id=entry.client_id,
                endpoint_path=entry.endpoint_path,
                metadata=entry.metadata,
                created_at=_format_iso_timestamp(entry.created_at) or "",
            )
        )

    return AuditLogResponse(
        entries=entries,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


def _usage_entry_to_response(row: dict[str, Any]) -> UsageEntryResponse:
    enriched = enrich_transaction_for_api(row)
    line_items_raw = enriched.get("line_items") or []
    line_items: list[UsageLineItemResponse] = []
    for item in line_items_raw:
        if not isinstance(item, dict):
            continue
        amount_units = item.get("amount_units")
        line_items.append(
            UsageLineItemResponse(
                operation=str(item.get("operation") or ""),
                provider=item.get("provider"),
                model=item.get("model") or item.get("sub_model"),
                amount_units=int(amount_units) if isinstance(amount_units, (int, float)) else None,
                amount=units_to_credits(int(amount_units))
                if isinstance(amount_units, (int, float))
                else None,
            )
        )

    created_at = enriched.get("created_at")
    return UsageEntryResponse(
        id=str(enriched["id"]),
        user_id=str(enriched["user_id"]),
        user_email=str(enriched.get("user_email") or ""),
        user_display_name=str(enriched.get("user_display_name") or ""),
        amount=float(enriched["amount"]),
        amount_units=int(enriched["amount_units"]),
        direction=str(enriched.get("direction") or "debit"),
        reason=str(enriched.get("reason") or ""),
        purpose=str(enriched.get("purpose") or ""),
        provider=enriched.get("provider"),
        model=enriched.get("model"),
        operation=enriched.get("operation"),
        category=enriched.get("category"),
        line_items_summary=enriched.get("line_items_summary"),
        line_items=line_items,
        ref_id=enriched.get("ref_id"),
        batch_id=enriched.get("batch_id"),
        song_id=enriched.get("song_id"),
        batch_index=enriched.get("batch_index"),
        attempts_used=enriched.get("attempts_used"),
        llm_calls_title=enriched.get("llm_calls_title"),
        llm_calls_album=enriched.get("llm_calls_album"),
        llm_calls_lyric=enriched.get("llm_calls_lyric"),
        source=enriched.get("source"),
        billing=enriched.get("billing"),
        list_credit_units=int(enriched["list_credit_units"])
        if isinstance(enriched.get("list_credit_units"), (int, float))
        else None,
        charged_credit_units=int(enriched["charged_credit_units"])
        if isinstance(enriched.get("charged_credit_units"), (int, float))
        else None,
        coverage=enriched.get("coverage"),
        metadata=enriched.get("metadata"),
        legacy=bool(enriched.get("legacy")),
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
    )


@router.get(
    "/usage/filters",
    response_model=UsageFiltersResponse,
    summary="List provider and operation filter options for usage",
)
async def get_usage_filters(
    ctx: AdminDep,
    credit_repo: CreditRepoDep,
) -> UsageFiltersResponse:
    del ctx
    options = await credit_repo.get_usage_filter_options()
    return UsageFiltersResponse(
        providers=options.get("providers", []),
        operations=options.get("operations", []),
    )


class ExportTelemetryEntry(BaseModel):
    id: str
    user_id: str
    user_email: str = ""
    operation_type: str
    ref_id: str | None = None
    track_count: int = 0
    completed_count: int = 0
    duration_ms: int | None = None
    codec: str | None = None
    resolution: str | None = None
    fps: int | None = None
    export_tier: str | None = None
    speed_mode: str | None = None
    hw_cpu: str | None = None
    hw_gpu: str | None = None
    hw_encoder: str | None = None
    app_version: str | None = None
    created_at: str | None = None


class ExportTelemetryListResponse(BaseModel):
    items: list[ExportTelemetryEntry]
    total: int


@router.get(
    "/export-telemetry",
    response_model=ExportTelemetryListResponse,
    summary="List desktop video export duration/hardware telemetry",
)
async def list_export_telemetry(
    ctx: AdminDep,
    user_id: str | None = Query(default=None),
    operation_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ExportTelemetryListResponse:
    del ctx
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    clauses = ["1=1"]
    args: list[Any] = []
    if user_id:
        args.append(user_id)
        clauses.append(f"t.user_id = ${len(args)}::uuid")
    if operation_type:
        args.append(operation_type.strip().lower())
        clauses.append(f"t.operation_type = ${len(args)}::varchar")
    where = " AND ".join(clauses)
    total = int(
        await pool.fetchval(
            f"SELECT COUNT(*) FROM video_export_telemetry t WHERE {where}",
            *args,
        )
        or 0
    )
    args.extend([limit, offset])
    rows = await pool.fetch(
        f"""
        SELECT t.*, u.email AS user_email
        FROM video_export_telemetry t
        LEFT JOIN users u ON u.id = t.user_id
        WHERE {where}
        ORDER BY t.created_at DESC
        LIMIT ${len(args) - 1} OFFSET ${len(args)}
        """,
        *args,
    )
    items = [
        ExportTelemetryEntry(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            user_email=str(row["user_email"] or ""),
            operation_type=str(row["operation_type"] or ""),
            ref_id=row["ref_id"],
            track_count=int(row["track_count"] or 0),
            completed_count=int(row["completed_count"] or 0),
            duration_ms=int(row["duration_ms"]) if row["duration_ms"] is not None else None,
            codec=row["codec"],
            resolution=row["resolution"],
            fps=int(row["fps"]) if row["fps"] is not None else None,
            export_tier=row["export_tier"],
            speed_mode=row["speed_mode"],
            hw_cpu=row["hw_cpu"],
            hw_gpu=row["hw_gpu"],
            hw_encoder=row["hw_encoder"],
            app_version=row["app_version"],
            created_at=row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else row["created_at"],
        )
        for row in rows
    ]
    return ExportTelemetryListResponse(items=items, total=total)


@router.get(
    "/usage",
    response_model=UsageListResponse,
    summary="List credit usage transactions across all users",
)
async def get_usage(
    ctx: AdminDep,
    credit_repo: CreditRepoDep,
    user_id: str | None = Query(default=None, description="Filter by user UUID"),
    provider: str | None = Query(default=None, description="Filter by provider"),
    operation: str | None = Query(default=None, description="Filter by operation type"),
    direction: str | None = Query(default=None, description="debit, credit, or refund"),
    reason: str | None = Query(default=None, description="Filter by reason substring"),
    from_date: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    to_date: datetime | None = Query(default=None, description="Filter to date (ISO 8601)"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Entries per page (max 200)"),
) -> UsageListResponse:
    """Return paginated credit usage with user, provider, model, and purpose details."""
    del ctx
    from uuid import UUID

    parsed_user_id = UUID(user_id) if user_id else None
    rows, total, summary_raw = await credit_repo.list_admin_usage(
        page=page,
        page_size=page_size,
        user_id=parsed_user_id,
        provider=provider,
        operation=operation,
        direction=direction,
        reason=reason,
        from_date=from_date,
        to_date=to_date,
    )

    debit_units = int(summary_raw.get("debit_units") or 0)
    refund_units = int(summary_raw.get("refund_units") or 0)
    wallet_charged_units = int(summary_raw.get("wallet_charged_units") or 0)
    plan_included_list_units = int(summary_raw.get("plan_included_list_units") or 0)
    by_operation_raw = summary_raw.get("by_operation") or []
    by_operation: list[dict[str, Any]] = []
    for row in by_operation_raw:
        if not isinstance(row, dict):
            continue
        by_operation.append(
            {
                "operation": str(row.get("operation") or "unknown"),
                "provider": str(row.get("provider") or ""),
                "model": str(row.get("model") or ""),
                "events": int(row.get("events") or 0),
                "wallet_charged": units_to_credits(int(row.get("wallet_charged_units") or 0)),
                "plan_included_list": units_to_credits(
                    int(row.get("plan_included_list_units") or 0)
                ),
            }
        )

    # Subscription cash uses date/user filters only (not ledger op/provider filters).
    sub_cash = await credit_repo.sum_fulfilled_subscription_revenue(
        user_id=parsed_user_id,
        from_date=from_date,
        to_date=to_date,
    )

    summary = UsageSummaryResponse(
        billable_events=int(summary_raw.get("billable_events") or 0),
        credit_cost=units_to_credits(debit_units),
        refund_total=units_to_credits(refund_units),
        refund_events=int(summary_raw.get("refund_events") or 0),
        net_credit_cost=units_to_credits(max(debit_units - refund_units, 0)),
        wallet_charged=units_to_credits(wallet_charged_units),
        plan_included_list=units_to_credits(plan_included_list_units),
        plan_allowance_events=int(summary_raw.get("plan_allowance_events") or 0),
        plan_draft_list=units_to_credits(
            int(summary_raw.get("plan_draft_list_units") or 0)
        ),
        plan_song_list=units_to_credits(
            int(summary_raw.get("plan_song_list_units") or 0)
        ),
        plan_image_list=units_to_credits(
            int(summary_raw.get("plan_image_list_units") or 0)
        ),
        platform_absorb_events=int(summary_raw.get("platform_absorb_events") or 0),
        platform_absorb_list=units_to_credits(
            int(summary_raw.get("platform_absorb_list_units") or 0)
        ),
        subscription_revenue_cents=int(
            sub_cash.get("subscription_revenue_cents") or 0
        ),
        subscription_payment_count=int(
            sub_cash.get("subscription_payment_count") or 0
        ),
        credit_pack_revenue_cents=int(
            sub_cash.get("credit_pack_revenue_cents") or 0
        ),
        grant_issued=units_to_credits(int(summary_raw.get("grant_issued_units") or 0)),
        grant_issued_events=int(summary_raw.get("grant_issued_events") or 0),
        credit_pack_payment_count=int(
            sub_cash.get("credit_pack_payment_count") or 0
        ),
        by_operation=by_operation,
    )
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1

    return UsageListResponse(
        items=[_usage_entry_to_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        summary=summary,
    )


@router.get(
    "/user-spend",
    response_model=UserSpendListResponse,
    summary="Per-user estimated COGS spend with plan-allowance alerts",
)
async def get_user_spend(
    ctx: AdminDep,
    user_spend_service: UserSpendServiceDep,
    from_date: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    to_date: datetime | None = Query(default=None, description="Filter to date (ISO 8601)"),
    q: str | None = Query(default=None, description="Search email or user UUID"),
    plan_id: str | None = Query(default=None, description="Filter by active plan UUID"),
    provider: str | None = Query(default=None, description="Filter by provider"),
    operation: str | None = Query(default=None, description="Filter by operation type"),
    alert: str = Query(
        default="all",
        description="all | over_allowance | margin_risk | healthy",
    ),
    sort: str = Query(
        default="cogs_desc",
        description="cogs_desc | wallet_desc | overage_first",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> UserSpendListResponse:
    """Roster of users with est. USD COGS, wallet spend, meters, and alerts."""
    del ctx
    parsed_plan_id = UUID(plan_id) if plan_id else None
    result = await user_spend_service.list_user_spend(
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
        q=q,
        plan_id=parsed_plan_id,
        provider=provider,
        operation=operation,
        alert=alert,
        sort=sort,
    )

    items: list[UserSpendItemResponse] = []
    for row in result.items:
        meters = {
            key: UserSpendMeterResponse(
                used=m.used,
                limit=m.limit,
                pct=m.pct,
                hot=m.hot,
            )
            for key, m in row.meters.items()
        }
        items.append(
            UserSpendItemResponse(
                user_id=str(row.user_id),
                email=row.email,
                display_name=row.display_name,
                plan_id=str(row.plan_id) if row.plan_id else None,
                plan_name=row.plan_name,
                plan_price_cents=row.plan_price_cents,
                billing_cycle_days=row.billing_cycle_days,
                plan_revenue_usd=row.plan_revenue_usd,
                est_cogs_usd=row.est_cogs_usd,
                wallet_charged_usd=row.wallet_charged_usd,
                plan_included_usd=row.plan_included_usd,
                soft_overage_events=row.soft_overage_events,
                meters=meters,
                alerts=UserSpendAlertsResponse(
                    over_allowance=row.over_allowance,
                    margin_risk=row.margin_risk,
                    meters_hot=list(row.meters_hot),
                ),
                by_cog=[
                    UserSpendCogResponse(
                        provider=c.provider,
                        operation=c.operation,
                        model=c.model,
                        events=c.events,
                        plan_included_usd=c.plan_included_usd,
                        wallet_usd=c.wallet_usd,
                        est_cogs_usd=c.est_cogs_usd,
                        coverage=c.coverage,
                    )
                    for c in row.by_cog
                ],
            )
        )

    total_pages = max(1, (result.total + page_size - 1) // page_size) if result.total else 1
    summary_raw = result.summary
    return UserSpendListResponse(
        items=items,
        total=result.total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        summary=UserSpendSummaryResponse(
            users_over_allowance=int(summary_raw.get("users_over_allowance") or 0),
            users_margin_risk=int(summary_raw.get("users_margin_risk") or 0),
            total_est_cogs_usd=float(summary_raw.get("total_est_cogs_usd") or 0),
            total_wallet_usd=float(summary_raw.get("total_wallet_usd") or 0),
            gcv=float(summary_raw.get("gcv") or 0.01),
        ),
    )


@router.get(
    "/pipeline/stuck",
    response_model=AdminStuckBatchesResponse,
    summary="List batches with no pipeline activity past the stuck threshold",
)
async def get_admin_stuck_batches(
    ctx: AdminDep,
    batch_repo: BatchRepoDep,
    min_age_seconds: int | None = Query(
        default=None,
        ge=60,
        description="Override the configured stuck-batch age threshold, in seconds.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> AdminStuckBatchesResponse:
    """On-demand view of the same detection the stuck-batch housekeeping scan uses.

    Complements the scheduled `admin:pipeline_stuck_alert` push (which only fires
    once per batch per cooldown window) with a live, pollable list — useful for an
    admin dashboard widget, or for checking "what's stuck right now" without
    waiting for the next scan cycle or alert.
    """
    del ctx
    threshold = min_age_seconds if min_age_seconds is not None else get_settings().pipeline_stuck_threshold_seconds
    rows = await batch_repo.list_stuck_batches(min_age_seconds=threshold, limit=limit)
    return AdminStuckBatchesResponse(
        items=[
            AdminStuckBatchItem(
                batch_id=str(row["batch_id"]),
                user_id=str(row["user_id"]) if row.get("user_id") else None,
                user_email=row.get("user_email"),
                status=str(row.get("status") or ""),
                last_activity_at=row["last_activity_at"].isoformat() if row.get("last_activity_at") else None,
                age_seconds=int(row.get("age_seconds") or 0),
            )
            for row in rows
        ],
        threshold_seconds=threshold,
    )


@router.get(
    "/batches/{batch_id}",
    response_model=AdminBatchSummaryResponse,
    summary="Get batch summary for admin usage tracing",
)
async def get_admin_batch_summary(
    batch_id: str,
    ctx: AdminDep,
    batch_repo: BatchRepoDep,
) -> AdminBatchSummaryResponse:
    """Return batch and per-song status for tracing credit usage."""
    del ctx
    from uuid import UUID

    from platform_api.dependencies import get_user_repo

    try:
        parsed_batch_id = UUID(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid batch ID.") from exc

    batch = await batch_repo.get_batch_by_id(parsed_batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found.")

    user = await get_user_repo().get_by_id(batch.user_id)
    songs = await batch_repo.get_songs_by_batch(parsed_batch_id)

    return AdminBatchSummaryResponse(
        id=str(batch.id),
        user_id=str(batch.user_id),
        user_email=str(user.email if user else ""),
        user_display_name=str(user.display_name if user else ""),
        status=batch.status,
        song_count=batch.song_count,
        language=batch.language,
        created_at=batch.created_at.isoformat() if batch.created_at else None,
        updated_at=batch.updated_at.isoformat() if batch.updated_at else None,
        songs=[
            AdminBatchSongSummary(
                id=str(song.id),
                batch_index=song.batch_index,
                title=song.title,
                album=song.album,
                status=song.status,
            )
            for song in songs
        ],
    )


@router.get(
    "/songs/{song_id}",
    response_model=AdminSongSummaryResponse,
    summary="Get song summary for admin usage tracing",
)
async def get_admin_song_summary(
    song_id: str,
    ctx: AdminDep,
    batch_repo: BatchRepoDep,
) -> AdminSongSummaryResponse:
    """Return song details for tracing a draft charge."""
    del ctx
    from uuid import UUID

    from platform_api.dependencies import get_user_repo

    try:
        parsed_song_id = UUID(song_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid song ID.") from exc

    song = await batch_repo.get_song_by_id(parsed_song_id)
    if song is None:
        raise HTTPException(status_code=404, detail="Song not found.")

    user = await get_user_repo().get_by_id(song.user_id)

    return AdminSongSummaryResponse(
        id=str(song.id),
        batch_id=str(song.batch_id),
        batch_index=song.batch_index,
        user_id=str(song.user_id),
        user_email=str(user.email if user else ""),
        user_display_name=str(user.display_name if user else ""),
        title=song.title,
        album=song.album,
        status=song.status,
        created_at=song.created_at.isoformat() if song.created_at else None,
        updated_at=song.updated_at.isoformat() if song.updated_at else None,
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


@router.get(
    "/rate-limits/slai-image-provider",
    response_model=SlaiImageProviderConfigResponse,
    summary="Get SLAI image provider throttling configuration",
)
async def get_slai_image_provider_config(
    ctx: AdminDep,
    settings_repo: SettingsRepoDep,
) -> SlaiImageProviderConfigResponse:
    """Return admin-managed SLAI image rate limit and retry settings."""
    from platform_api.services.slai_image_config_service import load_slai_image_provider_config

    config = await load_slai_image_provider_config(settings_repo)
    return SlaiImageProviderConfigResponse(**config.to_dict())


@router.put(
    "/rate-limits/slai-image-provider",
    response_model=SlaiImageProviderConfigResponse,
    summary="Update SLAI image provider throttling configuration",
)
async def update_slai_image_provider_config(
    request: SlaiImageProviderConfigResponse,
    ctx: AdminDep,
    settings_repo: SettingsRepoDep,
) -> SlaiImageProviderConfigResponse:
    """Persist SLAI image throttling settings and apply them immediately."""
    from platform_api.services.slai_image_config_service import save_slai_image_provider_config

    config = await save_slai_image_provider_config(
        settings_repo,
        request.model_dump(exclude={"updated_at"}),
    )
    return SlaiImageProviderConfigResponse(**config.to_dict())


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


class CutluyBillingConfigResponse(BaseModel):
    """Admin view of CutLuy credentials without exposing the full secret."""

    api_base_url: str
    payment_link_id: str = ""
    secret_key_configured: bool = False
    secret_key_masked: str = ""
    secret_source: str | None = None
    webhook_secret_configured: bool = False
    webhook_secret_masked: str = ""
    webhook_secret_source: str | None = None


class ChmabaBillingConfigResponse(BaseModel):
    """Admin view of ChmabaPay credentials without exposing the live key."""

    api_base_url: str
    store_id: str = ""
    api_key_configured: bool = False
    api_key_masked: str = ""
    api_key_source: str | None = None
    store_source: str | None = None
    webhook_secret_configured: bool = False
    webhook_secret_masked: str = ""
    webhook_secret_source: str | None = None
    ready: bool = False


class UpdateChmabaBillingConfigRequest(BaseModel):
    """Update ChmabaPay credentials stored in system_settings."""

    api_base_url: str = Field(default="https://pay.chmaba.com", min_length=8, max_length=255)
    store_id: str = Field(default="", max_length=255)
    api_key: str | None = Field(
        default=None,
        max_length=4096,
        description="ChmabaPay live key (ck_live_…). Leave blank to keep the current key.",
    )
    webhook_secret: str | None = Field(
        default=None,
        max_length=4096,
        description="ChmabaPay webhook signing secret (whsec_…). Leave blank to keep.",
    )


class UpdateCutluyBillingConfigRequest(BaseModel):
    """Update CutLuy billing credentials stored in system_settings."""

    api_base_url: str = Field(default="https://cutluy.com", min_length=8, max_length=255)
    payment_link_id: str = Field(default="", max_length=255)
    secret_key: str | None = Field(
        default=None,
        max_length=4096,
        description="Leave blank to keep the current secret.",
    )
    webhook_secret: str | None = Field(
        default=None,
        max_length=4096,
        description="CutLuy Dashboard → Webhooks signing secret. Leave blank to keep.",
    )


async def _upsert_system_setting_value(
    pool: Any,
    *,
    key: str,
    value: str,
    value_type: str = "string",
) -> None:
    await pool.execute(
        """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        key,
        value,
        value_type,
    )


def _mask_system_setting_value(key: str, value: str) -> str:
    if key in {
        CUTLUY_SECRET_KEY_SETTING,
        CUTLUY_WEBHOOK_SECRET_KEY,
        CHMABA_API_KEY_SETTING,
        CHMABA_WEBHOOK_SECRET_KEY,
    }:
        return mask_secret_value(value)
    return value


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
            value=_mask_system_setting_value(row["key"], str(row["value"] or "")),
            value_type=row["value_type"],
            updated_at=row["updated_at"].isoformat() + "Z" if row["updated_at"] else None,
        )
        for row in rows
    ]
    return SystemSettingsResponse(settings=settings)


@router.get(
    "/job-queue/metrics",
    summary="Job queue + /progress latency metrics (Admin)",
)
async def get_job_queue_metrics(ctx: AdminDep) -> dict[str, Any]:
    """Basic ops snapshot: queue depth, busy workers, /progress p95, threshold alerts."""
    _ = ctx
    from platform_api.dependencies import get_job_queue_repo
    from platform_api.services.request_latency import latency_summary

    queue_metrics = await get_job_queue_repo().get_metrics()
    progress = latency_summary("/progress")
    alerts: list[str] = []
    queued_depth = int(queue_metrics.get("queued_depth") or 0)
    running = int(queue_metrics.get("running") or 0)
    oldest = queue_metrics.get("oldest_claimable") or {}
    oldest_age = float(oldest.get("age_seconds") or 0.0) if isinstance(oldest, dict) else 0.0
    progress_p95 = progress.get("p95_ms")
    if queued_depth >= 50:
        alerts.append("queue_depth_high")
    if oldest_age >= 300:
        alerts.append("oldest_job_stale")
    if running == 0 and queued_depth > 0:
        alerts.append("worker_idle_with_backlog")
    if progress_p95 is not None and float(progress_p95) >= 5000:
        alerts.append("progress_p95_high")
    return {
        "queue": queue_metrics,
        "progress_latency": progress,
        "alerts": alerts,
        "note": (
            "progress_latency is per-uvicorn-worker in-memory samples; "
            "aggregate across workers separately if needed."
        ),
    }


@router.get(
    "/job-queue/jobs",
    summary="List durable job_queue rows for ops board (Admin)",
)
async def list_job_queue_jobs(
    ctx: AdminDep,
    status: str | None = Query(
        default=None,
        description="Filter: queued | delayed | running | failed",
    ),
    job_type: str | None = Query(default=None, description="Exact job_type filter"),
    user: str | None = Query(default=None, description="User email substring"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Filterable job rows with user email, worker lock, and last_error."""
    _ = ctx
    from platform_api.dependencies import get_job_queue_repo
    from platform_api.exceptions import ValidationError

    try:
        jobs = await get_job_queue_repo().list_admin_jobs(
            status=status,
            job_type=job_type,
            user=user,
            limit=limit,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return {"jobs": jobs, "count": len(jobs)}


@router.get(
    "/job-queue/image-failures",
    summary="Recent image_jobs failures (Admin)",
)
async def list_recent_image_job_failures(
    ctx: AdminDep,
    hours: int = Query(default=24, ge=1, le=168, description="Lookback window hours"),
    limit: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    """Surface provider/image failures that may not appear as job_queue.failed."""
    _ = ctx
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    rows = await pool.fetch(
        """
        SELECT j.id, j.user_id, u.email AS user_email, j.batch_id, j.song_id,
               j.kind, j.channel_role, j.provider, j.status, j.attempt_count,
               j.error, j.updated_at,
               EXTRACT(EPOCH FROM (NOW() - j.updated_at))::float AS age_seconds
        FROM image_jobs j
        JOIN users u ON u.id = j.user_id
        WHERE j.status = 'failed'
          AND j.updated_at > NOW() - make_interval(hours => $1)
        ORDER BY j.updated_at DESC
        LIMIT $2
        """,
        int(hours),
        int(limit),
    )
    failures: list[dict[str, Any]] = []
    for row in rows:
        err = str(row["error"] or "")
        if len(err) > 300:
            err = err[:297] + "..."
        failures.append(
            {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "user_email": str(row["user_email"] or ""),
                "batch_id": str(row["batch_id"]) if row["batch_id"] else None,
                "song_id": str(row["song_id"]) if row["song_id"] else None,
                "kind": str(row["kind"] or ""),
                "channel_role": str(row["channel_role"] or ""),
                "provider": row["provider"],
                "status": str(row["status"]),
                "attempt_count": int(row["attempt_count"] or 0),
                "error": err or None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "age_seconds": round(float(row["age_seconds"] or 0.0), 1),
            }
        )
    return {"failures": failures, "count": len(failures), "hours": int(hours)}


@router.get(
    "/billing/cutluy-config",
    response_model=CutluyBillingConfigResponse,
    summary="Get CutLuy billing credentials (Admin)",
)
async def get_cutluy_billing_config(ctx: AdminDep) -> CutluyBillingConfigResponse:
    """Return CutLuy API settings for the admin payment tab without exposing the full secret."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    cutluy = await resolve_cutluy_config(pool)
    return CutluyBillingConfigResponse(
        api_base_url=cutluy.api_base_url,
        payment_link_id=cutluy.payment_link_id or "",
        secret_key_configured=bool(cutluy.secret_key),
        secret_key_masked=mask_secret_value(cutluy.secret_key),
        secret_source=cutluy.secret_source if cutluy.secret_key else None,
        webhook_secret_configured=bool(cutluy.webhook_secret),
        webhook_secret_masked=mask_secret_value(cutluy.webhook_secret),
        webhook_secret_source=cutluy.webhook_secret_source if cutluy.webhook_secret else None,
    )


@router.put(
    "/billing/cutluy-config",
    response_model=CutluyBillingConfigResponse,
    summary="Update CutLuy billing credentials (Admin)",
)
async def update_cutluy_billing_config(
    request: UpdateCutluyBillingConfigRequest,
    ctx: AdminDep,
) -> CutluyBillingConfigResponse:
    """Store CutLuy credentials in system_settings (no .env edit required)."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    api_base_url = request.api_base_url.strip().rstrip("/") or "https://cutluy.com"
    payment_link_id = normalize_cutluy_payment_link_id(request.payment_link_id.strip()) or ""

    await _upsert_system_setting_value(
        pool,
        key=CUTLUY_API_BASE_URL_KEY,
        value=api_base_url,
    )
    await _upsert_system_setting_value(
        pool,
        key=CUTLUY_PAYMENT_LINK_ID_KEY,
        value=payment_link_id,
    )

    secret_input = (request.secret_key or "").strip()
    if secret_input:
        await _upsert_system_setting_value(
            pool,
            key=CUTLUY_SECRET_KEY_SETTING,
            value=secret_input,
        )

    webhook_input = (request.webhook_secret or "").strip()
    if webhook_input:
        await _upsert_system_setting_value(
            pool,
            key=CUTLUY_WEBHOOK_SECRET_KEY,
            value=webhook_input,
        )

    cutluy = await resolve_cutluy_config(pool)
    return CutluyBillingConfigResponse(
        api_base_url=cutluy.api_base_url,
        payment_link_id=cutluy.payment_link_id or "",
        secret_key_configured=bool(cutluy.secret_key),
        secret_key_masked=mask_secret_value(cutluy.secret_key),
        secret_source=cutluy.secret_source if cutluy.secret_key else None,
        webhook_secret_configured=bool(cutluy.webhook_secret),
        webhook_secret_masked=mask_secret_value(cutluy.webhook_secret),
        webhook_secret_source=cutluy.webhook_secret_source if cutluy.webhook_secret else None,
    )


def _chmaba_response(config) -> ChmabaBillingConfigResponse:
    """Build the masked admin view for ChmabaPay credentials."""
    return ChmabaBillingConfigResponse(
        api_base_url=config.api_base_url,
        store_id=config.store_id,
        api_key_configured=bool(config.api_key),
        api_key_masked=mask_secret_value(config.api_key),
        api_key_source=config.api_key_source if config.api_key else None,
        store_source=config.store_source if config.store_id else None,
        webhook_secret_configured=bool(config.webhook_secret),
        webhook_secret_masked=mask_secret_value(config.webhook_secret),
        webhook_secret_source=(
            config.webhook_secret_source if config.webhook_secret else None
        ),
        ready=config.configured,
    )


@router.get(
    "/billing/chmaba-config",
    response_model=ChmabaBillingConfigResponse,
    summary="Get ChmabaPay billing credentials (Admin)",
)
async def get_chmaba_billing_config(ctx: AdminDep) -> ChmabaBillingConfigResponse:
    """Return ChmabaPay settings for the admin payment tab without the live key."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    return _chmaba_response(await resolve_chmaba_config(pool))


@router.put(
    "/billing/chmaba-config",
    response_model=ChmabaBillingConfigResponse,
    summary="Update ChmabaPay billing credentials (Admin)",
)
async def update_chmaba_billing_config(
    request: UpdateChmabaBillingConfigRequest,
    ctx: AdminDep,
) -> ChmabaBillingConfigResponse:
    """Store ChmabaPay credentials in system_settings (no .env edit required)."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    api_base_url = (
        request.api_base_url.strip().rstrip("/") or "https://pay.chmaba.com"
    )
    store_id = request.store_id.strip()

    await _upsert_system_setting_value(
        pool,
        key=CHMABA_API_BASE_URL_KEY,
        value=api_base_url,
    )
    await _upsert_system_setting_value(
        pool,
        key=CHMABA_STORE_ID_KEY,
        value=store_id,
    )

    api_key_input = (request.api_key or "").strip()
    if api_key_input:
        await _upsert_system_setting_value(
            pool,
            key=CHMABA_API_KEY_SETTING,
            value=api_key_input,
        )

    webhook_input = (request.webhook_secret or "").strip()
    if webhook_input:
        await _upsert_system_setting_value(
            pool,
            key=CHMABA_WEBHOOK_SECRET_KEY,
            value=webhook_input,
        )

    return _chmaba_response(await resolve_chmaba_config(pool))


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

    if request.key == CUTLUY_SECRET_KEY_SETTING:
        incoming = request.value.strip()
        masked = mask_secret_value(incoming)
        if not incoming or incoming == masked or "••••" in incoming:
            raise HTTPException(
                status_code=400,
                detail="Use Admin Settings → Payment → CutLuy to update the API secret.",
            )
    if request.key in {CHMABA_API_KEY_SETTING, CHMABA_WEBHOOK_SECRET_KEY}:
        incoming = request.value.strip()
        masked = mask_secret_value(incoming)
        if not incoming or incoming == masked or "••••" in incoming:
            raise HTTPException(
                status_code=400,
                detail="Use Admin Settings → Payment → ChmabaPay to update this secret.",
            )

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
        value=_mask_system_setting_value(row["key"], str(row["value"] or "")),
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


@router.get(
    "/youtube-oauth-apps",
    response_model=YouTubeOAuthAppsResponse,
    summary="Get all admin-managed YouTube OAuth apps",
)
async def list_youtube_oauth_apps(
    ctx: AdminDep,
    repo: YouTubeOAuthAppRepoDep,
) -> YouTubeOAuthAppsResponse:
    """Return all admin-managed YouTube OAuth apps without exposing secrets."""
    apps = await repo.list_all()
    return YouTubeOAuthAppsResponse(
        apps=[_to_youtube_oauth_app_entry(app) for app in apps]
    )


@router.post(
    "/youtube-oauth-apps",
    response_model=YouTubeOAuthAppEntry,
    summary="Create a YouTube OAuth app",
)
async def create_youtube_oauth_app(
    request: CreateYouTubeOAuthAppRequest,
    ctx: AdminDep,
    repo: YouTubeOAuthAppRepoDep,
    encryption: YouTubeOAuthEncryptionDep,
) -> YouTubeOAuthAppEntry:
    """Create a new admin-managed YouTube OAuth app with encrypted secret storage."""
    if encryption is None:
        raise HTTPException(
            status_code=503,
            detail="YouTube OAuth storage unavailable. Set PLATFORM_ENCRYPTION_MASTER_KEY first.",
        )
    record = await repo.create(
        name=request.name.strip(),
        client_id=request.client_id.strip(),
        encrypted_client_secret=encryption.encrypt(request.client_secret.strip()),
        is_default=request.is_default,
    )
    if record is None:
        raise HTTPException(status_code=500, detail="Unable to create YouTube OAuth app.")
    return _to_youtube_oauth_app_entry(record)


@router.patch(
    "/youtube-oauth-apps/{app_id}",
    response_model=YouTubeOAuthAppEntry,
    summary="Update a YouTube OAuth app",
)
async def update_youtube_oauth_app(
    app_id: str,
    request: UpdateYouTubeOAuthAppRequest,
    ctx: AdminDep,
    repo: YouTubeOAuthAppRepoDep,
    encryption: YouTubeOAuthEncryptionDep,
) -> YouTubeOAuthAppEntry:
    """Update YouTube OAuth app metadata and optionally replace the secret."""
    encrypted_client_secret = None
    if request.client_secret is not None:
        if encryption is None:
            raise HTTPException(
                status_code=503,
                detail="YouTube OAuth storage unavailable. Set PLATFORM_ENCRYPTION_MASTER_KEY first.",
            )
        encrypted_client_secret = encryption.encrypt(request.client_secret.strip())

    record = await repo.update(
        app_id,
        name=request.name.strip() if request.name is not None else None,
        client_id=request.client_id.strip() if request.client_id is not None else None,
        encrypted_client_secret=encrypted_client_secret,
        is_default=request.is_default,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="YouTube OAuth app not found.")
    return _to_youtube_oauth_app_entry(record)


@router.delete(
    "/youtube-oauth-apps/{app_id}",
    status_code=200,
    summary="Delete a YouTube OAuth app",
)
async def delete_youtube_oauth_app(
    app_id: str,
    ctx: AdminDep,
    repo: YouTubeOAuthAppRepoDep,
) -> dict[str, str]:
    """Delete an admin-managed YouTube OAuth app."""
    deleted = await repo.delete(app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="YouTube OAuth app not found.")
    return {"message": "YouTube OAuth app deleted."}


# ---------------------------------------------------------------------------
# Admin Overview (Dashboard Stats)
# ---------------------------------------------------------------------------


class AdminOverviewResponse(BaseModel):
    """Aggregated counts for the admin dashboard."""
    total_users: int = 0
    total_admins: int = 0
    active_users: int = 0
    suspended_users: int = 0
    deleted_users: int = 0
    new_users_7d: int = 0
    new_users_30d: int = 0
    users_with_profiles: int = 0
    users_with_active_license: int = 0
    active_licenses: int = 0
    total_songs: int = 0
    total_images: int = 0


@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Get admin dashboard overview stats",
)
async def get_admin_overview(ctx: AdminDep) -> AdminOverviewResponse:
    """Return aggregated platform counts for the admin dashboard."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()

    overview_row = await pool.fetchrow(
        """
        SELECT
            COUNT(*)::bigint AS total_users,
            COUNT(*) FILTER (WHERE role = 'admin')::bigint AS total_admins,
            COUNT(*) FILTER (WHERE status = 'active')::bigint AS active_users,
            COUNT(*) FILTER (WHERE status = 'suspended')::bigint AS suspended_users,
            COUNT(*) FILTER (WHERE status = 'deleted' OR deleted_at IS NOT NULL)::bigint AS deleted_users,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')::bigint AS new_users_7d,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days')::bigint AS new_users_30d
        FROM users
        """
    ) or {}

    users_with_profiles = await pool.fetchval(
        """
        SELECT COUNT(DISTINCT user_id)
        FROM channel_profiles
        """
    ) or 0
    users_with_active_license = await pool.fetchval(
        """
        SELECT COUNT(DISTINCT user_id)
        FROM licenses
        WHERE status = 'active' AND user_id IS NOT NULL
        """
    ) or 0
    active_licenses = await pool.fetchval(
        "SELECT COUNT(*) FROM licenses WHERE status = 'active'"
    ) or 0
    total_songs = await pool.fetchval("SELECT COUNT(*) FROM songs") or 0
    total_images = await pool.fetchval("SELECT COUNT(*) FROM image_jobs") or 0

    return AdminOverviewResponse(
        total_users=int(overview_row.get("total_users", 0) or 0),
        total_admins=int(overview_row.get("total_admins", 0) or 0),
        active_users=int(overview_row.get("active_users", 0) or 0),
        suspended_users=int(overview_row.get("suspended_users", 0) or 0),
        deleted_users=int(overview_row.get("deleted_users", 0) or 0),
        new_users_7d=int(overview_row.get("new_users_7d", 0) or 0),
        new_users_30d=int(overview_row.get("new_users_30d", 0) or 0),
        users_with_profiles=int(users_with_profiles),
        users_with_active_license=int(users_with_active_license),
        active_licenses=int(active_licenses),
        total_songs=int(total_songs),
        total_images=int(total_images),
    )


# ---------------------------------------------------------------------------
# User Data Reset / Backup / Restore
# ---------------------------------------------------------------------------


@router.post(
    "/user-data/reset",
    response_model=ResetResponse,
    summary="Reset all user data (destructive, requires password)",
)
async def reset_user_data(
    request: ResetRequest,
    ctx: AdminDep,
    reset_service: ResetServiceDep,
) -> ResetResponse | JSONResponse:
    """Wipe all user data after password re-verification.

    Creates a backup before deletion. Returns HTTP 207 if Redis flush fails
    after a successful DB commit (partial success).

    Requirements: 1.1, 1.2, 1.3, 5.1, 7.1, 7.2, 7.3, 7.4
    """
    from platform_api.dependencies import get_db_pool, get_redis
    from platform_api.services.admin_password import verify_admin_password

    admin_id = str(ctx.user_id)

    # Verify admin password (raises AuthenticationError or RateLimitExceededError)
    await verify_admin_password(
        admin_id=admin_id,
        password=request.password,
        pool=get_db_pool(),
        redis=get_redis(),
    )

    # Execute the reset operation
    result = await reset_service.execute_reset(admin_id)

    # Determine status and HTTP code
    status = "success" if result.redis_flushed else "partial"
    response_data = ResetResponse(
        status=status,
        backup_filename=result.backup_filename,
        tables_cleared=result.tables_cleared,
        record_counts=result.record_counts,
        total_records_deleted=result.total_records_deleted,
        redis_flushed=result.redis_flushed,
        redis_error=result.redis_error,
    )

    if not result.redis_flushed:
        # HTTP 207 Multi-Status for partial success
        return JSONResponse(
            status_code=207,
            content=response_data.model_dump(),
        )

    return response_data


@router.get(
    "/user-data/backups",
    response_model=BackupListResponse,
    summary="List available user data backups",
)
async def list_user_data_backups(
    ctx: AdminDep,
    reset_service: ResetServiceDep,
) -> BackupListResponse:
    """Return available backup files sorted newest-first, max 100.

    Requirements: 4.1, 7.1, 7.2, 7.3, 7.4
    """
    backups = await reset_service.list_backups()

    return BackupListResponse(
        backups=[
            BackupMetadataResponse(
                filename=b.filename,
                created_at=b.created_at.isoformat(),
                file_size_bytes=b.file_size_bytes,
                total_records=b.total_records,
                tables=b.tables,
                actor_id=b.actor_id,
            )
            for b in backups
        ]
    )


@router.post(
    "/user-data/restore",
    response_model=RestoreResponse,
    summary="Restore user data from a backup (requires password)",
)
async def restore_user_data(
    request: RestoreRequest,
    ctx: AdminDep,
    reset_service: ResetServiceDep,
) -> RestoreResponse:
    """Restore user data from a backup file after password re-verification.

    Inserts records with ON CONFLICT DO NOTHING semantics (skips existing PKs).

    Requirements: 1.1, 1.2, 1.3, 5.1, 5.3, 7.1, 7.2, 7.3, 7.4
    """
    from platform_api.dependencies import get_db_pool, get_redis
    from platform_api.services.admin_password import verify_admin_password

    admin_id = str(ctx.user_id)

    # Verify admin password (raises AuthenticationError or RateLimitExceededError)
    await verify_admin_password(
        admin_id=admin_id,
        password=request.password,
        pool=get_db_pool(),
        redis=get_redis(),
    )

    # Execute the restore operation
    try:
        result = await reset_service.execute_restore(
            request.backup_filename, admin_id
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Backup not found.")

    return RestoreResponse(
        status="success",
        backup_filename=result.backup_filename,
        records_restored=result.records_restored,
        records_skipped=result.records_skipped,
    )


# ---------------------------------------------------------------------------
# Desktop notifications & software updates
# ---------------------------------------------------------------------------


class SoftwareUpdateConfigResponse(BaseModel):
    version: str
    download_url: str
    mandatory: bool
    release_notes: str
    published_at: str | None = None
    is_published: bool = False
    live_version: str = ""
    live_download_url: str = ""
    live_mandatory: bool = False
    live_release_notes: str = ""
    live_published_at: str | None = None


class PublishSoftwareUpdateRequest(BaseModel):
    notify_desktop_users: bool = True
    create_changelog: bool = False


class PublishSoftwareUpdateResponse(BaseModel):
    recipients: int
    version: str
    published_at: str
    changelog_slug: str | None = None


class PublishInstallerRequest(BaseModel):
    version: str | None = Field(default=None, max_length=64)
    mandatory: bool | None = None
    release_notes: str | None = Field(default=None, max_length=4000)
    notify_desktop_users: bool = True
    create_changelog: bool = True


class UpdateSoftwareUpdateConfigRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=64)
    download_url: str = Field(default="", max_length=2048)
    mandatory: bool = False
    release_notes: str = Field(default="", max_length=4000)


class UnpublishSoftwareUpdateResponse(BaseModel):
    version: str
    is_published: bool = False
    unpublished_version: str = ""
    restored_live_version: str | None = None
    live_version: str = ""


class UploadDesktopSoftwareUpdateResponse(BaseModel):
    download_url: str
    filename: str
    size_bytes: int
    draft_saved: bool = True


class DesktopInstallerFileResponse(BaseModel):
    filename: str
    download_url: str
    size_bytes: int
    modified_at: str
    version: str | None = None
    download_count: int = 0


class DesktopInstallerListResponse(BaseModel):
    items: list[DesktopInstallerFileResponse]


class DeleteDesktopInstallerResponse(BaseModel):
    status: str
    filename: str
    unpublished_version: str = ""
    restored_live_version: str | None = None


class DraftInstallerResponse(SoftwareUpdateConfigResponse):
    unpublished_version: str = ""
    restored_live_version: str | None = None


class SendPushNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=2000)


class SendPushNotificationResponse(BaseModel):
    recipients: int
    title: str
    notification_id: str
    created_at: str


class PushNotificationHistoryEntry(BaseModel):
    id: str
    title: str
    message: str
    created_at: str
    recipients: int


class PushNotificationHistoryResponse(BaseModel):
    items: list[PushNotificationHistoryEntry]


def _software_update_config_response(config) -> SoftwareUpdateConfigResponse:
    live_version = str(getattr(config, "live_version", "") or "").strip()
    draft_is_live = bool((config.published_at or "").strip()) and bool(live_version)
    return SoftwareUpdateConfigResponse(
        version=config.version,
        download_url=config.download_url,
        mandatory=config.mandatory,
        release_notes=config.release_notes,
        published_at=config.published_at,
        is_published=draft_is_live,
        live_version=live_version,
        live_download_url=str(getattr(config, "live_download_url", "") or ""),
        live_mandatory=bool(getattr(config, "live_mandatory", False)),
        live_release_notes=str(getattr(config, "live_release_notes", "") or ""),
        live_published_at=getattr(config, "live_published_at", None),
    )


def _installer_candidates_from_service(service) -> list:
    from platform_api.services.desktop_notification_admin_service import InstallerCandidate
    from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

    items: list[InstallerCandidate] = []
    for record in service.list_installers():
        items.append(
            InstallerCandidate(
                version=extract_version_from_installer_filename(record.filename) or "",
                download_url=record.download_url,
                filename=record.filename,
            )
        )
    return items


@router.get(
    "/desktop/software-update",
    response_model=SoftwareUpdateConfigResponse,
    summary="Get desktop software update configuration (Admin)",
)
async def get_desktop_software_update_config(
    ctx: AdminDep, request: Request
) -> SoftwareUpdateConfigResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.services.desktop_notification_admin_service import get_software_update_config

    pool = get_db_pool()
    candidates = []
    try:
        service = await get_desktop_release_upload_service_resolved(pool, request)
        candidates = _installer_candidates_from_service(service)
    except Exception:
        candidates = []
    config = await get_software_update_config(pool, installer_candidates=candidates or None)
    return _software_update_config_response(config)


@router.put(
    "/desktop/software-update",
    response_model=SoftwareUpdateConfigResponse,
    summary="Save desktop software update configuration (Admin)",
)
async def update_desktop_software_update_config(
    request: UpdateSoftwareUpdateConfigRequest,
    ctx: AdminDep,
) -> SoftwareUpdateConfigResponse:
    from platform_api.dependencies import get_db_pool
    from platform_api.services.desktop_notification_admin_service import save_software_update_config

    config = await save_software_update_config(
        get_db_pool(),
        version=request.version.strip(),
        download_url=request.download_url.strip(),
        mandatory=request.mandatory,
        release_notes=request.release_notes.strip(),
    )
    return _software_update_config_response(config)


@router.post(
    "/desktop/software-update/upload",
    response_model=UploadDesktopSoftwareUpdateResponse,
    summary="Upload desktop installer package (Admin)",
)
async def upload_desktop_software_update(
    ctx: AdminDep,
    request: Request,
    file: UploadFile = File(...),
    version: str | None = Form(default=None),
) -> UploadDesktopSoftwareUpdateResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.exceptions import ValidationError
    from platform_api.services.desktop_notification_admin_service import apply_uploaded_installer_to_draft
    from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

    content = await file.read()
    pool = get_db_pool()
    service = await get_desktop_release_upload_service_resolved(pool, request)
    try:
        result = service.store_installer(
            content,
            original_filename=file.filename or "Camxora.zip",
            version=version,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    draft_version = str(version or "").strip() or extract_version_from_installer_filename(result.filename)
    await apply_uploaded_installer_to_draft(
        pool,
        download_url=result.download_url,
        version=draft_version or None,
    )

    return UploadDesktopSoftwareUpdateResponse(
        download_url=result.download_url,
        filename=result.filename,
        size_bytes=result.size_bytes,
        draft_saved=True,
    )


@router.get(
    "/desktop/software-update/installers",
    response_model=DesktopInstallerListResponse,
    summary="List uploaded desktop installer files (Admin)",
)
async def list_desktop_installers(ctx: AdminDep, request: Request) -> DesktopInstallerListResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.services.desktop_release_download_stats import get_download_counts
    from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

    pool = get_db_pool()
    service = await get_desktop_release_upload_service_resolved(pool, request)
    counts = await get_download_counts(pool)
    items = []
    for record in service.list_installers():
        version = extract_version_from_installer_filename(record.filename)
        items.append(
            DesktopInstallerFileResponse(
                filename=record.filename,
                download_url=record.download_url,
                size_bytes=record.size_bytes,
                modified_at=record.modified_at,
                version=version,
                download_count=int(counts.get(version or "", 0)) if version else 0,
            )
        )
    return DesktopInstallerListResponse(items=items)


@router.delete(
    "/desktop/software-update/installers/{filename}",
    response_model=DeleteDesktopInstallerResponse,
    summary="Delete an uploaded desktop installer file (Admin)",
)
async def delete_desktop_installer(
    ctx: AdminDep, filename: str, request: Request
) -> DeleteDesktopInstallerResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.exceptions import ValidationError
    from platform_api.services.desktop_notification_admin_service import sync_after_installer_delete
    from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

    pool = get_db_pool()
    service = await get_desktop_release_upload_service_resolved(pool, request)
    record = next((item for item in service.list_installers() if item.filename == filename), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Installer file not found.")
    remaining = [item for item in _installer_candidates_from_service(service) if item.filename != filename]
    try:
        service.delete_installer(filename)
    except ValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = await sync_after_installer_delete(
        pool,
        filename=filename,
        download_url=record.download_url,
        version=extract_version_from_installer_filename(filename) or "",
        installer_candidates=remaining,
    )
    return DeleteDesktopInstallerResponse(
        status="deleted",
        filename=filename,
        unpublished_version=result.unpublished_version,
        restored_live_version=result.restored_live_version,
    )


@router.post(
    "/desktop/software-update/publish",
    response_model=PublishSoftwareUpdateResponse,
    summary="Publish desktop software update (public download + optional notifications/changelog)",
)
async def publish_desktop_software_update(
    ctx: AdminDep,
    request: PublishSoftwareUpdateRequest | None = None,
) -> PublishSoftwareUpdateResponse:
    from platform_api.dependencies import get_db_pool
    from platform_api.services.desktop_notification_admin_service import publish_software_update

    body = request or PublishSoftwareUpdateRequest()
    try:
        config, recipients, changelog_slug = await publish_software_update(
            get_db_pool(),
            notify_desktop_users=body.notify_desktop_users,
            create_changelog=body.create_changelog,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PublishSoftwareUpdateResponse(
        recipients=recipients,
        version=config.version,
        published_at=config.published_at or datetime.utcnow().isoformat() + "Z",
        changelog_slug=changelog_slug,
    )


@router.post(
    "/desktop/software-update/unpublish",
    response_model=UnpublishSoftwareUpdateResponse,
    summary="Unpublish desktop release (restore previous live version)",
)
async def unpublish_desktop_software_update(
    ctx: AdminDep, request: Request
) -> UnpublishSoftwareUpdateResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.services.desktop_notification_admin_service import unpublish_software_update

    pool = get_db_pool()
    service = await get_desktop_release_upload_service_resolved(pool, request)
    result = await unpublish_software_update(
        pool,
        installer_candidates=_installer_candidates_from_service(service),
    )
    return UnpublishSoftwareUpdateResponse(
        version=result.draft.version,
        is_published=False,
        unpublished_version=result.unpublished_version,
        restored_live_version=result.restored_live_version,
        live_version=result.draft.live_version,
    )


@router.post(
    "/desktop/software-update/installers/{filename}/draft",
    response_model=DraftInstallerResponse,
    summary="Set an installer as the working draft; if it is live, restore the previous live release",
)
async def draft_desktop_installer(
    ctx: AdminDep,
    filename: str,
    http_request: Request,
) -> DraftInstallerResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.services.desktop_notification_admin_service import move_installer_to_draft
    from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

    pool = get_db_pool()
    service = await get_desktop_release_upload_service_resolved(pool, http_request)
    record = next((item for item in service.list_installers() if item.filename == filename), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Installer file not found.")

    result = await move_installer_to_draft(
        pool,
        version=extract_version_from_installer_filename(record.filename) or "",
        download_url=record.download_url,
        filename=record.filename,
        installer_candidates=_installer_candidates_from_service(service),
    )
    payload = _software_update_config_response(result.draft)
    return DraftInstallerResponse(
        **payload.model_dump(),
        unpublished_version=result.unpublished_version,
        restored_live_version=result.restored_live_version,
    )


@router.post(
    "/desktop/software-update/installers/{filename}/publish",
    response_model=PublishSoftwareUpdateResponse,
    summary="Select an installer file and publish it as the live desktop release",
)
async def publish_desktop_installer(
    ctx: AdminDep,
    filename: str,
    request: PublishInstallerRequest,
    http_request: Request,
) -> PublishSoftwareUpdateResponse:
    from platform_api.dependencies import get_db_pool, get_desktop_release_upload_service_resolved
    from platform_api.services.desktop_notification_admin_service import (
        get_software_update_config,
        publish_software_update,
        save_software_update_config,
    )
    from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

    pool = get_db_pool()
    service = await get_desktop_release_upload_service_resolved(pool, http_request)
    record = next((item for item in service.list_installers() if item.filename == filename), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Installer file not found.")

    # Version comes from the Software Update form / draft — not from the
    # installer filename. Filename parse is a last-resort convenience only
    # (e.g. older Camxora-1.0.0.zip uploads). Force-update must work for any
    # uploaded .exe as long as Version + Force update are set in the form.
    current = await get_software_update_config(pool)
    version = (
        str(request.version or "").strip()
        or str(current.version or "").strip()
        or (extract_version_from_installer_filename(record.filename) or "")
    )
    if not version:
        raise HTTPException(
            status_code=400,
            detail="Version is required. Set it in the Software Update form, then publish.",
        )

    release_notes = (
        request.release_notes.strip()
        if request.release_notes is not None
        else current.release_notes
    )
    mandatory = current.mandatory if request.mandatory is None else request.mandatory

    await save_software_update_config(
        pool,
        version=version,
        download_url=record.download_url,
        mandatory=mandatory,
        release_notes=release_notes,
    )

    try:
        config, recipients, changelog_slug = await publish_software_update(
            pool,
            notify_desktop_users=request.notify_desktop_users,
            create_changelog=request.create_changelog,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PublishSoftwareUpdateResponse(
        recipients=recipients,
        version=config.version,
        published_at=config.published_at or datetime.utcnow().isoformat() + "Z",
        changelog_slug=changelog_slug,
    )


@router.get(
    "/desktop/push-notifications/history",
    response_model=PushNotificationHistoryResponse,
    summary="List recent desktop push notification broadcasts (Admin)",
)
async def get_desktop_push_notification_history(ctx: AdminDep) -> PushNotificationHistoryResponse:
    from platform_api.dependencies import get_db_pool
    from platform_api.services.desktop_notification_admin_service import list_push_notification_history

    items = await list_push_notification_history(get_db_pool())
    return PushNotificationHistoryResponse(
        items=[
            PushNotificationHistoryEntry(
                id=item.id,
                title=item.title,
                message=item.message,
                created_at=item.created_at,
                recipients=item.recipients,
            )
            for item in items
        ]
    )


@router.post(
    "/desktop/push-notifications",
    response_model=SendPushNotificationResponse,
    summary="Broadcast a desktop push notification message (Admin)",
)
async def send_desktop_push_notification(
    request: SendPushNotificationRequest,
    ctx: AdminDep,
) -> SendPushNotificationResponse:
    from platform_api.dependencies import get_db_pool
    from platform_api.services.desktop_notification_admin_service import send_push_notification

    history_item, recipients = await send_push_notification(
        get_db_pool(),
        title=request.title.strip(),
        message=request.message.strip(),
    )
    return SendPushNotificationResponse(
        recipients=recipients,
        title=history_item.title,
        notification_id=history_item.id,
        created_at=history_item.created_at,
    )
