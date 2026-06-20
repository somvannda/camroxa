"""Licenses router endpoints.

Provides Admin endpoints for license CRUD (create, assign, revoke)
and a User endpoint for validating their active license.

Requirements: 4.1, 4.2, 4.3, 4.5
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus
from platform_api.repositories.license_repo import LicenseRepository, PlanRepository

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
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class ValidateLicenseResponse(BaseModel):
    """Response model for license validation — returns active plan details."""

    plan_type: str
    profile_allowance: int
    monthly_song_quota: int | None = None
    songs_remaining: int | None = None
    wallet_balance: int = 0
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


# Type aliases for dependency injection
LicenseRepoDep = Annotated[LicenseRepository, Depends(_get_license_repo)]
PlanRepoDep = Annotated[PlanRepository, Depends(_get_plan_repo)]
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


# ---------------------------------------------------------------------------
# User Endpoints
# ---------------------------------------------------------------------------


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
) -> ValidateLicenseResponse:
    """Validate the current user's active license and return plan details.

    Requirement 4.5: Returns plan type, profile allowance, monthly song quota,
    songs remaining in current period, wallet balance, and expiration date.
    """
    user_id = UUID(ctx.user_id)

    # Find the user's active license
    license = await license_repo.get_active_for_user(user_id)
    if license is None:
        raise NotFoundError(
            message="No active license found for this user.",
            details={"user_id": ctx.user_id},
        )

    # Get the associated plan
    plan = await plan_repo.get_by_id(license.plan_id)
    if plan is None:
        raise NotFoundError(
            message="Associated plan not found.",
            details={"plan_id": str(license.plan_id)},
        )

    # Calculate songs remaining in current period
    songs_remaining: int | None = None
    if plan.monthly_song_quota is not None and license.id is not None:
        current_usage = await plan_repo.get_current_usage(user_id, license.id)
        songs_remaining = max(0, plan.monthly_song_quota - current_usage)

    # Note: wallet_balance would come from the credit repo in full implementation.
    # For now, we return 0 as placeholder — will be wired when credit service is available.
    return ValidateLicenseResponse(
        plan_type=plan.name,
        profile_allowance=plan.profile_allowance,
        monthly_song_quota=plan.monthly_song_quota,
        songs_remaining=songs_remaining,
        wallet_balance=0,
        expiration_date=license.expires_at,
    )
