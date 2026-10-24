"""Web Music credit top-up API v2.

Handles:
- Listing credit packs
- Purchasing top-ups
- Top-up purchase history
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.services.pricing_display import credits_to_songs
from platform_api.services.v2.payment_security import sanitize_music_web_return_url
from platform_api.services.v2.topup_service import TopupService
from platform_api.exceptions import ExternalServiceError, NotFoundError, ValidationError

router = APIRouter(prefix="/topups", tags=["topups-v2"])

logger = logging.getLogger(__name__)

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
    pack_slug: str = Field(
        ...,
        pattern=r"^[a-z0-9_-]{1,64}$",
        description="Credit pack slug (e.g., 'small', 'medium')",
    )
    success_url: str = Field(default="", max_length=500, description="Ignored unless a music-web origin")
    cancel_url: str = Field(default="", max_length=500, description="Ignored unless a music-web origin")


class PurchaseTopupResponse(BaseModel):
    checkout_url: str
    payment_id: str
    expires_at: str = ""
    qr_string: str = ""
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


class TopupCheckoutStatusResponse(BaseModel):
    status: str
    fulfilled: bool
    pack_name: str
    credits: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _credit_packs_response(packs) -> CreditPacksListResponse:
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
                songs_equivalent=credits_to_songs(pack.total_credits)
            )
            for pack in packs
        ]
    )


@router.get("/packs/public", response_model=CreditPacksListResponse)
async def list_public_packs(service: TopupServiceDep) -> CreditPacksListResponse:
    """List active credit packs without requiring an account.

    Pricing is public information, so the marketing pricing page can render
    pack cards before sign-in. Purchasing still requires authentication.
    """
    return _credit_packs_response(await service.get_credit_packs())


@router.get("/packs", response_model=CreditPacksListResponse)
async def list_packs(service: TopupServiceDep) -> CreditPacksListResponse:
    """Get all available credit top-up packs.
    
    Returns packs sorted by display_order (cheapest to most expensive).
    Each pack shows:
    - Credits amount
    - Price in cents
    - Songs equivalent (10 credits = 1 generate = 2 songs)
    """
    return _credit_packs_response(await service.get_credit_packs())


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
            success_url=sanitize_music_web_return_url(body.success_url),
            cancel_url=sanitize_music_web_return_url(body.cancel_url),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    except RuntimeError as exc:
        # Provider clients raise RuntimeError for transport/HTTP failures. A
        # gateway refusal is a 502 with the provider's reason, never a bare
        # "unexpected error" the payer cannot act on.
        logger.exception("top-up checkout failed at the provider")
        raise ExternalServiceError(
            f"Payment provider could not start checkout: {exc}",
            is_retryable=True,
            details={"provider": "khqr"},
        ) from exc
    
    return PurchaseTopupResponse(
        checkout_url=payment["checkout_url"],
        payment_id=payment["payment_id"],
        expires_at=payment.get("expires_at") or "",
        qr_string=payment.get("qr_string") or "",
        pack_name=pack.name,
        credits=pack.total_credits,
        amount_cents=pack.price_cents
    )


@router.get("/payments/{payment_id}", response_model=TopupCheckoutStatusResponse)
async def get_topup_payment_status(
    payment_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    service: TopupServiceDep,
) -> TopupCheckoutStatusResponse:
    """Poll CutLuy and fulfill a music-web top-up checkout for the caller."""
    await enforce_rate_limit(http_request, ctx.user_id)
    try:
        result = await service.get_checkout_status(str(ctx.user_id), payment_id)
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    return TopupCheckoutStatusResponse(**result)


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
