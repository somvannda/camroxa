"""Credits router endpoints.

Provides User endpoints for wallet balance, pack listing, and pack purchasing,
plus Admin endpoints for pricing management and manual credit adjustments.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.7, 6.8
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.services.credit_pricing_service import CreditPricingService

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
    model_identifier: str
    operation_type: str
    credits_per_operation: int
    external_cost_cents: int | None = None
    margin: float | None = None
    created_at: datetime
    updated_at: datetime


class CreatePricingRequest(BaseModel):
    """Body for creating a new pricing entry."""

    model_config = {"protected_namespaces": ()}

    model_identifier: str = Field(..., min_length=1, max_length=100)
    operation_type: str = Field(..., min_length=1, max_length=50)
    credits_per_operation: int = Field(..., ge=1, le=10000)
    external_cost_cents: int | None = Field(default=None, ge=0)


class UpdatePricingRequest(BaseModel):
    """Body for updating an existing pricing entry."""

    model_config = {"protected_namespaces": ()}

    model_identifier: str = Field(..., min_length=1, max_length=100)
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


# Type aliases for dependency injection
CreditRepoDep = Annotated[CreditRepository, Depends(_get_credit_repo)]
PricingServiceDep = Annotated[CreditPricingService, Depends(_get_pricing_service)]
PackRepoDep = Annotated[Any, Depends(_get_pack_repo)]
UserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pricing_to_response(entry: dict[str, Any]) -> PricingResponse:
    """Convert a pricing entry dict to the response model."""
    return PricingResponse(
        id=str(entry["id"]),
        model_identifier=entry["model_identifier"],
        operation_type=entry["operation_type"],
        credits_per_operation=entry["credits_per_operation"],
        external_cost_cents=entry.get("external_cost_cents"),
        margin=entry.get("margin"),
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
    credit_repo: CreditRepoDep,
) -> WalletBalanceResponse:
    """Return the user's wallet balance, plan quota remaining, and recent 50 transactions.

    Requirement 6.8: Returns current credit balance, active plan song quota
    remaining (if on Monthly/Yearly), and the most recent 50 transactions.
    """
    user_id = UUID(ctx.user_id)
    balance = await credit_repo.get_balance(user_id)

    # Get recent 50 transactions
    transactions, _ = await credit_repo.get_transactions(user_id, page=1, page_size=50)

    # plan_quota_remaining is populated by the license service in the full flow;
    # for now we return None until the quota consumption logic is wired.
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
    credit_repo: CreditRepoDep,
    pack_repo: PackRepoDep,
) -> PurchaseResponse:
    """Purchase a credit pack and add credits to the user's wallet.

    Requirement 6.3: Adds pack's song credits to the user's wallet.
    Requirement 6.5: Records the transaction with timestamp, pack identifier,
    amount paid, credit quantity added, and payment reference.
    Requirement 6.10: Rejects if purchase would exceed max wallet balance.
    """
    user_id = UUID(ctx.user_id)
    pack_id = UUID(request.pack_id)

    # Fetch the pack
    pack = await pack_repo.get_by_id(pack_id)
    if pack is None or not pack.get("is_active", False):
        raise NotFoundError(
            "Credit pack not found or inactive.",
            details={"pack_id": request.pack_id},
        )

    # Add credits to wallet (this enforces max balance constraint)
    new_balance = await credit_repo.add_credits(
        user_id=user_id,
        amount=pack["song_credits"],
        reason="pack_purchase",
        ref_id=str(pack_id),
        pack_id=pack_id,
        payment_ref=request.payment_ref,
    )

    return PurchaseResponse(
        balance=new_balance,
        credits_added=pack["song_credits"],
        pack_name=pack["name"],
        transaction_id=str(pack_id),  # The pack_id serves as ref for now
    )


# ---------------------------------------------------------------------------
# Admin Endpoints
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
) -> list[PricingResponse]:
    """Return all pricing entries with computed margins.

    Requirement 5.4: Returns all configured model operations with their
    credit charge, external API cost, and calculated margin.
    """
    entries = await pricing_service.get_all_pricing()
    return [_pricing_to_response(e) for e in entries]


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
) -> PricingResponse:
    """Create a new pricing entry for a model/operation combination.

    Requirement 5.1: Stores model identifier, operation type,
    credits-per-operation, and external API cost.
    Requirement 5.5: Validates credits_per_operation in [1, 10000].
    Requirement 5.7: Rejects duplicate (model_identifier, operation_type).
    """
    entry = await pricing_service.create_price(
        model_identifier=request.model_identifier,
        operation_type=request.operation_type,
        credits_per_operation=request.credits_per_operation,
        external_cost_cents=request.external_cost_cents,
    )
    return _pricing_to_response(entry)


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
) -> PricingResponse:
    """Update an existing pricing entry for a model/operation combination.

    Requirement 5.2: New price applies to all subsequent generation requests
    without affecting previously charged transactions.
    """
    entry = await pricing_service.update_price(
        model_identifier=request.model_identifier,
        operation_type=request.operation_type,
        credits_per_operation=request.credits_per_operation,
        external_cost_cents=request.external_cost_cents,
    )
    return _pricing_to_response(entry)


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
    credit_repo: CreditRepoDep,
) -> AdjustBalanceResponse:
    """Manually adjust a user's wallet balance (add or subtract credits).

    Requirement 6.7: Admin can add bonus credits or subtract for dispute
    resolution. Resulting balance must not go below zero or exceed 10,000,000.
    """
    user_id = UUID(request.user_id)

    if request.amount == 0:
        raise ValidationError(
            "Adjustment amount must be non-zero.",
            details={"amount": request.amount},
        )

    if request.amount > 0:
        # Adding credits
        new_balance = await credit_repo.add_credits(
            user_id=user_id,
            amount=request.amount,
            reason=f"admin_adjustment: {request.reason}",
            ref_id=f"admin:{ctx.user_id}",
        )
    else:
        # Subtracting credits — use atomic_deduct
        deduct_amount = abs(request.amount)
        success = await credit_repo.atomic_deduct(
            user_id=user_id,
            amount=deduct_amount,
            reason=f"admin_adjustment: {request.reason}",
            ref_id=f"admin:{ctx.user_id}",
        )
        if not success:
            raise ValidationError(
                "Insufficient balance for the requested deduction.",
                details={
                    "user_id": request.user_id,
                    "requested_deduction": deduct_amount,
                },
            )
        new_balance = await credit_repo.get_balance(user_id)

    return AdjustBalanceResponse(
        user_id=request.user_id,
        new_balance=new_balance,
        amount_adjusted=request.amount,
        reason=request.reason,
    )
