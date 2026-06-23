"""Plans router endpoints.

Provides Admin endpoints for plan management: listing plans, updating
plan configuration, and managing promotional offers.

Requirements: 1.1, 1.2, 1.4, 4.1, 4.2, 4.10, 4.12
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.repositories.license_repo import PlanRepository
from platform_api.services.plan_validation import validate_plan_limits

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/plans", tags=["plans"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PlanResponse(BaseModel):
    """Response model for a plan configuration."""

    id: str
    name: str
    price_cents: int
    billing_cycle_days: int | None = None
    profile_allowance: int
    monthly_song_limit: int | None = None
    monthly_image_limit: int | None = None
    daily_song_limit_per_channel: int
    daily_image_limit_per_channel: int
    is_active: bool
    effective_from: datetime
    created_at: datetime
    updated_at: datetime


class UpdatePlanRequest(BaseModel):
    """Partial plan update — only provided fields are changed."""

    price_cents: int | None = Field(default=None, ge=0, description="Price in cents")
    profile_allowance: int | None = Field(default=None, ge=1, description="Max channel profiles")
    monthly_song_limit: int | None = Field(default=None, ge=0, le=100_000, description="Monthly song limit (None for unlimited)")
    monthly_image_limit: int | None = Field(default=None, ge=0, le=100_000, description="Monthly image limit (None for unlimited)")
    daily_song_limit_per_channel: int | None = Field(default=None, ge=1, le=1_000, description="Daily song limit per channel")
    daily_image_limit_per_channel: int | None = Field(default=None, ge=1, le=1_000, description="Daily image limit per channel")
    billing_cycle_days: int | None = Field(default=None, ge=1, description="Billing cycle in days")
    is_active: bool | None = Field(default=None, description="Whether the plan accepts new licenses")


class OfferResponse(BaseModel):
    """Response model for a promotional offer."""

    id: str
    plan_id: str
    promo_price_cents: int
    max_redemptions: int
    current_redemptions: int
    is_active: bool
    created_at: datetime


class CreateOfferRequest(BaseModel):
    """Body for creating a new promotional offer."""

    plan_id: str = Field(..., description="UUID of the plan this offer applies to")
    promo_price_cents: int = Field(..., ge=0, description="Promotional price in cents")
    max_redemptions: int = Field(..., ge=1, description="Maximum number of redemptions")


class CreatePlanRequest(BaseModel):
    """Body for creating a new subscription plan."""

    name: str = Field(..., min_length=1, max_length=50, description="Plan name (unique)")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    profile_allowance: int = Field(..., ge=1, description="Max channel profiles")
    monthly_song_limit: int | None = Field(default=None, ge=0, le=100_000, description="Monthly song limit (None for unlimited)")
    monthly_image_limit: int | None = Field(default=None, ge=0, le=100_000, description="Monthly image limit (None for unlimited)")
    billing_cycle_days: int | None = Field(default=None, ge=1, description="Billing cycle in days (None for lifetime)")
    daily_song_limit_per_channel: int = Field(default=7, ge=1, le=1_000, description="Daily song limit per channel")
    daily_image_limit_per_channel: int = Field(default=7, ge=1, le=1_000, description="Daily image limit per channel")


# ---------------------------------------------------------------------------
# Placeholder Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_plan_repo() -> PlanRepository:
    """Placeholder dependency for PlanRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "PlanRepository dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
PlanRepoDep = Annotated[PlanRepository, Depends(_get_plan_repo)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plan_to_response(plan: Any) -> PlanResponse:
    """Convert a domain Plan object to the response model."""
    return PlanResponse(
        id=str(plan.id),
        name=plan.name,
        price_cents=plan.price_cents,
        billing_cycle_days=plan.billing_cycle_days,
        profile_allowance=plan.profile_allowance,
        monthly_song_limit=plan.monthly_song_limit,
        monthly_image_limit=plan.monthly_image_limit,
        daily_song_limit_per_channel=plan.daily_song_limit_per_channel,
        daily_image_limit_per_channel=plan.daily_image_limit_per_channel,
        is_active=plan.is_active,
        effective_from=plan.effective_from,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[PlanResponse],
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="List all plans (Admin)",
)
async def list_plans(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> list[PlanResponse]:
    """Return all plans with their configurations.

    Requirement 4.1: Plans are stored as Admin-configurable records with
    pricing, quotas, and profile allowances.
    """
    plans = await plan_repo.get_all()
    return [_plan_to_response(p) for p in plans]


@router.post(
    "",
    response_model=PlanResponse,
    status_code=201,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        409: {"description": "Plan name already exists"},
    },
    summary="Create a new plan (Admin)",
)
async def create_plan(
    request: CreatePlanRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> PlanResponse:
    """Create a new subscription plan.

    Requirement 1.2: Validates plan limit fields before persisting.
    """
    # Validate plan limits (Requirement 1.2)
    validate_plan_limits(
        monthly_song_limit=request.monthly_song_limit,
        monthly_image_limit=request.monthly_image_limit,
        daily_song_limit_per_channel=request.daily_song_limit_per_channel,
        daily_image_limit_per_channel=request.daily_image_limit_per_channel,
    )

    plan = await plan_repo.create(
        name=request.name,
        price_cents=request.price_cents,
        profile_allowance=request.profile_allowance,
        monthly_song_limit=request.monthly_song_limit,
        monthly_image_limit=request.monthly_image_limit,
        billing_cycle_days=request.billing_cycle_days,
        daily_song_limit_per_channel=request.daily_song_limit_per_channel,
        daily_image_limit_per_channel=request.daily_image_limit_per_channel,
    )
    return _plan_to_response(plan)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Plan not found"},
    },
    summary="Update plan configuration (Admin)",
)
async def update_plan(
    plan_id: UUID,
    request: UpdatePlanRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> PlanResponse:
    """Update a plan's configuration fields.

    Requirement 1.2: Validates plan limit fields before persisting.
    Requirement 4.2: Changes are stored with an effective date and apply
    to new subscriptions. Existing active subscriptions retain original terms.

    Requirement 4.12: Setting is_active to false prevents new license creation
    for that plan; setting it to true resumes.
    """
    # Build the update dict from non-None fields
    fields: dict[str, Any] = {}
    if request.price_cents is not None:
        fields["price_cents"] = request.price_cents
    if request.profile_allowance is not None:
        fields["profile_allowance"] = request.profile_allowance
    if request.monthly_song_limit is not None:
        fields["monthly_song_limit"] = request.monthly_song_limit
    if request.monthly_image_limit is not None:
        fields["monthly_image_limit"] = request.monthly_image_limit
    if request.daily_song_limit_per_channel is not None:
        fields["daily_song_limit_per_channel"] = request.daily_song_limit_per_channel
    if request.daily_image_limit_per_channel is not None:
        fields["daily_image_limit_per_channel"] = request.daily_image_limit_per_channel
    if request.billing_cycle_days is not None:
        fields["billing_cycle_days"] = request.billing_cycle_days
    if request.is_active is not None:
        fields["is_active"] = request.is_active

    if not fields:
        raise ValidationError(
            message="No fields provided for update.",
            details={
                "allowed_fields": [
                    "price_cents",
                    "profile_allowance",
                    "monthly_song_limit",
                    "monthly_image_limit",
                    "daily_song_limit_per_channel",
                    "daily_image_limit_per_channel",
                    "billing_cycle_days",
                    "is_active",
                ]
            },
        )

    # Validate plan limits if any limit fields are being updated (Requirement 1.2)
    limit_fields_present = any(
        k in fields
        for k in (
            "monthly_song_limit",
            "monthly_image_limit",
            "daily_song_limit_per_channel",
            "daily_image_limit_per_channel",
        )
    )
    if limit_fields_present:
        # Fetch current plan to merge with partial update for validation
        current_plan = await plan_repo.get_by_id(plan_id)
        if current_plan is None:
            raise NotFoundError(message="Plan not found.", details={"plan_id": str(plan_id)})

        validate_plan_limits(
            monthly_song_limit=fields.get("monthly_song_limit", current_plan.monthly_song_limit),
            monthly_image_limit=fields.get("monthly_image_limit", current_plan.monthly_image_limit),
            daily_song_limit_per_channel=fields.get(
                "daily_song_limit_per_channel", current_plan.daily_song_limit_per_channel
            ),
            daily_image_limit_per_channel=fields.get(
                "daily_image_limit_per_channel", current_plan.daily_image_limit_per_channel
            ),
        )

    updated_plan = await plan_repo.update(plan_id, **fields)
    if updated_plan is None:
        raise NotFoundError(message="Plan not found.", details={"plan_id": str(plan_id)})

    return _plan_to_response(updated_plan)


@router.get(
    "/offers",
    response_model=list[OfferResponse],
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
    },
    summary="List active promotional offers (Admin)",
)
async def list_offers(
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> list[OfferResponse]:
    """Return all active promotional offers.

    Requirement 4.10: Admins can view and manage launch offers with
    promotional pricing and redemption limits.
    """
    # Note: The offer querying is handled via raw pool access on PlanRepository.
    # For now, we access the pool directly since PlanRepository doesn't have
    # a dedicated offer method yet. This will be refactored with a proper
    # OfferRepository in a later task.
    rows = await plan_repo._pool.fetch(
        """
        SELECT id, plan_id, promo_price_cents, max_redemptions,
               current_redemptions, is_active, created_at
        FROM plan_offers
        WHERE is_active = true
        ORDER BY created_at DESC
        """
    )
    return [
        OfferResponse(
            id=str(row["id"]),
            plan_id=str(row["plan_id"]),
            promo_price_cents=row["promo_price_cents"],
            max_redemptions=row["max_redemptions"],
            current_redemptions=row["current_redemptions"],
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.post(
    "/offers",
    response_model=OfferResponse,
    status_code=201,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Plan not found"},
    },
    summary="Create a promotional offer (Admin)",
)
async def create_offer(
    request: CreateOfferRequest,
    ctx: AdminDep,
    plan_repo: PlanRepoDep,
) -> OfferResponse:
    """Create a new promotional offer for a plan.

    Requirement 4.10: Admins can set a promotional price and maximum
    redemption count. When the count is reached, the standard price
    applies automatically.
    """
    plan_id = UUID(request.plan_id)

    # Verify the plan exists
    plan = await plan_repo.get_by_id(plan_id)
    if plan is None:
        raise NotFoundError(message="Plan not found.", details={"plan_id": request.plan_id})

    # Insert the offer
    row = await plan_repo._pool.fetchrow(
        """
        INSERT INTO plan_offers (plan_id, promo_price_cents, max_redemptions, is_active, created_at)
        VALUES ($1, $2, $3, true, NOW())
        RETURNING id, plan_id, promo_price_cents, max_redemptions,
                  current_redemptions, is_active, created_at
        """,
        plan_id,
        request.promo_price_cents,
        request.max_redemptions,
    )

    return OfferResponse(
        id=str(row["id"]),
        plan_id=str(row["plan_id"]),
        promo_price_cents=row["promo_price_cents"],
        max_redemptions=row["max_redemptions"],
        current_redemptions=row["current_redemptions"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )
