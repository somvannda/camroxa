"""Channel prompts router endpoints.

Admin CRUD for channel setup prompts + public lookup for onboarding wizard.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.services.channel_prompt_service import ChannelPromptService, VALID_CATEGORIES

logger = logging.getLogger(__name__)

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


class GeneratePromptRequest(BaseModel):
    category: str = Field(..., description="title, logo, cover, description, keyword, tag")
    genre: str = Field("", description="Genre name (e.g. EDM, Hip-Hop)")
    match_key: str | None = Field(None, description="Music description match key")


class GeneratePromptResponse(BaseModel):
    content: str
    category: str


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
# AI prompt generation endpoint
# ---------------------------------------------------------------------------

_CATEGORY_DESCRIPTIONS = {
    "title": "YouTube channel name",
    "logo": "YouTube channel logo",
    "cover": "YouTube channel banner/cover art",
    "description": "YouTube channel description (SEO-optimized)",
    "keyword": "SEO keywords for a YouTube channel",
    "tag": "YouTube tags for a music channel",
}


async def _call_deepseek(prompt: str, system: str = "") -> str:
    """Call DeepSeek LLM API directly."""
    from platform_api.config import get_settings

    settings = get_settings()
    api_key = settings.deepseek_api_key
    base_url = settings.deepseek_api_base_url.rstrip("/")

    if not api_key:
        raise ValueError("DeepSeek API key not configured")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.8, "max_tokens": 1500},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


@router.post("/generate", response_model=GeneratePromptResponse)
async def generate_channel_prompt(
    request: GeneratePromptRequest,
    ctx: AuthContext = Depends(require_admin),
) -> GeneratePromptResponse:
    """Generate a channel prompt using DeepSeek AI based on category and genre."""
    category = request.category
    genre = request.genre or "music"
    desc = _CATEGORY_DESCRIPTIONS.get(category, category)

    system = (
        "You are an expert YouTube channel branding consultant and prompt engineer. "
        "Your job is to generate a high-quality system/user prompt that will be used "
        "by an AI to create channel onboarding assets.\n\n"
        "The generated prompt should:\n"
        "- Be specific to the music genre provided\n"
        "- Include clear instructions for the AI that will consume it\n"
        "- Support template variables like {channel_name} and {genre} where appropriate\n"
        "- Be detailed enough to produce professional results\n"
        "- NOT include any explanation, just the prompt text itself"
    )

    user = (
        f"Generate a prompt for creating a **{desc}** for a YouTube music channel "
        f"in the **{genre}** genre.\n\n"
        f"Requirements:\n"
        f"- The prompt will be used by an AI to generate the actual {desc}\n"
        f"- It should instruct the AI to create something professional and genre-appropriate\n"
        f"- Use {{channel_name}} as a placeholder for the channel name (where applicable)\n"
        f"- Use {{genre}} as a placeholder for the genre (where applicable)\n"
        f"- Return ONLY the prompt text, no labels or explanations\n"
    )

    content = await _call_deepseek(user, system)
    # Strip any wrapping quotes the LLM might add
    content = content.strip().strip('"').strip("'")

    return GeneratePromptResponse(content=content, category=category)


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
