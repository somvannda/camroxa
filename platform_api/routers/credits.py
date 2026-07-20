"""Credits router endpoints.

Provides User endpoints for wallet balance, pack listing, and pack purchasing,
plus Admin endpoints for pricing management, manual credit adjustments,
service availability, and global credit value configuration.

Requirements: 2.1, 2.2, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 4.1, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.7, 6.8
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.services.ai_routing_service import AIRoutingService
from platform_api.services.credit_pack_service import CreditPackService
from platform_api.services.credit_pricing_service import CreditPricingService
from platform_api.services.credit_service import CreditService
from platform_api.services.credit_units import (
    MAX_DISPLAY_CREDITS,
    MIN_DISPLAY_CREDITS,
    credits_to_units,
    units_to_credits,
    validate_display_credits,
    validate_pack_credits,
)
from platform_api.services.settings_service import SettingsService
from platform_api.models.schemas import ChannelDailyQuotaResponse, QuotaStatusResponse

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/credits", tags=["credits"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class WalletBalanceResponse(BaseModel):
    """User's current credit wallet state."""

    balance: float
    plan_quota_remaining: int | None = None
    recent_transactions: list[dict[str, Any]] = Field(default_factory=list)


class CreditPackResponse(BaseModel):
    """Response model for a credit pack."""

    id: str
    name: str
    price_cents: int
    song_credits: float
    request_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PurchaseRequest(BaseModel):
    """Body for purchasing a credit pack."""

    pack_id: str = Field(..., description="UUID of the credit pack to purchase")
    payment_ref: str = Field(
        ..., min_length=1, max_length=255, description="Payment reference from processor"
    )


class PurchaseResponse(BaseModel):
    """Response after purchasing a credit pack."""

    balance: float
    credits_added: float
    pack_name: str
    transaction_id: str


class PricingResponse(BaseModel):
    """Response model for a pricing entry."""

    model_config = {"protected_namespaces": ()}

    id: str
    ai_service: str
    operation_type: str
    sub_model: str = ""
    credits_per_operation: float
    external_cost_cents: float | None = None
    margin: float | None = None
    sell_price_cents: int | None = None
    profit_margin_cents: int | None = None
    profit_margin_percent: float | None = None
    needs_review: bool = False
    created_at: datetime
    updated_at: datetime


class CreatePricingRequest(BaseModel):
    """Body for creating a new pricing entry."""

    model_config = {"protected_namespaces": ()}

    ai_service: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    sub_model: str | None = Field(
        default=None,
        max_length=120,
        description="Model id for per-model pricing; empty means provider-wide default",
    )
    credits_per_operation: float = Field(..., ge=MIN_DISPLAY_CREDITS, le=MAX_DISPLAY_CREDITS)
    external_cost_cents: float | None = Field(default=None, ge=0)


class UpdatePricingRequest(BaseModel):
    """Body for updating an existing pricing entry."""

    model_config = {"protected_namespaces": ()}

    ai_service: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    sub_model: str | None = Field(default=None, max_length=120)
    lookup_sub_model: str | None = Field(
        default=None,
        max_length=120,
        description="Original sub_model key when editing an existing row",
    )
    credits_per_operation: float = Field(..., ge=MIN_DISPLAY_CREDITS, le=MAX_DISPLAY_CREDITS)
    external_cost_cents: float | None = Field(default=None, ge=0)


class ApprovePricingRequest(BaseModel):
    """Approve one or more draft pricing rows."""

    model_config = {"protected_namespaces": ()}

    ai_service: str | None = Field(default=None, min_length=1, max_length=100)
    operation_type: str | None = Field(default=None, min_length=1, max_length=50)
    sub_model: str | None = Field(default=None, max_length=120)
    entries: list[dict[str, str]] = Field(default_factory=list)


class AdjustBalanceRequest(BaseModel):
    """Body for manual balance adjustment (Admin)."""

    user_id: str = Field(..., description="UUID of the user to adjust")
    amount: float = Field(
        ...,
        description="Display credits to add (positive) or subtract (negative)",
    )
    reason: str = Field(..., min_length=1, max_length=255, description="Reason for adjustment")


class AdjustBalanceResponse(BaseModel):
    """Response after manual balance adjustment (or queued dual-control)."""

    user_id: str
    new_balance: float | None = None
    amount_adjusted: float
    reason: str
    status: str = "applied"
    pending_id: str | None = None
    requires_approval: bool = False
    message: str | None = None


class PendingOpDecisionRequest(BaseModel):
    """Optional note when approving/rejecting a dual-control request."""

    note: str | None = Field(default=None, max_length=500)


class PendingOpResponse(BaseModel):
    """Queued admin sensitive operation."""

    id: str
    op_type: str
    status: str
    requested_by: str
    target_user_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str
    created_at: str | None = None


class ServiceAvailabilityEntry(BaseModel):
    """Response model for a service availability entry."""

    ai_service: str
    status: str


class GlobalCreditValueResponse(BaseModel):
    """Response model for the global credit value."""

    global_credit_value: float | None = None


class UpdateGlobalCreditValueRequest(BaseModel):
    """Body for updating the global credit value."""

    value: float = Field(..., gt=0, le=1.0, description="Global credit value (> 0, <= 1.0)")


class OperationCostResponse(BaseModel):
    operation_type: str
    provider: str | None = None
    sub_model: str | None = None
    credits_per_operation: float | None = None
    available: bool = True
    message: str | None = None


class OperationCostsResponse(BaseModel):
    items: list[OperationCostResponse] = Field(default_factory=list)


class ModelCostResponse(BaseModel):
    id: str
    ai_service: str
    sub_model: str = ""
    operation_type: str
    cost_usd: float
    notes: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime


class CreateModelCostRequest(BaseModel):
    ai_service: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    sub_model: str | None = Field(default=None, max_length=120)
    cost_usd: float = Field(..., ge=0)
    notes: str | None = None


class UpdateModelCostRequest(BaseModel):
    ai_service: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    sub_model: str | None = Field(default=None, max_length=120)
    cost_usd: float = Field(..., ge=0)
    notes: str | None = None


class GeneratePricingRequest(BaseModel):
    margin_percent: float = Field(..., ge=0, lt=100)
    overwrite_existing: bool = False
    mark_needs_review: bool = True


class GeneratePricingResponse(BaseModel):
    created_count: int
    updated_count: int
    skipped_existing_count: int
    missing_cost_count: int
    missing_costs: list[dict[str, str]] = Field(default_factory=list)


class RegistryPricingGapEntry(BaseModel):
    ai_service: str
    operation_type: str
    sub_model: str = ""


class RegistryPricingGapsResponse(BaseModel):
    gap_count: int
    gaps: list[RegistryPricingGapEntry] = Field(default_factory=list)


class SeedRegistryPricingRequest(BaseModel):
    margin_percent: float = Field(..., ge=0, lt=100)


class CreateCreditPackRequest(BaseModel):
    """Body for creating a credit pack (Admin)."""

    name: str = Field(..., min_length=1, max_length=100)
    price_cents: int = Field(..., ge=50)
    song_credits: float = Field(..., ge=1, le=10_000_000)
    is_active: bool = True


class UpdateCreditPackRequest(BaseModel):
    """Body for updating a credit pack (Admin)."""

    id: str = Field(..., description="UUID of the credit pack")
    name: str = Field(..., min_length=1, max_length=100)
    price_cents: int = Field(..., ge=50)
    song_credits: float = Field(..., ge=1, le=10_000_000)
    is_active: bool = True


# ---------------------------------------------------------------------------
# Placeholder Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_credit_repo() -> CreditRepository:
    """Placeholder dependency for CreditRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "CreditRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_pricing_service() -> CreditPricingService:
    """Placeholder dependency for CreditPricingService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "CreditPricingService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_credit_pack_service() -> CreditPackService:
    """Placeholder dependency for CreditPackService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "CreditPackService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_pack_repo() -> Any:
    """Placeholder dependency for credit pack queries — override in tests or dependencies.py."""
    raise NotImplementedError(
        "CreditPackRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_settings_service() -> SettingsService:
    """Placeholder dependency for SettingsService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "SettingsService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_credit_service() -> CreditService:
    """Placeholder dependency for CreditService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "CreditService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_ai_routing_service() -> AIRoutingService:
    """Placeholder dependency for AIRoutingService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "AIRoutingService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_model_cost_service() -> Any:
    raise NotImplementedError(
        "ModelCostService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_pricing_generator_service() -> Any:
    raise NotImplementedError(
        "PricingGeneratorService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_db_pool() -> Any:
    """Resolve the asyncpg pool via the shared dependencies module."""
    from platform_api.dependencies import get_db_pool

    return get_db_pool()


# Type aliases for dependency injection
CreditRepoDep = Annotated[CreditRepository, Depends(_get_credit_repo)]
CreditServiceDep = Annotated[CreditService, Depends(_get_credit_service)]
PricingServiceDep = Annotated[CreditPricingService, Depends(_get_pricing_service)]
CreditPackServiceDep = Annotated[CreditPackService, Depends(_get_credit_pack_service)]
PackRepoDep = Annotated[Any, Depends(_get_pack_repo)]
SettingsServiceDep = Annotated[SettingsService, Depends(_get_settings_service)]
AIRoutingServiceDep = Annotated[AIRoutingService, Depends(_get_ai_routing_service)]
ModelCostServiceDep = Annotated[Any, Depends(_get_model_cost_service)]
PricingGeneratorServiceDep = Annotated[Any, Depends(_get_pricing_generator_service)]
UserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _transaction_to_api(tx: dict[str, Any]) -> dict[str, Any]:
    from platform_api.services.usage_transaction_labels import enrich_transaction_for_api

    enriched = enrich_transaction_for_api(tx)
    # User balance view: show debit magnitude as positive with direction, same as before,
    # but attach billing fields for plan-allowance UX.
    amount_display = abs(float(enriched["amount"]))
    return {
        "id": str(enriched["id"]),
        "amount": amount_display,
        "amount_units": enriched["amount_units"],
        "direction": enriched["direction"],
        "reason": enriched.get("reason"),
        "purpose": enriched.get("purpose"),
        "provider": enriched.get("provider"),
        "model": enriched.get("model"),
        "operation": enriched.get("operation"),
        "ref_id": enriched.get("ref_id"),
        "payment_ref": enriched.get("payment_ref"),
        "billing": enriched.get("billing"),
        "list_credit_units": enriched.get("list_credit_units"),
        "charged_credit_units": enriched.get("charged_credit_units"),
        "coverage": enriched.get("coverage"),
        "metadata": enriched.get("metadata"),
        "created_at": enriched.get("created_at"),
    }


def _pricing_to_response(
    entry: dict[str, Any],
    global_credit_value: float | None = None,
) -> PricingResponse:
    """Convert a pricing entry dict to the response model with margin details."""
    pricing_units = int(entry["credits_per_operation"])
    cost_units = entry.get("external_cost_cents")
    cost_units_int = int(cost_units) if cost_units is not None else None

    sell_price_cents: int | None = None
    profit_margin_cents: int | None = None
    profit_margin_percent: float | None = None

    if global_credit_value is not None and cost_units_int is not None:
        margin_details = CreditPricingService.compute_margin_details(
            credits_per_operation=pricing_units,
            external_cost_cents=cost_units_int,
            global_credit_value=global_credit_value,
        )
        if margin_details is not None:
            sell_price_cents = margin_details.sell_price_cents
            profit_margin_cents = margin_details.profit_margin_cents
            profit_margin_percent = margin_details.profit_margin_percent

    return PricingResponse(
        id=str(entry["id"]),
        ai_service=entry["ai_service"],
        operation_type=entry["operation_type"],
        sub_model=str(entry.get("sub_model") or ""),
        credits_per_operation=units_to_credits(pricing_units),
        external_cost_cents=units_to_credits(cost_units_int)
        if cost_units_int is not None
        else None,
        margin=entry.get("margin"),
        sell_price_cents=sell_price_cents,
        profit_margin_cents=profit_margin_cents,
        profit_margin_percent=profit_margin_percent,
        needs_review=bool(entry.get("needs_review", False)),
        created_at=entry["created_at"],
        updated_at=entry["updated_at"],
    )


def _pack_to_response(row: dict[str, Any]) -> CreditPackResponse:
    return CreditPackResponse(
        id=str(row["id"]),
        name=row["name"],
        price_cents=row["price_cents"],
        song_credits=units_to_credits(int(row["song_credits"])),
        request_count=row["request_count"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _pricing_units_from_request(
    pricing_credits: float,
    cost_credits: float | None,
) -> tuple[int, int | None]:
    pricing_units = validate_display_credits(
        pricing_credits,
        field="credits_per_operation",
    )
    cost_units = (
        validate_display_credits(cost_credits, field="external_cost_cents")
        if cost_credits is not None
        else None
    )
    return pricing_units, cost_units


# ---------------------------------------------------------------------------
# User Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/balance",
    response_model=WalletBalanceResponse,
    status_code=200,
    responses={
        401: {"description": "Unauthorized — invalid or missing token"},
    },
    summary="Get wallet balance (User)",
)
async def get_balance(
    ctx: UserDep,
    credit_service: CreditServiceDep,
    credit_repo: CreditRepoDep,
) -> WalletBalanceResponse:
    """Return the user's wallet balance, plan quota remaining, and recent 50 transactions."""
    from platform_api.dependencies import get_plan_repo, get_usage_tracking_repo
    from platform_api.services.quota_display_service import get_plan_quota_remaining

    user_id = UUID(ctx.user_id)
    balance = await credit_service.get_balance(ctx.user_id)

    # Get recent 50 transactions (read-only — repo direct is fine)
    transactions, _ = await credit_repo.get_transactions(user_id, page=1, page_size=50)
    plan_repo = get_plan_repo()
    usage_repo = get_usage_tracking_repo()
    plan_quota_remaining = await get_plan_quota_remaining(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
    )

    return WalletBalanceResponse(
        balance=units_to_credits(balance),
        plan_quota_remaining=plan_quota_remaining,
        recent_transactions=[_transaction_to_api(tx) for tx in transactions],
    )


@router.get(
    "/quota-status",
    response_model=QuotaStatusResponse,
    status_code=200,
    summary="Get monthly and per-channel daily quota status (User)",
)
async def get_quota_status(
    ctx: UserDep,
    credit_service: CreditServiceDep,
) -> QuotaStatusResponse:
    """Return plan quota remaining and per-channel daily caps for the current user."""
    from platform_api.dependencies import (
        get_license_repo,
        get_plan_repo,
        get_profile_repo,
        get_usage_tracking_repo,
    )
    from platform_api.services.quota_display_service import (
        get_channel_daily_quotas,
        get_monthly_quota_status,
    )

    user_id = UUID(ctx.user_id)
    balance = await credit_service.get_balance(ctx.user_id)
    plan_repo = get_plan_repo()
    usage_repo = get_usage_tracking_repo()
    profile_repo = get_profile_repo()

    songs_quota, songs_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="songs",
    )
    images_quota, images_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="images",
    )
    drafts_quota, drafts_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="drafts",
    )
    videos_quota, videos_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="videos",
    )
    merges_quota, merges_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="merges",
    )
    if images_quota is None:
        plan = await plan_repo.get_user_active_plan(user_id)
        if plan is not None and plan.monthly_image_limit is not None:
            images_quota = int(plan.monthly_image_limit)
            images_remaining = images_quota
    if drafts_quota is None:
        plan = await plan_repo.get_user_active_plan(user_id)
        if plan is not None and getattr(plan, "monthly_draft_limit", None) is not None:
            drafts_quota = int(plan.monthly_draft_limit)
            drafts_remaining = drafts_quota
    plan = await plan_repo.get_user_active_plan(user_id)
    daily_videos_limit = int(getattr(plan, "daily_video_limit", 10) or 10) if plan else None
    daily_merges_limit = int(getattr(plan, "daily_merge_limit", 1) or 1) if plan else None
    daily_videos_remaining = None
    daily_merges_remaining = None
    if plan is not None:
        from platform_api.services.billing_calendar import billing_today

        today = billing_today()
        getter = getattr(usage_repo, "get_account_daily_count", None)
        if getter is not None:
            videos_used_today = int(await getter(user_id, "video", today) or 0)
            videos_used_today += int(await getter(user_id, "video_manual", today) or 0)
            merges_used_today = await getter(user_id, "video_merge", today)
        else:
            videos_used_today = 0
            merges_used_today = 0
        daily_videos_remaining = max(0, int(daily_videos_limit or 0) - int(videos_used_today))
        daily_merges_remaining = max(0, int(daily_merges_limit or 0) - int(merges_used_today))
    channels = await get_channel_daily_quotas(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        profile_repo=profile_repo,
    )
    from platform_api.services.subscription_renewal_alert_service import (
        renewal_alert_for_license,
    )

    license_repo = get_license_repo()
    expires_at = await license_repo.get_user_license_expires_at(user_id)
    renewal_alert = renewal_alert_for_license(expires_at)
    return QuotaStatusResponse(
        songs_remaining=songs_remaining,
        songs_quota=songs_quota,
        images_remaining=images_remaining,
        images_quota=images_quota,
        drafts_remaining=drafts_remaining,
        drafts_quota=drafts_quota,
        videos_remaining=videos_remaining,
        videos_quota=videos_quota,
        merges_remaining=merges_remaining,
        merges_quota=merges_quota,
        daily_videos_remaining=daily_videos_remaining,
        daily_videos_limit=daily_videos_limit,
        daily_merges_remaining=daily_merges_remaining,
        daily_merges_limit=daily_merges_limit,
        wallet_balance=units_to_credits(balance),
        renewal_alert=renewal_alert,
        channels=[
            ChannelDailyQuotaResponse(
                profile_id=item.profile_id,
                profile_name=item.profile_name,
                daily_songs_used=item.daily_songs_used,
                daily_songs_limit=item.daily_songs_limit,
                daily_songs_remaining=item.daily_songs_remaining,
                daily_images_used=item.daily_images_used,
                daily_images_limit=item.daily_images_limit,
                daily_images_remaining=item.daily_images_remaining,
            )
            for item in channels
        ],
    )


@router.get(
    "/operation-costs",
    response_model=OperationCostsResponse,
    status_code=200,
    responses={
        401: {"description": "Unauthorized — invalid or missing token"},
    },
    summary="Get resolved generation operation costs (User)",
)
async def get_operation_costs(
    ctx: UserDep,
    pricing_service: PricingServiceDep,
    routing_service: AIRoutingServiceDep,
) -> OperationCostsResponse:
    del ctx
    items: list[OperationCostResponse] = []
    for operation_type in ("title", "album", "lyric", "music", "background_image"):
        try:
            routing = await routing_service.resolve(operation_type)
            credits_units = await pricing_service.get_price(
                routing.provider, operation_type, routing.sub_model
            )
            items.append(
                OperationCostResponse(
                    operation_type=operation_type,
                    provider=routing.provider,
                    sub_model=routing.sub_model,
                    credits_per_operation=units_to_credits(credits_units),
                    available=True,
                )
            )
        except Exception as exc:
            items.append(
                OperationCostResponse(
                    operation_type=operation_type,
                    available=False,
                    message=str(exc),
                )
            )
    return OperationCostsResponse(items=items)


@router.get(
    "/packs",
    response_model=list[CreditPackResponse],
    status_code=200,
    responses={
        401: {"description": "Unauthorized — invalid or missing token"},
    },
    summary="List available credit packs (User)",
)
async def list_packs(
    ctx: UserDep,
    pack_repo: PackRepoDep,
) -> list[CreditPackResponse]:
    """Return all active (available) credit packs for purchase.

    Requirement 6.1: Credit packs are Admin-configurable and listed
    for users to browse and purchase.
    """
    rows = await pack_repo.get_active_packs()
    return [_pack_to_response(row) for row in rows]


@router.post(
    "/purchase",
    response_model=PurchaseResponse,
    status_code=201,
    responses={
        401: {"description": "Unauthorized — invalid or missing token"},
        404: {"description": "Credit pack not found"},
        422: {"description": "Validation error"},
    },
    summary="Purchase a credit pack (User)",
)
async def purchase_pack(
    request: PurchaseRequest,
    ctx: UserDep,
    credit_service: CreditServiceDep,
    pack_repo: PackRepoDep,
) -> PurchaseResponse:
    """Disabled until CutLuy (or equivalent) verifies payment before minting credits."""
    del request, ctx, credit_service, pack_repo
    from platform_api.exceptions import ForbiddenError

    raise ForbiddenError(
        "Direct credit pack purchase is disabled. Start checkout at "
        "POST /billing/credit-pack/payments and complete payment via CutLuy.",
        details={"error_code": "CREDIT_PURCHASE_USE_BILLING_CHECKOUT"},
    )


# ---------------------------------------------------------------------------
# Admin Endpoints — Pricing
# ---------------------------------------------------------------------------


@router.get(
    "/pricing",
    response_model=list[PricingResponse],
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="List all pricing entries (Admin)",
)
async def list_pricing(
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
    settings_service: SettingsServiceDep,
) -> list[PricingResponse]:
    """Return all pricing entries with computed margins.

    Requirement 2.4: Returns all configured model operations with their
    credit charge, external API cost, and calculated margin details.
    Requirement 3.5: If GCV not configured, margin fields are null.
    """
    entries = await pricing_service.get_all_pricing()
    gcv = await settings_service.get_global_credit_value()
    return [_pricing_to_response(e, gcv) for e in entries]


@router.post(
    "/pricing",
    response_model=PricingResponse,
    status_code=201,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        409: {"description": "Duplicate pricing entry"},
        422: {"description": "Validation error"},
    },
    summary="Create pricing entry (Admin)",
)
async def create_pricing(
    request: CreatePricingRequest,
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
    settings_service: SettingsServiceDep,
) -> PricingResponse:
    """Create a new pricing entry for an ai_service/operation combination.

    Requirement 2.1: Stores ai_service, operation type,
    credits-per-operation, and external API cost.
    Requirement 5.5: Validates credits_per_operation in [1, 10000].
    Requirement 2.7: Rejects duplicate (ai_service, operation_type) with 409.
    """
    pricing_units, cost_units = _pricing_units_from_request(
        request.credits_per_operation,
        request.external_cost_cents,
    )
    entry = await pricing_service.create_price(
        ai_service=request.ai_service,
        operation_type=request.operation_type,
        credits_per_operation=pricing_units,
        external_cost_cents=cost_units,
        sub_model=request.sub_model,
    )
    gcv = await settings_service.get_global_credit_value()
    return _pricing_to_response(entry, gcv)


@router.put(
    "/pricing",
    response_model=PricingResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Pricing entry not found"},
        422: {"description": "Validation error"},
    },
    summary="Update pricing entry (Admin)",
)
async def update_pricing(
    request: UpdatePricingRequest,
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
    settings_service: SettingsServiceDep,
) -> PricingResponse:
    """Update an existing pricing entry for an ai_service/operation combination.

    Requirement 5.2: New price applies to all subsequent generation requests
    without affecting previously charged transactions.
    """
    pricing_units, cost_units = _pricing_units_from_request(
        request.credits_per_operation,
        request.external_cost_cents,
    )
    entry = await pricing_service.update_price(
        ai_service=request.ai_service,
        operation_type=request.operation_type,
        credits_per_operation=pricing_units,
        external_cost_cents=cost_units,
        sub_model=request.sub_model,
        lookup_sub_model=request.lookup_sub_model,
    )
    gcv = await settings_service.get_global_credit_value()
    return _pricing_to_response(entry, gcv)


@router.delete(
    "/pricing/all",
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="Delete all pricing entries (Admin)",
)
async def delete_all_pricing(
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
    ai_service: str | None = None,
) -> dict:
    """Permanently delete all pricing rows, optionally for one provider only."""
    deleted_count = await pricing_service.delete_all_prices(ai_service=ai_service)
    return {"deleted_count": deleted_count}


class DeletePricingRequest(BaseModel):
    """Body for deleting a pricing entry."""

    ai_service: str = Field(..., min_length=1)
    operation_type: str = Field(..., min_length=1)
    sub_model: str | None = Field(default=None, max_length=120)


@router.delete(
    "/pricing",
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Pricing entry not found"},
    },
    summary="Delete pricing entry (Admin)",
)
async def delete_pricing(
    ai_service: str,
    operation_type: str,
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
    sub_model: str | None = None,
) -> dict:
    """Permanently delete a pricing entry."""
    deleted = await pricing_service.delete_price(
        ai_service=ai_service,
        operation_type=operation_type,
        sub_model=sub_model,
    )
    if not deleted:
        raise NotFoundError(
            "Pricing entry not found.",
            details={
                "ai_service": ai_service,
                "operation_type": operation_type,
                "sub_model": sub_model,
            },
        )
    return {"deleted": True}


@router.post(
    "/pricing/approve",
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Pricing entry not found"},
    },
    summary="Approve draft pricing entries (Admin)",
)
async def approve_pricing(
    request: ApprovePricingRequest,
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
    settings_service: SettingsServiceDep,
) -> dict:
    """Clear needs_review on one or more draft pricing rows."""
    if request.entries:
        pairs = [
            (
                str(item["ai_service"]),
                str(item["operation_type"]),
                str(item.get("sub_model") or ""),
            )
            for item in request.entries
            if item.get("ai_service") and item.get("operation_type")
        ]
        result = await pricing_service.approve_pricing_many(pairs)
        return result

    if not request.ai_service or not request.operation_type:
        raise ValidationError(
            "Provide ai_service and operation_type, or a non-empty entries list.",
            details={"field": "ai_service"},
        )

    entry = await pricing_service.approve_pricing(
        request.ai_service,
        request.operation_type,
        sub_model=request.sub_model,
    )
    gcv = await settings_service.get_global_credit_value()
    return {"approved_count": 1, "entry": _pricing_to_response(entry, gcv)}


def _model_cost_to_response(row: dict[str, Any]) -> ModelCostResponse:
    return ModelCostResponse(
        id=str(row["id"]),
        ai_service=row["ai_service"],
        sub_model=str(row.get("sub_model") or ""),
        operation_type=row["operation_type"],
        cost_usd=float(row["cost_usd"]),
        notes=row.get("notes"),
        source=str(row.get("source") or "manual"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get(
    "/model-costs",
    response_model=list[ModelCostResponse],
    status_code=200,
    summary="List model USD costs (Admin)",
)
async def list_model_costs(
    _: AdminDep,
    model_cost_service: ModelCostServiceDep,
) -> list[ModelCostResponse]:
    rows = await model_cost_service.list_costs()
    return [_model_cost_to_response(row) for row in rows]


@router.post(
    "/model-costs",
    response_model=ModelCostResponse,
    status_code=201,
    summary="Create model USD cost (Admin)",
)
async def create_model_cost(
    request: CreateModelCostRequest,
    _: AdminDep,
    model_cost_service: ModelCostServiceDep,
) -> ModelCostResponse:
    row = await model_cost_service.create_cost(
        ai_service=request.ai_service,
        operation_type=request.operation_type,
        sub_model=request.sub_model,
        cost_usd=request.cost_usd,
        notes=request.notes,
    )
    return _model_cost_to_response(row)


@router.put(
    "/model-costs",
    response_model=ModelCostResponse,
    status_code=200,
    summary="Update model USD cost (Admin)",
)
async def update_model_cost(
    request: UpdateModelCostRequest,
    _: AdminDep,
    model_cost_service: ModelCostServiceDep,
) -> ModelCostResponse:
    row = await model_cost_service.update_cost(
        ai_service=request.ai_service,
        operation_type=request.operation_type,
        sub_model=request.sub_model,
        cost_usd=request.cost_usd,
        notes=request.notes,
    )
    return _model_cost_to_response(row)


@router.delete(
    "/model-costs",
    status_code=200,
    summary="Delete model USD cost (Admin)",
)
async def delete_model_cost(
    ai_service: str,
    operation_type: str,
    _: AdminDep,
    model_cost_service: ModelCostServiceDep,
    sub_model: str | None = None,
) -> dict[str, bool]:
    deleted = await model_cost_service.delete_cost(
        ai_service=ai_service,
        operation_type=operation_type,
        sub_model=sub_model,
    )
    if not deleted:
        raise NotFoundError(
            "Model cost entry not found.",
            details={
                "ai_service": ai_service,
                "operation_type": operation_type,
                "sub_model": sub_model,
            },
        )
    return {"deleted": True}


@router.post(
    "/model-costs/seed",
    status_code=200,
    summary="Seed model costs from registry estimates (Admin)",
)
async def seed_model_costs(
    _: AdminDep,
    model_cost_service: ModelCostServiceDep,
    pricing_service: PricingServiceDep,
    overwrite: bool = False,
) -> dict[str, int]:
    cost_result = await model_cost_service.seed_from_registry(overwrite=overwrite)
    pricing_result = await pricing_service.seed_local_platform_pricing(
        overwrite=overwrite
    )
    return {
        **cost_result,
        "local_pricing_created_count": pricing_result["created_count"],
        "local_pricing_updated_count": pricing_result["updated_count"],
        "local_pricing_skipped_count": pricing_result["skipped_existing_count"],
    }


@router.post(
    "/pricing/generate",
    response_model=GeneratePricingResponse,
    status_code=200,
    summary="Auto-generate credit pricing from model costs (Admin)",
)
async def generate_pricing(
    request: GeneratePricingRequest,
    _: AdminDep,
    pricing_generator: PricingGeneratorServiceDep,
    settings_service: SettingsServiceDep,
    routing_service: AIRoutingServiceDep,
) -> GeneratePricingResponse:
    gcv = await settings_service.get_global_credit_value()
    if gcv is None:
        raise ValidationError(
            "Configure Global Credit Value before generating pricing.",
            details={"field": "global_credit_value"},
        )

    assignments_data = await routing_service.get_all_assignments()
    flat_assignments: dict[str, dict[str, Any]] = {}
    for service_type in ("text_generation", "image_generation", "music_generation"):
        flat_assignments.update(assignments_data.get(service_type, {}))

    result = await pricing_generator.generate_from_costs(
        margin_percent=request.margin_percent,
        global_credit_value=gcv,
        assignments=flat_assignments,
        text_fallback_chain=assignments_data.get("text_fallback_chain", []),
        image_fallback_chain=assignments_data.get("image_fallback_chain", []),
        overwrite_existing=request.overwrite_existing,
        mark_needs_review=request.mark_needs_review,
    )
    return GeneratePricingResponse(
        created_count=int(result["created_count"]),
        updated_count=int(result["updated_count"]),
        skipped_existing_count=int(result["skipped_existing_count"]),
        missing_cost_count=int(result["missing_cost_count"]),
        missing_costs=list(result.get("missing_costs") or []),
    )


@router.get(
    "/pricing/registry-gaps",
    response_model=RegistryPricingGapsResponse,
    status_code=200,
    summary="List registry catalog pairs missing from credit pricing (Admin)",
)
async def list_registry_pricing_gaps(
    _: AdminDep,
    pricing_generator: PricingGeneratorServiceDep,
) -> RegistryPricingGapsResponse:
    gaps = await pricing_generator.list_registry_pricing_gaps()
    return RegistryPricingGapsResponse(
        gap_count=len(gaps),
        gaps=[
            RegistryPricingGapEntry(
                ai_service=str(item["ai_service"]),
                operation_type=str(item["operation_type"]),
                sub_model=str(item.get("sub_model") or ""),
            )
            for item in gaps
        ],
    )


@router.post(
    "/pricing/seed-from-registry",
    response_model=GeneratePricingResponse,
    status_code=200,
    summary="Create needs-review pricing rows for registry pairs not yet priced (Admin)",
)
async def seed_pricing_from_registry(
    request: SeedRegistryPricingRequest,
    _: AdminDep,
    pricing_generator: PricingGeneratorServiceDep,
    settings_service: SettingsServiceDep,
) -> GeneratePricingResponse:
    gcv = await settings_service.get_global_credit_value()
    if gcv is None:
        raise ValidationError(
            "Configure Global Credit Value before seeding pricing.",
            details={"field": "global_credit_value"},
        )

    result = await pricing_generator.generate_missing_from_registry(
        margin_percent=request.margin_percent,
        global_credit_value=gcv,
    )
    return GeneratePricingResponse(
        created_count=int(result["created_count"]),
        updated_count=int(result["updated_count"]),
        skipped_existing_count=int(result["skipped_existing_count"]),
        missing_cost_count=int(result["missing_cost_count"]),
        missing_costs=list(result.get("missing_costs") or []),
    )


# ---------------------------------------------------------------------------
# Admin Endpoints — Credit Packs
# ---------------------------------------------------------------------------


@router.get(
    "/admin/packs",
    response_model=list[CreditPackResponse],
    status_code=200,
    summary="List all credit packs (Admin)",
)
async def list_admin_packs(
    _: AdminDep,
    pack_service: CreditPackServiceDep,
) -> list[CreditPackResponse]:
    """Return active and inactive credit packs for admin management."""
    rows = await pack_service.list_packs(include_inactive=True)
    return [_pack_to_response(row) for row in rows]


@router.post(
    "/admin/packs",
    response_model=CreditPackResponse,
    status_code=201,
    summary="Create credit pack (Admin)",
)
async def create_admin_pack(
    request: CreateCreditPackRequest,
    _: AdminDep,
    pack_service: CreditPackServiceDep,
) -> CreditPackResponse:
    created = await pack_service.create_pack(
        name=request.name,
        price_cents=request.price_cents,
        song_credits=validate_pack_credits(request.song_credits),
        is_active=request.is_active,
    )
    return _pack_to_response(created)


@router.put(
    "/admin/packs",
    response_model=CreditPackResponse,
    status_code=200,
    summary="Update credit pack (Admin)",
)
async def update_admin_pack(
    request: UpdateCreditPackRequest,
    _: AdminDep,
    pack_service: CreditPackServiceDep,
) -> CreditPackResponse:
    updated = await pack_service.update_pack(
        request.id,
        name=request.name,
        price_cents=request.price_cents,
        song_credits=validate_pack_credits(request.song_credits),
        is_active=request.is_active,
    )
    return _pack_to_response(updated)


@router.delete(
    "/admin/packs",
    status_code=200,
    summary="Delete credit pack (Admin)",
)
async def delete_admin_pack(
    pack_id: str,
    _: AdminDep,
    pack_service: CreditPackServiceDep,
) -> dict:
    await pack_service.delete_pack(pack_id)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Admin Endpoints — Service Availability
# ---------------------------------------------------------------------------


@router.get(
    "/service-availability",
    response_model=list[ServiceAvailabilityEntry],
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="Get AI service availability (Admin)",
)
async def get_service_availability(
    ctx: AdminDep,
    pricing_service: PricingServiceDep,
) -> list[ServiceAvailabilityEntry]:
    """Return per-service availability based on Key Pool status.

    Requirement 4.1: Returns each AI_Service's status based on key pool entries.
    """
    availability = await pricing_service.get_service_availability()
    return [
        ServiceAvailabilityEntry(
            ai_service=entry["ai_service"],
            status=entry["status"],
        )
        for entry in availability
    ]


# ---------------------------------------------------------------------------
# Admin Endpoints — Global Credit Value
# ---------------------------------------------------------------------------


@router.get(
    "/global-credit-value",
    response_model=GlobalCreditValueResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="Get Global Credit Value (Admin)",
)
async def get_global_credit_value(
    ctx: AdminDep,
    settings_service: SettingsServiceDep,
) -> GlobalCreditValueResponse:
    """Return the current Global Credit Value setting.

    Requirement 3.1: Returns the configured GCV or null if not set.
    """
    gcv = await settings_service.get_global_credit_value()
    return GlobalCreditValueResponse(global_credit_value=gcv)


@router.put(
    "/global-credit-value",
    response_model=GlobalCreditValueResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        422: {"description": "Validation error — value must be > 0 and <= 1.0"},
    },
    summary="Update Global Credit Value (Admin)",
)
async def update_global_credit_value(
    request: UpdateGlobalCreditValueRequest,
    ctx: AdminDep,
    settings_service: SettingsServiceDep,
) -> GlobalCreditValueResponse:
    """Update the Global Credit Value.

    Requirement 3.2: Validates > 0 and <= 1.0, then stores the new value.
    """
    updated_value = await settings_service.update_global_credit_value(request.value)
    return GlobalCreditValueResponse(global_credit_value=updated_value)


# ---------------------------------------------------------------------------
# Admin Endpoints — Balance Adjustment
# ---------------------------------------------------------------------------


@router.post(
    "/adjust",
    response_model=AdjustBalanceResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        422: {"description": "Validation error (balance would go below 0 or exceed max)"},
    },
    summary="Manual balance adjustment (Admin)",
)
async def adjust_balance(
    request: AdjustBalanceRequest,
    ctx: AdminDep,
    credit_service: CreditServiceDep,
    pool: Annotated[Any, Depends(_get_db_pool)],
) -> AdjustBalanceResponse:
    """Manually adjust a user's wallet balance (add or subtract credits).

    Large adjusts (see PLATFORM_ADMIN_ADJUST_DUAL_CONTROL_CREDITS) are queued
    for a second admin to approve before applying.
    """
    from platform_api.services.dual_control_service import DualControlService

    dual = DualControlService(pool=pool, credit_service=credit_service)
    result = await dual.request_or_apply_credit_adjust(
        admin_id=ctx.user_id,
        user_id=request.user_id,
        amount_display=request.amount,
        reason=request.reason,
    )
    if result.get("status") == "applied" and result.get("new_balance") is not None:
        from platform_api.services.credit_audit_service import log_wallet_credit_event
        from platform_api.services.credit_units import credits_to_units

        amount_units = credits_to_units(request.amount)
        await log_wallet_credit_event(
            actor_id=ctx.user_id,
            user_id=request.user_id,
            action_type="credit.adjust",
            amount_units=amount_units,
            reason=request.reason,
            metadata={"admin_adjust": True, "new_balance_display": result["new_balance"]},
        )
    return AdjustBalanceResponse(
        user_id=result["user_id"],
        new_balance=result.get("new_balance"),
        amount_adjusted=result["amount_adjusted"],
        reason=result["reason"],
        status=result["status"],
        pending_id=result.get("pending_id"),
        requires_approval=bool(result.get("requires_approval")),
        message=result.get("message"),
    )


@router.get(
    "/pending-ops",
    response_model=list[PendingOpResponse],
    status_code=200,
    summary="List pending dual-control admin ops",
)
async def list_pending_ops(
    ctx: AdminDep,
    pool: Annotated[Any, Depends(_get_db_pool)],
    credit_service: CreditServiceDep,
) -> list[PendingOpResponse]:
    """Return queued dual-control requests awaiting a second admin."""
    del credit_service
    from platform_api.services.dual_control_service import DualControlService

    dual = DualControlService(pool=pool, credit_service=None)
    rows = await dual.list_pending()
    return [PendingOpResponse(**row) for row in rows]


@router.post(
    "/pending-ops/{pending_id}/approve",
    response_model=AdjustBalanceResponse,
    status_code=200,
    summary="Approve a pending dual-control credit adjust",
)
async def approve_pending_op(
    pending_id: UUID,
    request: PendingOpDecisionRequest,
    ctx: AdminDep,
    credit_service: CreditServiceDep,
    pool: Annotated[Any, Depends(_get_db_pool)],
) -> AdjustBalanceResponse:
    from platform_api.services.dual_control_service import DualControlService

    dual = DualControlService(pool=pool, credit_service=credit_service)
    result = await dual.approve(
        pending_id=pending_id,
        admin_id=ctx.user_id,
        note=request.note,
    )
    return AdjustBalanceResponse(
        user_id=result["user_id"],
        new_balance=result.get("new_balance"),
        amount_adjusted=result["amount_adjusted"],
        reason=result["reason"],
        status=result["status"],
        pending_id=result.get("pending_id"),
        requires_approval=False,
        message="Dual-control adjustment approved and applied.",
    )


@router.post(
    "/pending-ops/{pending_id}/reject",
    response_model=PendingOpResponse,
    status_code=200,
    summary="Reject a pending dual-control credit adjust",
)
async def reject_pending_op(
    pending_id: UUID,
    request: PendingOpDecisionRequest,
    ctx: AdminDep,
    credit_service: CreditServiceDep,
    pool: Annotated[Any, Depends(_get_db_pool)],
) -> PendingOpResponse:
    from platform_api.services.dual_control_service import DualControlService

    dual = DualControlService(pool=pool, credit_service=credit_service)
    await dual.reject(pending_id=pending_id, admin_id=ctx.user_id, note=request.note)
    return PendingOpResponse(
        id=str(pending_id),
        op_type="credit.adjust",
        status="rejected",
        requested_by="",
        reason=request.note or "rejected",
    )
