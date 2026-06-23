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
from platform_api.services.credit_pricing_service import CreditPricingService
from platform_api.services.credit_service import CreditService
from platform_api.services.settings_service import SettingsService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/credits", tags=["credits"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class WalletBalanceResponse(BaseModel):
    """User's current credit wallet state."""

    balance: int
    plan_quota_remaining: int | None = None
    recent_transactions: list[dict[str, Any]] = Field(default_factory=list)


class CreditPackResponse(BaseModel):
    """Response model for a credit pack."""

    id: str
    name: str
    price_cents: int
    song_credits: int
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

    balance: int
    credits_added: int
    pack_name: str
    transaction_id: str


class PricingResponse(BaseModel):
    """Response model for a pricing entry."""

    model_config = {"protected_namespaces": ()}

    id: str
    ai_service: str
    operation_type: str
    credits_per_operation: int
    external_cost_cents: int | None = None
    margin: float | None = None
    sell_price_cents: int | None = None
    profit_margin_cents: int | None = None
    profit_margin_percent: float | None = None
    created_at: datetime
    updated_at: datetime


class CreatePricingRequest(BaseModel):
    """Body for creating a new pricing entry."""

    model_config = {"protected_namespaces": ()}

    ai_service: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    credits_per_operation: int = Field(..., ge=1, le=10000)
    external_cost_cents: int | None = Field(default=None, ge=0)


class UpdatePricingRequest(BaseModel):
    """Body for updating an existing pricing entry."""

    model_config = {"protected_namespaces": ()}

    ai_service: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    credits_per_operation: int = Field(..., ge=1, le=10000)
    external_cost_cents: int | None = Field(default=None, ge=0)


class AdjustBalanceRequest(BaseModel):
    """Body for manual balance adjustment (Admin)."""

    user_id: str = Field(..., description="UUID of the user to adjust")
    amount: int = Field(..., description="Credits to add (positive) or subtract (negative)")
    reason: str = Field(..., min_length=1, max_length=255, description="Reason for adjustment")


class AdjustBalanceResponse(BaseModel):
    """Response after manual balance adjustment."""

    user_id: str
    new_balance: int
    amount_adjusted: int
    reason: str


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


# Type aliases for dependency injection
CreditRepoDep = Annotated[CreditRepository, Depends(_get_credit_repo)]
CreditServiceDep = Annotated[CreditService, Depends(_get_credit_service)]
PricingServiceDep = Annotated[CreditPricingService, Depends(_get_pricing_service)]
PackRepoDep = Annotated[Any, Depends(_get_pack_repo)]
SettingsServiceDep = Annotated[SettingsService, Depends(_get_settings_service)]
UserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pricing_to_response(
    entry: dict[str, Any],
    global_credit_value: float | None = None,
) -> PricingResponse:
    """Convert a pricing entry dict to the response model with margin details."""
    sell_price_cents: int | None = None
    profit_margin_cents: int | None = None
    profit_margin_percent: float | None = None

    external_cost_cents = entry.get("external_cost_cents")
    if global_credit_value is not None and external_cost_cents is not None:
        margin_details = CreditPricingService.compute_margin_details(
            credits_per_operation=entry["credits_per_operation"],
            external_cost_cents=external_cost_cents,
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
        credits_per_operation=entry["credits_per_operation"],
        external_cost_cents=external_cost_cents,
        margin=entry.get("margin"),
        sell_price_cents=sell_price_cents,
        profit_margin_cents=profit_margin_cents,
        profit_margin_percent=profit_margin_percent,
        created_at=entry["created_at"],
        updated_at=entry["updated_at"],
    )


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
    user_id = UUID(ctx.user_id)
    balance = await credit_service.get_balance(ctx.user_id)

    # Get recent 50 transactions (read-only — repo direct is fine)
    transactions, _ = await credit_repo.get_transactions(user_id, page=1, page_size=50)

    return WalletBalanceResponse(
        balance=balance,
        plan_quota_remaining=None,
        recent_transactions=transactions,
    )


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
    return [
        CreditPackResponse(
            id=str(row["id"]),
            name=row["name"],
            price_cents=row["price_cents"],
            song_credits=row["song_credits"],
            request_count=row["request_count"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


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
) -> PurchaseResponse:
    """Purchase a credit pack and add credits to the user's wallet."""
    new_balance = await credit_service.purchase_pack(
        user_id=ctx.user_id,
        pack_id=request.pack_id,
        payment_ref=request.payment_ref,
    )

    return PurchaseResponse(
        balance=new_balance,
        credits_added=0,  # The service handles the actual amount
        pack_name=request.pack_id,
        transaction_id=request.pack_id,
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
    entry = await pricing_service.create_price(
        ai_service=request.ai_service,
        operation_type=request.operation_type,
        credits_per_operation=request.credits_per_operation,
        external_cost_cents=request.external_cost_cents,
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
    entry = await pricing_service.update_price(
        ai_service=request.ai_service,
        operation_type=request.operation_type,
        credits_per_operation=request.credits_per_operation,
        external_cost_cents=request.external_cost_cents,
    )
    gcv = await settings_service.get_global_credit_value()
    return _pricing_to_response(entry, gcv)


class DeletePricingRequest(BaseModel):
    """Body for deleting a pricing entry."""

    ai_service: str = Field(..., min_length=1)
    operation_type: str = Field(..., min_length=1)


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
) -> dict:
    """Permanently delete a pricing entry."""
    deleted = await pricing_service.delete_price(
        ai_service=ai_service,
        operation_type=operation_type,
    )
    if not deleted:
        raise NotFoundError(
            "Pricing entry not found.",
            details={
                "ai_service": ai_service,
                "operation_type": operation_type,
            },
        )
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
) -> AdjustBalanceResponse:
    """Manually adjust a user's wallet balance (add or subtract credits)."""
    new_balance = await credit_service.admin_adjust(
        user_id=request.user_id,
        amount=request.amount,
        reason=request.reason,
    )

    return AdjustBalanceResponse(
        user_id=request.user_id,
        new_balance=new_balance,
        amount_adjusted=request.amount,
        reason=request.reason,
    )
