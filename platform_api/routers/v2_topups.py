"""Web Music credit top-up API v2.

Handles:
- Listing credit packs
- Purchasing top-ups
- Top-up purchase history
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.services.v2.topup_service import TopupService
from platform_api.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/v2/topups", tags=["topups-v2"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


async def _get_topup_service() -> TopupService:
    raise NotImplementedError("TopupService dependency not configured.")


TopupServiceDep = Annotated[TopupService, Depends(_get_topup_service)]


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class CreditPackResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    total_credits: int
    price_cents: int
    display_order: int
    songs_equivalent: int  # Calculated: credits / 10


class CreditPacksListResponse(BaseModel):
    packs: list[CreditPackResponse]


class PurchaseTopupRequest(BaseModel):
    pack_slug: str = Field(..., description="Credit pack slug (e.g., 'small', 'medium')")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect after cancelled payment")


class PurchaseTopupResponse(BaseModel):
    checkout_url: str
    payment_id: str
    expires_at: str
    pack_name: str
    credits: int
    amount_cents: int


class TopupPurchaseResponse(BaseModel):
    id: str
    pack_name: str
    credits_purchased: int
    amount_paid_cents: int
    payment_status: str
    purchased_at: str


class TopupHistoryResponse(BaseModel):
    purchases: list[TopupPurchaseResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/packs", response_model=CreditPacksListResponse)
async def list_packs(service: TopupServiceDep) -> CreditPacksListResponse:
    """Get all available credit top-up packs.
    
    Returns packs sorted by display_order (cheapest to most expensive).
    Each pack shows:
    - Credits amount
    - Price in cents
    - Songs equivalent (assuming 10 credits per song)
    """
    packs = await service.get_credit_packs()
    
    return CreditPacksListResponse(
        packs=[
            CreditPackResponse(
                id=str(pack.id),
                slug=pack.slug,
                name=pack.name,
                description=getattr(pack, "description", "") or "",
                total_credits=pack.total_credits,
                price_cents=pack.price_cents,
                display_order=pack.display_order,
                songs_equivalent=pack.total_credits // 10
            )
            for pack in packs
        ]
    )


@router.post("/purchase", response_model=PurchaseTopupResponse, status_code=200)
async def purchase_topup(
    body: PurchaseTopupRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: TopupServiceDep
) -> PurchaseTopupResponse:
    """Create a CutLuy checkout session for credit top-up purchase.
    
    User will be redirected to CutLuy to complete payment.
    After payment, CutLuy will call our webhook to grant credits automatically.
    """
    await enforce_rate_limit(http_request, ctx.user_id)
    
    # Get pack details
    pack = await service.get_pack_by_slug(body.pack_slug)
    if not pack:
        raise NotFoundError(f"Credit pack '{body.pack_slug}' not found")
    
    try:
        payment = await service.purchase_topup(
            user_id=str(ctx.user_id),
            pack_slug=body.pack_slug,
            success_url=body.success_url,
            cancel_url=body.cancel_url
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    
    return PurchaseTopupResponse(
        checkout_url=payment["checkout_url"],
        payment_id=payment["payment_id"],
        expires_at=payment["expires_at"],
        pack_name=pack.name,
        credits=pack.total_credits,
        amount_cents=pack.price_cents
    )


@router.get("/history", response_model=TopupHistoryResponse)
async def get_history(
    ctx: CurrentUserDep,
    service: TopupServiceDep,
    limit: int = 50,
    offset: int = 0
) -> TopupHistoryResponse:
    """Get the current user's top-up purchase history.
    
    Query params:
    - limit: Number of purchases to return (max 100)
    - offset: Number of purchases to skip
    """
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
    
    purchases = await service.get_user_topups(
        user_id=str(ctx.user_id),
        limit=limit,
        offset=offset
    )
    total = len(purchases) if offset == 0 and len(purchases) < limit else offset + len(purchases)

    return TopupHistoryResponse(
        purchases=[
            TopupPurchaseResponse(
                id=str(purchase.id),
                pack_name=purchase.pack_name or "Credit pack",
                credits_purchased=purchase.credits_purchased,
                amount_paid_cents=purchase.amount_paid_cents,
                payment_status=purchase.payment_status,
                purchased_at=str(purchase.created_at)
            )
            for purchase in purchases
        ],
        total=total,
        limit=limit,
        offset=offset
    )
