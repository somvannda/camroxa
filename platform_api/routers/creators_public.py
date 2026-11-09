"""Public creator directory and creator pages."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from platform_api.exceptions import NotFoundError
from platform_api.services.creator_profile_service import CreatorProfileService

router = APIRouter(prefix="/creators", tags=["creators-public"])


async def _get_creator_service() -> CreatorProfileService:
    raise NotImplementedError("CreatorProfileService dependency not configured.")


CreatorServiceDep = Annotated[CreatorProfileService, Depends(_get_creator_service)]


class CreatorStats(BaseModel):
    followers: int = 0
    monthly_listeners: int = 0
    releases: int = 0
    valid_streams: int = 0


class CreatorLink(BaseModel):
    label: str
    url: str


class CreatorPublicProfile(BaseModel):
    handle: str
    display_name: str
    tagline: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    country_code: str | None = None
    city: str | None = None
    genres: list[str] = Field(default_factory=list)
    influences: list[str] = Field(default_factory=list)
    links: list[CreatorLink] = Field(default_factory=list)
    ai_disclosure: str = "none"
    tier: str = "creator"
    badges: list[str] = Field(default_factory=list)
    support_enabled: bool = False
    joined_at: datetime | None = None
    stats: CreatorStats = Field(default_factory=CreatorStats)
    is_following: bool = False


class CreatorListResponse(BaseModel):
    items: list[CreatorPublicProfile]
    total: int
    limit: int
    offset: int


@router.get("", response_model=CreatorListResponse)
async def list_creators(
    service: CreatorServiceDep,
    q: str | None = Query(default=None, max_length=80),
    genre: str | None = Query(default=None, max_length=60),
    country: str | None = Query(default=None, max_length=2),
    verified_only: bool = False,
    sort: str = Query(default="followers", pattern="^(followers|newest|name)$"),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CreatorListResponse:
    payload = await service.list_public(
        q=q,
        genre=genre,
        country=country,
        verified_only=verified_only,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return CreatorListResponse.model_validate(payload)


@router.get("/{handle}", response_model=CreatorPublicProfile)
async def get_creator(handle: str, service: CreatorServiceDep) -> CreatorPublicProfile:
    payload = await service.get_public(handle)
    if payload is None:
        raise NotFoundError("Creator not found.")
    if "redirect" in payload:
        return RedirectResponse(
            url=f"/api/v3/creators/{payload['redirect']}",
            status_code=308,
        )
    return CreatorPublicProfile.model_validate(payload)
