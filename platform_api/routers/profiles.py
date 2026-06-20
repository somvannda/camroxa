"""Channel profiles router endpoints.

Provides channel profile CRUD for authenticated users and an admin-only
stats endpoint for per-profile usage aggregation.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.services.profile_service import ProfileService

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/profiles", tags=["profiles"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ProfileResponse(BaseModel):
    """Public channel profile information."""

    id: str
    user_id: str
    name: str
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str
    image_config: dict[str, Any] = Field(default_factory=dict)
    youtube_config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CreateProfileRequest(BaseModel):
    """Request body for creating a new channel profile."""

    name: str = Field(..., min_length=1, max_length=100)
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str = "1920x1080"
    image_config: dict[str, Any] = Field(default_factory=dict)
    youtube_config: dict[str, Any] = Field(default_factory=dict)


class UpdateProfileRequest(BaseModel):
    """Request body for updating an existing channel profile."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str | None = None
    image_config: dict[str, Any] | None = None
    youtube_config: dict[str, Any] | None = None


class ProfileStatsResponse(BaseModel):
    """Admin-only per-profile usage statistics."""

    profile_id: str
    batches_generated: int
    songs_produced: int
    credits_consumed: int


# ---------------------------------------------------------------------------
# Dependency Protocols & Stubs
# ---------------------------------------------------------------------------


class ProfileStatsPort(Protocol):
    """Protocol for retrieving aggregate profile statistics (Admin)."""

    async def get_profile_stats(self, profile_id: UUID) -> dict[str, int]:
        """Return aggregate stats for a profile.

        Returns:
            Dict with keys: batches_generated, songs_produced, credits_consumed.
        """
        ...


async def _get_profile_service() -> ProfileService:
    """Placeholder dependency for ProfileService — override in tests or dependencies.py."""
    raise NotImplementedError(
        "ProfileService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_profile_stats_port() -> ProfileStatsPort:
    """Placeholder dependency for ProfileStatsPort — override in tests or dependencies.py."""
    raise NotImplementedError(
        "ProfileStatsPort dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
ProfileServiceDep = Annotated[ProfileService, Depends(_get_profile_service)]
ProfileStatsDep = Annotated[ProfileStatsPort, Depends(_get_profile_stats_port)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
AdminUserDep = Annotated[AuthContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_to_response(profile) -> ProfileResponse:
    """Convert a ChannelProfile domain object to the response model."""
    return ProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        name=profile.name,
        folder_name=profile.folder_name,
        run_prefix=profile.run_prefix,
        logo_path=profile.logo_path,
        video_template_id=profile.video_template_id,
        reel_template_id=profile.reel_template_id,
        output_resolution=profile.output_resolution,
        image_config=profile.image_config,
        youtube_config=profile.youtube_config,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


# ---------------------------------------------------------------------------
# User Endpoints (authenticated)
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[ProfileResponse],
    status_code=200,
    summary="List channel profiles",
)
async def list_profiles(
    ctx: CurrentUserDep,
    profile_service: ProfileServiceDep,
) -> list[ProfileResponse]:
    """Return all channel profiles for the authenticated user, ordered by name ascending.

    Requirement 8.7: List profiles ordered by name ascending.
    """
    profiles = await profile_service.list_profiles(UUID(ctx.user_id))
    return [_profile_to_response(p) for p in profiles]


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=201,
    summary="Create a channel profile",
)
async def create_profile(
    request: CreateProfileRequest,
    ctx: CurrentUserDep,
    profile_service: ProfileServiceDep,
) -> ProfileResponse:
    """Create a new channel profile for the authenticated user.

    Requirement 8.1: Enforce profile count limits based on plan.
    Requirement 8.2: Validate name uniqueness per user, max 100 chars.
    Requirement 8.4: Reject creation beyond limit with profile-limit-exceeded error.
    """
    profile = await profile_service.create_profile(
        user_id=UUID(ctx.user_id),
        name=request.name,
        folder_name=request.folder_name,
        run_prefix=request.run_prefix,
        logo_path=request.logo_path,
        video_template_id=request.video_template_id,
        reel_template_id=request.reel_template_id,
        output_resolution=request.output_resolution,
        image_config=request.image_config,
        youtube_config=request.youtube_config,
    )
    return _profile_to_response(profile)


@router.put(
    "/{profile_id}",
    response_model=ProfileResponse,
    status_code=200,
    summary="Update a channel profile",
)
async def update_profile(
    profile_id: UUID,
    request: UpdateProfileRequest,
    ctx: CurrentUserDep,
    profile_service: ProfileServiceDep,
) -> ProfileResponse:
    """Update an existing channel profile belonging to the authenticated user.

    Requirement 8.3: Persist updated fields, return updated record within 2 seconds.
    Requirement 8.5: Return not-found error for non-existent or other user's profiles.
    """
    # Build update dict from non-None fields
    fields: dict[str, Any] = {}
    if request.name is not None:
        fields["name"] = request.name
    if request.folder_name is not None:
        fields["folder_name"] = request.folder_name
    if request.run_prefix is not None:
        fields["run_prefix"] = request.run_prefix
    if request.logo_path is not None:
        fields["logo_path"] = request.logo_path
    if request.video_template_id is not None:
        fields["video_template_id"] = request.video_template_id
    if request.reel_template_id is not None:
        fields["reel_template_id"] = request.reel_template_id
    if request.output_resolution is not None:
        fields["output_resolution"] = request.output_resolution
    if request.image_config is not None:
        fields["image_config"] = request.image_config
    if request.youtube_config is not None:
        fields["youtube_config"] = request.youtube_config

    profile = await profile_service.update_profile(
        user_id=UUID(ctx.user_id),
        profile_id=profile_id,
        **fields,
    )
    return _profile_to_response(profile)


@router.delete(
    "/{profile_id}",
    status_code=200,
    summary="Delete a channel profile",
)
async def delete_profile(
    profile_id: UUID,
    ctx: CurrentUserDep,
    profile_service: ProfileServiceDep,
) -> dict[str, str]:
    """Delete a channel profile belonging to the authenticated user.

    Requirement 8.5: Return not-found error for non-existent or other user's profiles.
    Requirement 8.6: Delete dissociates from active batch assignments;
    in-progress batches continue.
    """
    await profile_service.delete_profile(
        user_id=UUID(ctx.user_id),
        profile_id=profile_id,
    )
    return {"message": f"Profile {profile_id} has been deleted."}


# ---------------------------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{profile_id}/stats",
    response_model=ProfileStatsResponse,
    status_code=200,
    summary="Get profile usage statistics (Admin)",
)
async def get_profile_stats(
    profile_id: UUID,
    ctx: AdminUserDep,
    stats_port: ProfileStatsDep,
) -> ProfileStatsResponse:
    """Return all-time usage statistics for a channel profile.

    Requirement 8.8: Admin stats endpoint returning batches generated,
    songs produced, and credits consumed per profile.
    """
    stats = await stats_port.get_profile_stats(profile_id)
    return ProfileStatsResponse(
        profile_id=str(profile_id),
        batches_generated=stats.get("batches_generated", 0),
        songs_produced=stats.get("songs_produced", 0),
        credits_consumed=stats.get("credits_consumed", 0),
    )
