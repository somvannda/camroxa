"""Authenticated Creator Studio identity endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.creators_public import CreatorLink, CreatorPublicProfile
from platform_api.services.creator_profile_service import CreatorProfileService

router = APIRouter(prefix="/creator", tags=["creator-studio"])


async def _get_creator_service() -> CreatorProfileService:
    raise NotImplementedError("CreatorProfileService dependency not configured.")


CreatorServiceDep = Annotated[CreatorProfileService, Depends(_get_creator_service)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


class CreatorStudioProfile(CreatorPublicProfile):
    user_id: str
    payout_currency: str = "USD"
    status: str = "active"
    pronouns: str | None = None
    program_joined_at: datetime | None = None


class CreatorChecklist(BaseModel):
    handle: bool = False
    display_name: bool = False
    bio: bool = False
    avatar: bool = False
    genre: bool = False
    first_release: bool = False
    verified: bool = False
    payout_ready: bool = False


class CreatorStudioResponse(BaseModel):
    profile: CreatorStudioProfile | None = None
    checklist: CreatorChecklist


class ClaimCreatorRequest(BaseModel):
    handle: str = Field(..., min_length=3, max_length=30)
    display_name: str = Field(..., min_length=1, max_length=50)
    tagline: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    links: list[CreatorLink] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    influences: list[str] = Field(default_factory=list)
    pronouns: str | None = Field(default=None, max_length=20)
    ai_disclosure: Literal["none", "ai_assisted", "ai_artist"] = "none"
    support_enabled: bool = False
    payout_currency: Literal["USD", "KHR"] = "USD"


class UpdateCreatorRequest(BaseModel):
    handle: str | None = Field(default=None, min_length=3, max_length=30)
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    tagline: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    links: list[CreatorLink] | None = None
    genres: list[str] | None = None
    influences: list[str] | None = None
    pronouns: str | None = Field(default=None, max_length=20)
    ai_disclosure: Literal["none", "ai_assisted", "ai_artist"] | None = None
    support_enabled: bool | None = None
    payout_currency: Literal["USD", "KHR"] | None = None


class HandleAvailabilityResponse(BaseModel):
    handle: str
    available: bool
    reason: str | None = None
    suggestions: list[str] = Field(default_factory=list)


@router.get("/me", response_model=CreatorStudioResponse)
async def get_my_creator_profile(
    ctx: CurrentUserDep, service: CreatorServiceDep
) -> CreatorStudioResponse:
    payload = await service.get_studio(ctx.user_id)
    return CreatorStudioResponse.model_validate(payload)


@router.post("/claim", response_model=CreatorStudioResponse, status_code=201)
async def claim_creator_profile(
    body: ClaimCreatorRequest,
    ctx: CurrentUserDep,
    service: CreatorServiceDep,
) -> CreatorStudioResponse:
    payload = await service.claim(ctx.user_id, body.model_dump(exclude_unset=True))
    return CreatorStudioResponse.model_validate(payload)


@router.patch("/me", response_model=CreatorStudioResponse)
async def update_my_creator_profile(
    body: UpdateCreatorRequest,
    ctx: CurrentUserDep,
    service: CreatorServiceDep,
) -> CreatorStudioResponse:
    payload = await service.update(ctx.user_id, body.model_dump(exclude_unset=True))
    return CreatorStudioResponse.model_validate(payload)


@router.get("/handle-available", response_model=HandleAvailabilityResponse)
async def check_handle(
    service: CreatorServiceDep,
    handle: str = Query(..., min_length=1, max_length=30),
) -> HandleAvailabilityResponse:
    return HandleAvailabilityResponse.model_validate(await service.availability(handle))
