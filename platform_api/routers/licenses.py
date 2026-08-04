"""Licenses router endpoints.

Provides Admin endpoints for license CRUD (create, assign, revoke)
and a User endpoint for validating their active license.

Requirements: 4.1, 4.2, 4.3, 4.5
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus
from platform_api.repositories.license_repo import LicenseRepository, PlanRepository
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.services.credit_units import units_to_credits
from platform_api.services.plan_tier_pricing_service import (
    PROFILE_ADDON_STEP,
    find_profile_addon_plan,
    find_two_channel_monthly_base,
    linear_plan_monthly_from_base,
    max_profile_addon_slots,
    quote_profile_addon_for_subscription,
    quote_profile_addon_from_plan,
)
from platform_api.services.subscription_entitlement_service import (
    effective_profile_creation_allowance,
    effective_quota_channels,
    validate_profile_addon_reduction,
    validate_profile_addon_request,
)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/licenses", tags=["licenses"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateLicenseRequest(BaseModel):
    """Body for creating a new unassigned license."""

    plan_id: str = Field(..., description="UUID of the plan to associate with the license")


class AssignLicenseRequest(BaseModel):
    """Body for assigning a license to a user."""

    user_id: str = Field(..., description="UUID of the user to assign the license to")


class LicenseResponse(BaseModel):
    """Response model for license information."""

    id: str
    license_key: str
    plan_id: str
    user_id: str | None = None
    status: str
    profile_addon_slots: int = 0
    profile_addon_pending: int = 0
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class UpdateProfileAddonSlotsRequest(BaseModel):
    """Admin request to grant or set profile add-on slots."""

    profile_addon_pending: int | None = Field(
        default=None,
        ge=0,
        le=8,
        description="Absolute pending add-on slots awaiting onboarding",
    )
    profile_addon_slots: int | None = Field(
        default=None,
        ge=0,
        le=8,
        description="Absolute active add-on slots (quotas apply)",
    )
    add_channels: int | None = Field(
        default=None,
        ge=2,
        le=8,
        description="Grant +N pending channels (admin bypass, multiples of 2)",
    )


class ProfileAddonQuoteResponse(BaseModel):
    """Quote for purchasing +2 channel profile add-ons."""

    current_channels: int
    addon_channels: int
    new_total_channels: int
    monthly_addon_cents: int
    capped_by_tier: bool
    next_tier_channels: int | None = None
    next_tier_monthly_cents: int | None = None
    max_addon_channels_remaining: int
    base_monthly_cents: int
    base_plan_channels: int
    addon_plan_id: str | None = None


class ValidateLicenseResponse(BaseModel):
    """Response model for license validation — returns active plan details."""

    plan_type: str
    profile_allowance: int
    profile_addon_slots: int = 0
    profile_addon_pending: int = 0
    effective_profile_allowance: int
    effective_quota_channels: int = 0
    monthly_song_quota: int | None = None
    songs_remaining: int | None = None
    monthly_image_quota: int | None = None
    images_remaining: int | None = None
    daily_song_limit_per_channel: int | None = None
    daily_image_limit_per_channel: int | None = None
    wallet_balance: float = 0
    expiration_date: datetime | None = None


# ---------------------------------------------------------------------------
# Placeholder Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_license_repo() -> LicenseRepository:
    """Placeholder dependency for LicenseRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "LicenseRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_plan_repo() -> PlanRepository:
    """Placeholder dependency for PlanRepository — override in tests or dependencies.py."""
    raise NotImplementedError(
        "PlanRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_credit_repo() -> CreditRepository:
    raise NotImplementedError(
        "CreditRepository dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
LicenseRepoDep = Annotated[LicenseRepository, Depends(_get_license_repo)]
PlanRepoDep = Annotated[PlanRepository, Depends(_get_plan_repo)]
CreditRepoDep = Annotated[CreditRepository, Depends(_get_credit_repo)]
AdminDep = Annotated[AuthContext, Depends(require_admin)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _license_to_response(license: License) -> LicenseResponse:
    """Convert a domain License to the response model."""
    return LicenseResponse(
        id=str(license.id),
        license_key=license.license_key,
        plan_id=str(license.plan_id),
        user_id=str(license.user_id) if license.user_id else None,
        status=license.status.value if hasattr(license.status, "value") else str(license.status),
        profile_addon_slots=int(getattr(license, "profile_addon_slots", 0) or 0),
        profile_addon_pending=int(getattr(license, "profile_addon_pending", 0) or 0),
        activated_at=license.activated_at,
        expires_at=license.expires_at,
        revoked_at=license.revoked_at,
        created_at=license.created_at,
    )


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------


class PaginatedLicensesResponse(BaseModel):
    """Paginated list of licenses for admin."""
    items: list[LicenseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get(
    "",
    response_model=PaginatedLicensesResponse,
    status_code=200,
    summary="List all licenses (Admin)",
)
async def list_licenses(
    ctx: AdminDep,
    license_repo: LicenseRepoDep,
    page: int = 1,
    page_size: int = 25,
    status: str | None = None,
) -> PaginatedLicensesResponse:
    """Return a paginated list of all licenses."""
    from fastapi import Query as Q
    licenses, total = await license_repo.get_all_paginated(
        page=page, page_size=page_size, status=status
    )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedLicensesResponse(
        items=[_license_to_response(lic) for lic in licenses],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "",
    response_model=LicenseResponse,
    status_code=201,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "Plan not found"},
    },
    summary="Create a new unassigned license (Admin)",
)
async def create_license(
    request: CreateLicenseRequest,
    ctx: AdminDep,
    license_repo: LicenseRepoDep,
    plan_repo: PlanRepoDep,
) -> LicenseResponse:
    """Create a new unassigned license for the specified plan.

    Requirement 4.3: Generates a unique license key and stores it with
    the specified plan type and activation parameters.
    """
    plan_id = UUID(request.plan_id)

    # Verify the plan exists
    plan = await plan_repo.get_by_id(plan_id)
    if plan is None:
        raise NotFoundError(message="Plan not found.", details={"plan_id": request.plan_id})

    license = await license_repo.create(plan_id)
    return _license_to_response(license)


@router.post(
    "/{license_id}/assign",
    response_model=LicenseResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "License not found"},
        409: {"description": "User already has an active license for this plan"},
    },
    summary="Assign a license to a user (Admin)",
)
async def assign_license(
    license_id: UUID,
    request: AssignLicenseRequest,
    ctx: AdminDep,
    license_repo: LicenseRepoDep,
    plan_repo: PlanRepoDep,
) -> LicenseResponse:
    """Assign an unassigned license to a user.

    Requirement 4.4: Associates the license key with the user account and
    activates the corresponding plan. Rejects if the user already has an
    active license of the same plan type (Requirement 4.9).
    """
    # Verify the license exists
    license = await license_repo.get_by_id(license_id)
    if license is None:
        raise NotFoundError(
            message="License not found.", details={"license_id": str(license_id)}
        )

    # Verify the license is unassigned
    if license.status != LicenseStatus.UNASSIGNED:
        raise ValidationError(
            message="License is not in unassigned state.",
            details={"current_status": str(license.status)},
        )

    user_id = UUID(request.user_id)

    # Check for duplicate plan assignment (Requirement 4.9)
    has_duplicate = await license_repo.has_duplicate_plan(user_id, license.plan_id)
    if has_duplicate:
        raise DuplicateError(
            message="User already has an active license for this plan type.",
            details={"user_id": request.user_id, "plan_id": str(license.plan_id)},
        )

    # Get the plan for expiration calculation
    plan = await plan_repo.get_by_id(license.plan_id)
    if plan is None:
        raise NotFoundError(
            message="Associated plan not found.", details={"plan_id": str(license.plan_id)}
        )

    updated_license = await license_repo.assign_to_user(license_id, user_id, plan)
    return _license_to_response(updated_license)


@router.post(
    "/{license_id}/revoke",
    response_model=LicenseResponse,
    status_code=200,
    responses={
        403: {"description": "Forbidden — non-admin access"},
        404: {"description": "License not found"},
    },
    summary="Revoke a license (Admin)",
)
async def revoke_license(
    license_id: UUID,
    ctx: AdminDep,
    license_repo: LicenseRepoDep,
) -> LicenseResponse:
    """Revoke an active license.

    Requirement 4.7: Marks the license as revoked, deactivates the
    associated plan for that user.
    """
    # Verify the license exists
    license = await license_repo.get_by_id(license_id)
    if license is None:
        raise NotFoundError(
            message="License not found.", details={"license_id": str(license_id)}
        )

    revoked = await license_repo.revoke(license_id)
    if not revoked:
        raise ValidationError(
            message="License could not be revoked (already revoked or not found).",
            details={"license_id": str(license_id)},
        )

    # Re-fetch the updated license
    updated_license = await license_repo.get_by_id(license_id)
    return _license_to_response(updated_license)  # type: ignore[arg-type]


@router.patch(
    "/{license_id}/profile-addon-slots",
    response_model=LicenseResponse,
    status_code=200,
    summary="Set profile add-on slots on a license (Admin)",
)
async def update_profile_addon_slots(
    license_id: UUID,
    request: UpdateProfileAddonSlotsRequest,
    ctx: AdminDep,
    license_repo: LicenseRepoDep,
    plan_repo: PlanRepoDep,
) -> LicenseResponse:
    """Grant pending +2 channel add-ons (admin bypass — user completes onboarding)."""
    license_obj = await license_repo.get_by_id(license_id)
    if license_obj is None:
        raise NotFoundError(
            message="License not found.", details={"license_id": str(license_id)}
        )

    plan = await plan_repo.get_by_id(license_obj.plan_id)
    if plan is None:
        raise NotFoundError(
            message="Associated plan not found.",
            details={"plan_id": str(license_obj.plan_id)},
        )

    current_slots = int(getattr(license_obj, "profile_addon_slots", 0) or 0)
    current_pending = int(getattr(license_obj, "profile_addon_pending", 0) or 0)
    provided = [
        request.profile_addon_pending is not None,
        request.profile_addon_slots is not None,
        request.add_channels is not None,
    ]
    if sum(provided) != 1:
        raise ValidationError(
            message="Provide exactly one of profile_addon_pending, profile_addon_slots, or add_channels.",
            details={"allowed_fields": ["profile_addon_pending", "profile_addon_slots", "add_channels"]},
        )

    if request.add_channels is not None:
        if request.add_channels % PROFILE_ADDON_STEP != 0:
            raise ValidationError(
                message=f"Profile add-ons must be purchased in multiples of {PROFILE_ADDON_STEP}.",
                details={"add_channels": request.add_channels},
            )
        try:
            validate_profile_addon_request(
                plan=plan,
                current_addon_slots=current_slots,
                current_addon_pending=current_pending,
                add_channels=request.add_channels,
            )
        except ValueError as exc:
            raise ValidationError(message=str(exc), details={"add_channels": request.add_channels}) from exc
        updated = await license_repo.add_profile_addon_pending(license_id, request.add_channels)
    elif request.profile_addon_pending is not None:
        new_pending = int(request.profile_addon_pending)
        if new_pending % PROFILE_ADDON_STEP != 0:
            raise ValidationError(
                message=f"profile_addon_pending must be a multiple of {PROFILE_ADDON_STEP}.",
                details={"profile_addon_pending": new_pending},
            )
        delta = new_pending - current_pending
        if delta > 0:
            try:
                validate_profile_addon_request(
                    plan=plan,
                    current_addon_slots=current_slots,
                    current_addon_pending=current_pending,
                    add_channels=delta,
                )
            except ValueError as exc:
                raise ValidationError(message=str(exc), details={"profile_addon_pending": new_pending}) from exc
        elif delta < 0 and license_obj.user_id is not None:
            from platform_api.dependencies import get_profile_service

            profile_service = get_profile_service()
            profiles = await profile_service.list_profiles(license_obj.user_id)
            try:
                validate_profile_addon_reduction(
                    plan=plan,
                    profile_count=len(profiles),
                    current_addon_slots=current_slots,
                    current_addon_pending=current_pending,
                    new_addon_pending=new_pending,
                )
            except ValueError as exc:
                raise ValidationError(
                    message=str(exc),
                    details={"profile_addon_pending": new_pending},
                ) from exc
        updated = await license_repo.set_profile_addon_pending(license_id, new_pending)
    else:
        new_slots = int(request.profile_addon_slots or 0)
        if new_slots % PROFILE_ADDON_STEP != 0:
            raise ValidationError(
                message=f"profile_addon_slots must be a multiple of {PROFILE_ADDON_STEP}.",
                details={"profile_addon_slots": new_slots},
            )
        if new_slots < current_slots and license_obj.user_id is not None:
            from platform_api.dependencies import get_profile_service

            profile_service = get_profile_service()
            profiles = await profile_service.list_profiles(license_obj.user_id)
            try:
                validate_profile_addon_reduction(
                    plan=plan,
                    profile_count=len(profiles),
                    current_addon_slots=current_slots,
                    current_addon_pending=current_pending,
                    new_addon_slots=new_slots,
                )
            except ValueError as exc:
                raise ValidationError(
                    message=str(exc),
                    details={"profile_addon_slots": new_slots},
                ) from exc
        updated = await license_repo.set_profile_addon_slots(license_id, new_slots)

    if updated is None:
        raise NotFoundError(
            message="License not found.", details={"license_id": str(license_id)}
        )
    return _license_to_response(updated)


@router.post(
    "/complete-addon-onboarding",
    response_model=LicenseResponse,
    status_code=200,
    summary="Activate pending add-on slots after onboarding",
)
async def complete_addon_onboarding(
    ctx: CurrentUserDep,
    license_repo: LicenseRepoDep,
    plan_repo: PlanRepoDep,
) -> LicenseResponse:
    """Move pending add-on slots to active after the user creates 2 profiles."""
    user_id = UUID(ctx.user_id)
    license_obj = await license_repo.get_active_for_user(user_id)
    if license_obj is None:
        raise NotFoundError(message="No active license found.", details={"user_id": ctx.user_id})

    pending = int(getattr(license_obj, "profile_addon_pending", 0) or 0)
    if pending < PROFILE_ADDON_STEP:
        raise ValidationError(
            message="No pending add-on bundle to activate.",
            details={"profile_addon_pending": pending},
        )

    plan = await plan_repo.get_by_id(license_obj.plan_id)
    if plan is None:
        raise NotFoundError(message="Associated plan not found.")

    from platform_api.dependencies import get_profile_service

    profile_service = get_profile_service()
    profiles = await profile_service.list_profiles(user_id)
    profile_count = len(profiles)
    required = effective_profile_creation_allowance(
        plan,
        int(license_obj.profile_addon_slots or 0),
        pending - PROFILE_ADDON_STEP,
    )
    if profile_count < required:
        raise ValidationError(
            message="Create your new channel profiles before activating add-on quotas.",
            details={
                "profile_count": profile_count,
                "required_profiles": required,
            },
        )

    updated = await license_repo.activate_profile_addon_pending(
        license_obj.id,
        PROFILE_ADDON_STEP,
    )
    if updated is None:
        raise NotFoundError(message="License not found.")
    return _license_to_response(updated)


# ---------------------------------------------------------------------------
# User Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/profile-addon-quote",
    response_model=ProfileAddonQuoteResponse,
    status_code=200,
    summary="Quote profile add-on pricing for the current user",
)
async def get_my_profile_addon_quote(
    ctx: CurrentUserDep,
    license_repo: LicenseRepoDep,
    plan_repo: PlanRepoDep,
    addon_channels: int = PROFILE_ADDON_STEP,
    pool: Any = Depends(get_db_pool),
) -> ProfileAddonQuoteResponse:
    """Return add-on pricing based on the user's active subscription."""
    if addon_channels % PROFILE_ADDON_STEP != 0:
        raise ValidationError(
            message=f"Profile add-ons must be purchased in multiples of {PROFILE_ADDON_STEP}.",
            details={"addon_channels": addon_channels},
        )

    user_id = UUID(ctx.user_id)
    license_obj = await license_repo.get_active_for_user(user_id)
    if license_obj is None:
        raise NotFoundError(
            message="No active license found for this user.",
            details={"user_id": ctx.user_id},
        )

    plan = await plan_repo.get_by_id(license_obj.plan_id)
    if plan is None:
        raise NotFoundError(
            message="Associated plan not found.",
            details={"plan_id": str(license_obj.plan_id)},
        )

    current_channels = effective_quota_channels(
        plan,
        int(getattr(license_obj, "profile_addon_slots", 0) or 0),
    )
    all_plans = await plan_repo.get_all()
    billing_cycle_days = int(plan.billing_cycle_days or 30)
    addon_plan = find_profile_addon_plan(
        all_plans,
        addon_channels,
        billing_cycle_days=billing_cycle_days,
    )
    if addon_plan is None:
        raise NotFoundError(
            message=f"No active profile add-on plan found for +{addon_channels} channels.",
            details={"addon_channels": addon_channels, "billing_cycle_days": billing_cycle_days},
        )
    from platform_api.services.plan_term_discount_service import load_plan_term_discounts

    discounts = await load_plan_term_discounts(pool)
    quote = quote_profile_addon_for_subscription(
        current_channels=current_channels,
        addon_channels=addon_channels,
        addon_plan=addon_plan,
        subscription_billing_cycle_days=billing_cycle_days,
        semi_annual_discount_percent=discounts.semi_annual_discount_percent,
        annual_discount_percent=discounts.annual_discount_percent,
    )
    from platform_api.services.plan_tier_pricing_service import MAX_ACCOUNT_CHANNELS

    used = (
        int(plan.profile_allowance or 0)
        + int(getattr(license_obj, "profile_addon_slots", 0) or 0)
        + int(getattr(license_obj, "profile_addon_pending", 0) or 0)
    )
    remaining = max(0, MAX_ACCOUNT_CHANNELS - used)
    remaining -= remaining % PROFILE_ADDON_STEP
    base_plan = find_two_channel_monthly_base(all_plans)

    return ProfileAddonQuoteResponse(
        current_channels=quote.current_channels,
        addon_channels=quote.addon_channels,
        new_total_channels=quote.new_total_channels,
        monthly_addon_cents=quote.monthly_addon_cents,
        capped_by_tier=quote.capped_by_tier,
        next_tier_channels=quote.next_tier_channels,
        next_tier_monthly_cents=quote.next_tier_monthly_cents,
        max_addon_channels_remaining=remaining,
        base_monthly_cents=int(base_plan.price_cents) if base_plan is not None else int(addon_plan.price_cents),
        base_plan_channels=int(base_plan.profile_allowance) if base_plan is not None else 2,
        addon_plan_id=str(addon_plan.id),
    )


@router.get(
    "/validate",
    response_model=ValidateLicenseResponse,
    status_code=200,
    responses={
        401: {"description": "Invalid or missing token"},
        404: {"description": "No active license found"},
    },
    summary="Validate current user's license",
)
async def validate_license(
    ctx: CurrentUserDep,
    license_repo: LicenseRepoDep,
    plan_repo: PlanRepoDep,
    credit_repo: CreditRepoDep,
) -> ValidateLicenseResponse:
    """Validate the current user's active license and return plan details.

    Requirement 4.5: Returns plan type, profile allowance, monthly song quota,
    songs remaining in current period, wallet balance, and expiration date.
    """
    user_id = UUID(ctx.user_id)

    wallet_balance_units = await credit_repo.get_balance(user_id)
    wallet_balance = units_to_credits(wallet_balance_units)

    # Find the user's active license
    license = await license_repo.get_active_for_user(user_id)
    if license is None:
        trial_plan = await plan_repo.get_by_name("Trial")
        if trial_plan is None:
            trial_plan = await plan_repo.get_by_name("trial")
        if trial_plan is None:
            raise NotFoundError(
                message="No active license found for this user.",
                details={"user_id": ctx.user_id},
            )

        return ValidateLicenseResponse(
            plan_type=trial_plan.name,
            profile_allowance=trial_plan.profile_allowance,
            profile_addon_slots=0,
            effective_profile_allowance=trial_plan.profile_allowance,
            monthly_song_quota=trial_plan.monthly_song_limit,
            songs_remaining=trial_plan.monthly_song_limit,
            monthly_image_quota=trial_plan.monthly_image_limit,
            images_remaining=trial_plan.monthly_image_limit,
            daily_song_limit_per_channel=trial_plan.daily_song_limit_per_channel,
            daily_image_limit_per_channel=trial_plan.daily_image_limit_per_channel,
            wallet_balance=wallet_balance,
            expiration_date=None,
        )

    # Get the associated plan
    plan = await plan_repo.get_by_id(license.plan_id)
    if plan is None:
        raise NotFoundError(
            message="Associated plan not found.",
            details={"plan_id": str(license.plan_id)},
        )

    # Calculate songs remaining in current period (usage_tracking is authoritative)
    from platform_api.dependencies import get_usage_tracking_repo
    from platform_api.services.quota_display_service import get_monthly_quota_status

    usage_repo = get_usage_tracking_repo()
    songs_quota, songs_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="songs",
    )
    if songs_quota is None and plan.monthly_song_limit is not None:
        songs_quota = int(plan.monthly_song_limit)
        songs_remaining = songs_quota

    images_quota, images_remaining = await get_monthly_quota_status(
        user_id=user_id,
        plan_repo=plan_repo,
        usage_repo=usage_repo,
        quota_field="images",
    )
    if images_quota is None and plan.monthly_image_limit is not None:
        images_quota = int(plan.monthly_image_limit)
        images_remaining = images_quota

    addon_slots = int(getattr(license, "profile_addon_slots", 0) or 0)
    addon_pending = int(getattr(license, "profile_addon_pending", 0) or 0)
    quota_channels = effective_quota_channels(plan, addon_slots)
    creation_allowance = effective_profile_creation_allowance(plan, addon_slots, addon_pending)

    return ValidateLicenseResponse(
        plan_type=plan.name,
        profile_allowance=plan.profile_allowance,
        profile_addon_slots=addon_slots,
        profile_addon_pending=addon_pending,
        effective_profile_allowance=creation_allowance,
        effective_quota_channels=quota_channels,
        monthly_song_quota=plan.monthly_song_limit,
        songs_remaining=songs_remaining,
        monthly_image_quota=plan.monthly_image_limit,
        images_remaining=images_remaining,
        daily_song_limit_per_channel=plan.daily_song_limit_per_channel,
        daily_image_limit_per_channel=plan.daily_image_limit_per_channel,
        wallet_balance=wallet_balance,
        expiration_date=license.expires_at,
    )
