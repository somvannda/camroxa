"""Channel prompts router endpoints.

Admin CRUD for channel setup prompts + public lookup for onboarding wizard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.channel_prompt_service import ChannelPromptService, VALID_CATEGORIES

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/channel-prompts", tags=["channel-prompts"])


# ---------------------------------------------------------------------------
# Dependency stub
# ---------------------------------------------------------------------------

async def _get_channel_prompt_service() -> ChannelPromptService:
    raise NotImplementedError("ChannelPromptService not configured.")


ChannelPromptServiceDep = Annotated[ChannelPromptService, Depends(_get_channel_prompt_service)]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChannelPromptResponse(BaseModel):
    id: str
    name: str
    content: str
    category: str
    genre: str
    match_key: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateChannelPromptRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(..., description="title, logo, cover, description, keyword, tag")
    genre: str = Field("", max_length=100)
    match_key: str | None = None
    is_active: bool = True


class UpdateChannelPromptRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    category: str | None = None
    genre: str | None = None
    match_key: str | None = None
    is_active: bool | None = None


class PublicChannelPromptResponse(BaseModel):
    id: str
    name: str
    content: str
    category: str
    genre: str
    match_key: str | None = None


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ChannelPromptResponse])
async def list_channel_prompts(ctx: AuthContext = Depends(require_admin), svc: ChannelPromptServiceDep = None) -> list[ChannelPromptResponse]:  # type: ignore[assignment]
    prompts = await svc.list_all()
    return [ChannelPromptResponse(id=str(p.id), name=p.name, content=p.content, category=p.category, genre=p.genre, match_key=p.match_key, is_active=p.is_active, created_at=p.created_at, updated_at=p.updated_at) for p in prompts]


@router.post("", response_model=ChannelPromptResponse, status_code=201)
async def create_channel_prompt(
    request: CreateChannelPromptRequest,
    ctx: AuthContext = Depends(require_admin),
    svc: ChannelPromptServiceDep = None,  # type: ignore[assignment]
) -> ChannelPromptResponse:
    prompt = await svc.create(name=request.name, content=request.content, category=request.category, genre=request.genre, match_key=request.match_key, is_active=request.is_active)
    return ChannelPromptResponse(id=str(prompt.id), name=prompt.name, content=prompt.content, category=prompt.category, genre=prompt.genre, match_key=prompt.match_key, is_active=prompt.is_active, created_at=prompt.created_at, updated_at=prompt.updated_at)


@router.put("/{prompt_id}", response_model=ChannelPromptResponse)
async def update_channel_prompt(
    prompt_id: UUID,
    request: UpdateChannelPromptRequest,
    ctx: AuthContext = Depends(require_admin),
    svc: ChannelPromptServiceDep = None,  # type: ignore[assignment]
) -> ChannelPromptResponse:
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    prompt = await svc.update(prompt_id, **updates)
    return ChannelPromptResponse(id=str(prompt.id), name=prompt.name, content=prompt.content, category=prompt.category, genre=prompt.genre, match_key=prompt.match_key, is_active=prompt.is_active, created_at=prompt.created_at, updated_at=prompt.updated_at)


@router.delete("/{prompt_id}", status_code=200)
async def delete_channel_prompt(
    prompt_id: UUID,
    ctx: AuthContext = Depends(require_admin),
    svc: ChannelPromptServiceDep = None,  # type: ignore[assignment]
) -> dict:
    await svc.delete(prompt_id)
    return {"message": f"Channel prompt {prompt_id} has been deleted."}


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------


@router.get("/public", response_model=list[PublicChannelPromptResponse])
async def list_public_channel_prompts(
    category: str = "",
    genre: str = "",
    svc: ChannelPromptServiceDep = None,  # type: ignore[assignment]
) -> list[PublicChannelPromptResponse]:
    """List active channel prompts for the onboarding wizard."""
    if category:
        prompts = await svc.list_by_category(category)
    else:
        prompts = await svc.list_all()
    active = [p for p in prompts if p.is_active]
    if genre:
        # Genre-specific first, then fallback to default
        genre_specific = [p for p in active if p.genre.lower() == genre.lower()]
        defaults = [p for p in active if not p.genre]
        active = genre_specific + defaults
    return [PublicChannelPromptResponse(id=str(p.id), name=p.name, content=p.content, category=p.category, genre=p.genre, match_key=p.match_key) for p in active]


@router.get("/lookup")
async def lookup_prompt(
    category: str,
    genre: str = "",
    match_key: str = "",
    svc: ChannelPromptServiceDep = None,  # type: ignore[assignment]
) -> dict:
    """Get the best matching prompt for a category, genre, and match_key."""
    mk = match_key if match_key else None
    prompt = await svc.get_best_match(category, genre, mk)
    if prompt is None:
        return {"found": False, "content": "", "name": ""}
    return {"found": True, "content": prompt.content, "name": prompt.name, "id": str(prompt.id)}
