"""Web Music subscription management API v2.

Handles:
- Listing available plans
- Creating and managing subscriptions
- Credit balance and quota management
- Payment integration with CutLuy
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.services.v2.payment_security import sanitize_music_web_return_url
from platform_api.services.v2.subscription_service import SubscriptionService
from platform_api.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/subscriptions", tags=["subscriptions-v2"])

CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


def _iso(value: object) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)


def _subscription_response(subscription: dict) -> SubscriptionResponse:
    cancelled = subscription.get("cancelled_at")
    return SubscriptionResponse(
        id=str(subscription["id"]),
        user_id=str(subscription["user_id"]),
        plan_id=str(subscription["plan_id"]),
        plan_name=subscription.get("plan_name") or "Pro",
        status=subscription["status"],
        billing_cycle=subscription["billing_cycle"],
        current_period_start=_iso(subscription["current_period_start"]),
        current_period_end=_iso(subscription["current_period_end"]),
        cancel_at_period_end=bool(subscription.get("cancel_at_period_end")),
        monthly_credits_granted=int(subscription.get("monthly_credits_granted") or 0),
        monthly_credits_used=int(subscription.get("monthly_credits_used") or 0),
        topup_credits_balance=int(subscription.get("topup_credits_balance") or 0),
        total_credits_available=int(subscription.get("total_credits_available") or 0),
        created_at=_iso(subscription["created_at"]),
        cancelled_at=_iso(cancelled) if cancelled else None,
    )


async def _get_subscription_service() -> SubscriptionService:
    raise NotImplementedError("SubscriptionService dependency not configured.")


SubscriptionServiceDep = Annotated[SubscriptionService, Depends(_get_subscription_service)]


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    id: str
    name: str
    price_cents: int
    billing_cycle: str
    monthly_credits: int
    features: list[str]
    display_order: int
    is_public: bool


class PlansListResponse(BaseModel):
    plans: list[PlanResponse]


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan_id: str
    plan_name: str
    status: str
    billing_cycle: str
    current_period_start: str
    current_period_end: str
    cancel_at_period_end: bool
    monthly_credits_granted: int
    monthly_credits_used: int
    topup_credits_balance: int
    total_credits_available: int
    created_at: str
    cancelled_at: str | None = None


class PurchaseSubscriptionRequest(BaseModel):
    plan_id: UUID = Field(..., description="Plan UUID to subscribe to")
    success_url: str = Field(default="", max_length=500, description="Ignored unless a music-web origin")
    cancel_url: str = Field(default="", max_length=500, description="Ignored unless a music-web origin")


class PurchaseSubscriptionResponse(BaseModel):
    checkout_url: str
    payment_id: str
    expires_at: str = ""
    qr_string: str = ""


class CancelSubscriptionRequest(BaseModel):
    cancel_at_period_end: bool = Field(
        default=True,
        description="If True, cancel at end of billing period. If False, cancel immediately."
    )


class CancelSubscriptionResponse(BaseModel):
    success: bool
    message: str
    subscription: SubscriptionResponse | None = None


class CheckoutStatusResponse(BaseModel):
    status: str
    fulfilled: bool
    plan_name: str
    credits: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=PlansListResponse)
async def list_plans(service: SubscriptionServiceDep) -> PlansListResponse:
    """Get all available subscription plans for web music.
    
    Returns public plans sorted by display_order.
    """
    plans = await service.get_plans(is_public=True)
    
    def format_features(features_dict: dict | None) -> list[str]:
        """Convert features dict to user-friendly list."""
        result = []
        if features_dict.get("music"):
            result.append("High-quality AI music generation")
        if features_dict.get("images"):
            result.append("AI image generation")
        if features_dict.get("topup"):
            result.append("Purchase additional credit packs")
        result.extend([
            "Commercial use license",
            "MP3 and WAV downloads",
            "Priority support"
        ])
        return result
    
    return PlansListResponse(
        plans=[
            PlanResponse(
                id=str(plan.id),
                name=plan.name,
                price_cents=plan.price_cents,
                billing_cycle="yearly" if plan.billing_cycle_days >= 365 else "monthly",
                monthly_credits=plan.monthly_credits,
                features=format_features(plan.features or {}),
                display_order=plan.display_order,
                is_public=plan.is_public
            )
            for plan in plans
        ]
    )


@router.get("/my-subscription", response_model=SubscriptionResponse | None)
async def get_my_subscription(
    ctx: CurrentUserDep,
    service: SubscriptionServiceDep
) -> SubscriptionResponse | None:
    """Get the current user's active subscription.
    
    Returns None if user has no active subscription.
    """
    subscription = await service.get_user_subscription(ctx.user_id)
    
    if not subscription:
        return None

    return _subscription_response(subscription)


@router.post("/purchase", response_model=PurchaseSubscriptionResponse, status_code=200)
async def purchase_subscription(
    body: PurchaseSubscriptionRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: SubscriptionServiceDep
) -> PurchaseSubscriptionResponse:
    """Create a CutLuy checkout session for subscription payment.
    
    User will be redirected to CutLuy to complete payment.
    After payment, CutLuy will call our webhook to activate the subscription.
    """
    await enforce_rate_limit(http_request, ctx.user_id)
    
    # Check if user already has active subscription
    existing = await service.get_user_subscription(ctx.user_id)
    if existing and existing["status"] == "active":
        raise ValidationError("You already have an active subscription. Cancel it first to change plans.")
    
    # Create subscription checkout
    try:
        payment = await service.create_subscription_by_plan_id(
            user_id=str(ctx.user_id),
            plan_id=str(body.plan_id),
            success_url=sanitize_music_web_return_url(body.success_url),
            cancel_url=sanitize_music_web_return_url(body.cancel_url),
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    
    return PurchaseSubscriptionResponse(
        checkout_url=payment["checkout_url"],
        payment_id=payment["payment_id"],
        expires_at=payment.get("expires_at") or "",
        qr_string=payment.get("qr_string") or "",
    )


@router.get("/payments/{payment_id}", response_model=CheckoutStatusResponse)
async def get_subscription_payment_status(
    payment_id: str,
    http_request: Request,
    ctx: CurrentUserDep,
    service: SubscriptionServiceDep,
) -> CheckoutStatusResponse:
    """Poll CutLuy and fulfill a music-web subscription checkout for the caller."""
    await enforce_rate_limit(http_request, ctx.user_id)
    try:
        result = await service.get_checkout_status(str(ctx.user_id), payment_id)
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    return CheckoutStatusResponse(**result)


@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    body: CancelSubscriptionRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    service: SubscriptionServiceDep
) -> CancelSubscriptionResponse:
    """Cancel the current user's subscription.
    
    By default, cancels at the end of the current billing period (user keeps access until then).
    Set cancel_at_period_end=false to cancel immediately.
    """
    await enforce_rate_limit(http_request, ctx.user_id)
    
    success = await service.cancel_subscription(
        user_id=ctx.user_id,
        cancel_at_period_end=body.cancel_at_period_end
    )
    
    if not success:
        raise NotFoundError("No active subscription found")
    
    # Get updated subscription
    subscription = await service.get_user_subscription(ctx.user_id)
    
    message = (
        "Subscription will be cancelled at the end of your billing period"
        if body.cancel_at_period_end
        else "Subscription cancelled immediately"
    )
    
    return CancelSubscriptionResponse(
        success=True,
        message=message,
        subscription=_subscription_response(subscription) if subscription else None
    )
