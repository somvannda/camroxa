"""Channel setup router for onboarding wizard.

Provides endpoints to generate channel names, logos, covers,
and descriptions using AI. Onboarding AI is payment-gated with
per-operation caps — no wallet credits are charged during setup.
"""

from __future__ import annotations

import base64
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.exceptions import (
    ExternalServiceError,
    PlatformAPIError,
    ValidationError,
)
from platform_api.routers.generation import GenerationServiceDep
from platform_api.services.ai_routing_service import AIRoutingService

logger = logging.getLogger(__name__)

T = TypeVar("T")

router = APIRouter(prefix="/channel-setup", tags=["channel-setup"])

# Module-level references, set by wire_dependencies
_llm_client: Any = None
_slai_client: Any = None


def set_clients(llm_client: Any, slai_client: Any) -> None:
    global _llm_client, _slai_client
    _llm_client = llm_client
    _slai_client = slai_client


_CATEGORY_VARIATION_NOTES: dict[str, list[str]] = {
    "title": [
        "Use a fresh naming angle for this run and avoid the most common genre cliches.",
        "Favor memorable brand names with a distinct tone instead of repeating familiar EDM or music channel patterns.",
        "Make the naming direction feel new and commercially brandable, not like a slight rewrite of a common channel name.",
    ],
    "logo": [
        "Take a distinct creative direction for this run with a different visual motif, accent color, and typography feel than a generic music logo.",
        "Avoid defaulting to the same common icon treatment; give this concept its own recognizable branding direction.",
        "Push for a noticeably different identity this time so the result does not feel like a repeat of a previous logo concept.",
    ],
    "cover": [
        "Choose a noticeably different composition, lighting mood, and focal story for this banner concept.",
        "Avoid repeating the same background layout or color story from typical genre cover art outputs.",
        "Give this banner a fresh visual direction with a different scene balance and atmosphere.",
    ],
    "description": [
        "Use a new narrative angle and phrasing pattern instead of repeating the same intro structure every time.",
        "Keep the SEO strong, but vary the voice and selling points so repeated runs do not sound templated.",
        "Avoid reusing the same sentence rhythm or repeated adjective stack from prior descriptions.",
    ],
    "keyword": [
        "Vary the keyword mix and ordering so the set does not feel copied from a previous run.",
        "Blend core genre terms with fresher long-tail phrases instead of returning the same predictable list.",
        "Keep the keyword set relevant, but avoid repeating the exact same cluster of standard phrases.",
    ],
    "tag": [
        "Return a varied tag mix with a fresh combination and ordering, not the same repeated tag pack.",
        "Balance broad discovery tags with more distinctive niche tags so repeated runs stay differentiated.",
        "Avoid reusing the same tag sequence or near-duplicate tag bundle from previous outputs.",
    ],
}

_ROLE_NOTES: dict[str, str] = {
    "primary": "This should feel like the flagship channel identity: confident, broad-appeal, and lead-brand ready.",
    "secondary": "This should feel like a companion channel identity with a differentiated angle, while still belonging to the same overall brand world.",
    "both": "Generate two distinct naming groups: the first half should fit a flagship primary channel, and the second half should fit a differentiated secondary companion channel. Avoid duplicates across the two halves.",
}

_YOUTUBE_KEYWORD_RULES = """
YouTube channel keyword rules (strict):
- Return 15-25 separate keyword strings in the JSON "keywords" array.
- Each item is ONE keyword or short keyphrase only (1-3 words, max 35 characters).
- Never return sentences, marketing copy, or channel descriptions.
- Use correct English spelling and grammar. No broken or truncated words.
- Never put commas inside an item. Commas are only JSON array separators.
- Prefer high-intent search terms for the genre and channel niche.
- Include the channel name once when relevant.
"""

_YOUTUBE_TAG_RULES = """
YouTube video tag rules (strict):
- Return 15-30 separate tag strings in the JSON "tags" array.
- Each tag is 1-3 words, max 30 characters, correct English spelling.
- Tags must paste directly into YouTube Studio (comma-separated in the UI).
- No sentences, no broken words, no commas inside a tag string.
- Combined tag length must stay under 500 characters.
- Mix broad discovery tags with niche tags that fit the channel genre.
"""
def _build_prompt_with_variation(
    base_prompt: str,
    category: str,
    *,
    genre: str = "",
    role: str = "",
    description: str = "",
) -> str:
    prompt = (
        base_prompt.replace("{genre}", genre or "music")
        .replace("{description}", description or "")
        .strip()
    )

    notes: list[str] = []
    role_note = _ROLE_NOTES.get(role.strip().lower(), "")
    if role_note:
        notes.append(role_note)

    variation_choices = _CATEGORY_VARIATION_NOTES.get(category, [])
    if variation_choices:
        notes.append(random.choice(variation_choices))

    if category == "title":
        notes.append(
            "Return clearly distinct options, avoid duplicates, and do not recycle the same few generic words across most names."
        )

    if not notes:
        return prompt

    return f"{prompt}\n\nAdditional guidance:\n- " + "\n- ".join(notes)


# ---------------------------------------------------------------------------
# AI Routing dependency
# ---------------------------------------------------------------------------


async def _get_ai_routing_service() -> AIRoutingService:
    """Placeholder dependency for AIRoutingService — override via app.dependency_overrides."""
    raise NotImplementedError(
        "AIRoutingService dependency not configured. Wire via app.dependency_overrides."
    )


AIRoutingServiceDep = Annotated[AIRoutingService, Depends(_get_ai_routing_service)]


async def _run_onboarding_ai(
    ctx: AuthContext,
    operation_type: str,
    operation: Callable[[], Awaitable[T]],
    *,
    count: int = 1,
    usage_metadata: dict[str, Any] | None = None,
) -> T:
    """Execute payment-gated onboarding AI (no wallet deduction)."""
    from platform_api.dependencies import get_db_pool
    from platform_api.middleware.rate_limit import enforce_rate_limit_for_endpoint
    from platform_api.services.onboarding_entitlement_service import run_onboarding_ai_operation

    endpoint_type = (
        "image"
        if operation_type in {"channel_logo", "channel_cover"}
        else "llm"
    )
    await enforce_rate_limit_for_endpoint(ctx.user_id, endpoint_type)

    pool = get_db_pool()
    return await run_onboarding_ai_operation(
        pool,
        UUID(str(ctx.user_id)),
        operation_type,
        operation,
        count=count,
        usage_metadata=usage_metadata,
    )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GenerateNamesRequest(BaseModel):
    """Request to generate channel name suggestions."""

    genre: str = Field(..., min_length=1, max_length=100, description="Music genre (e.g. EDM, R&B, Pop)")
    role: str = Field("primary", description="'primary', 'secondary', or 'both' channels")
    description: str = Field("", max_length=500, description="Optional genre description/context")
    match_key: str = Field("", max_length=100, description="Match key of the selected music description (links to the admin channel prompt)")
    count: int = Field(10, ge=1, le=20, description="Number of names to generate (max 20)")


class GenerateNamesResponse(BaseModel):
    """Response with generated channel names."""

    names: list[str]


class GenerateLogoRequest(BaseModel):
    """Request to generate a channel logo."""

    channel_name: str = Field(..., min_length=1, max_length=100)
    genre: str = Field("", max_length=100)
    role: str = Field("primary", description="'primary' or 'secondary' channel")
    match_key: str = Field("", max_length=100, description="Match key for prompt lookup")


class GenerateImageResponse(BaseModel):
    """Response with a generated image."""

    image_base64: str
    width: int = 512
    height: int = 512


class GenerateCoversRequest(BaseModel):
    """Request to generate channel cover images."""

    channel_name: str = Field(..., min_length=1, max_length=100)
    genre: str = Field("", max_length=100)
    count: int = Field(1, ge=1, le=5)
    role: str = Field("primary", description="'primary' or 'secondary' channel")
    match_key: str = Field("", max_length=100, description="Match key for prompt lookup")


class GenerateCoversResponse(BaseModel):
    """Response with generated cover images."""

    images: list[str]  # list of base64 strings


class GenerateDescriptionRequest(BaseModel):
    """Request to generate channel description + keywords."""

    channel_name: str = Field(..., min_length=1, max_length=100)
    genre: str = Field(..., min_length=1, max_length=100)
    match_key: str = Field("", max_length=100, description="Match key for prompt lookup")
    description: str = Field("", max_length=4000, description="Optional description context for keyword/tag generation")


class GenerateDescriptionResponse(BaseModel):
    """Response with generated description, keywords, and tags."""

    description: str
    keywords: list[str]
    tags: list[str]


class GenerateDescriptionTextResponse(BaseModel):
    description: str


class GenerateKeywordsResponse(BaseModel):
    keywords: list[str]


class GenerateTagsResponse(BaseModel):
    tags: list[str]


class SaveOnboardingDraftRequest(BaseModel):
    """Persisted onboarding state for the authenticated user."""

    payload: dict[str, Any] = Field(default_factory=dict)


class OnboardingDraftResponse(BaseModel):
    """Stored onboarding draft plus current name-generation usage state."""

    payload: dict[str, Any] = Field(default_factory=dict)
    name_generate_limit: int
    name_generate_used: int
    name_generate_remaining: int
    logo_generate_limit: int
    logo_generate_used: int
    logo_generate_remaining: int
    cover_generate_limit: int
    cover_generate_used: int
    cover_generate_remaining: int
    description_generate_limit: int
    description_generate_used: int
    description_generate_remaining: int
    keywords_generate_limit: int
    keywords_generate_used: int
    keywords_generate_remaining: int
    tags_generate_limit: int
    tags_generate_used: int
    tags_generate_remaining: int


class CreateProfileRequest(BaseModel):
    """Request to create a channel profile from onboarding."""

    name: str = Field(..., min_length=1, max_length=100)
    genre: str = Field("", max_length=100)
    role: str = Field("primary", description="'primary' or 'secondary' channel")
    logo_base64: str | None = None
    cover_images: list[str] = Field(default_factory=list, description="List of cover image base64 strings")
    description: str = ""
    keywords: list[str] = []
    tags: list[str] = []
    match_key: str = ""


class CreateProfileResponse(BaseModel):
    """Response after creating a channel profile."""

    profile_id: str
    name: str
    message: str


async def _get_channel_prompt(category: str, genre: str, default: str, match_key: str | None = None) -> str:
    """Fetch a channel prompt from DB, falling back to default if not found.

    Priority: match_key > genre > default (empty genre) > hardcoded fallback.
    """
    try:
        from platform_api.dependencies import get_db_pool
        pool = get_db_pool()
        # Try match_key first (linked to music_descriptions)
        if match_key:
            row = await pool.fetchrow(
                """SELECT content FROM channel_prompts
                   WHERE category = $1 AND match_key = $2 AND is_active = true
                   ORDER BY RANDOM() LIMIT 1""",
                category, match_key,
            )
            if row:
                return row["content"]
        # Try genre-specific
        if genre:
            row = await pool.fetchrow(
                """SELECT content FROM channel_prompts
                   WHERE category = $1 AND genre = $2 AND is_active = true
                   ORDER BY RANDOM() LIMIT 1""",
                category, genre,
            )
            if row:
                return row["content"]
        # Fall back to default (empty genre)
        row = await pool.fetchrow(
            """SELECT content FROM channel_prompts
               WHERE category = $1 AND genre = '' AND is_active = true
               ORDER BY RANDOM() LIMIT 1""",
            category,
        )
        if row:
            return row["content"]
    except Exception as exc:
        logger.debug("Could not fetch channel prompt for %s/%s: %s", category, genre, exc)
    return default


async def _build_onboarding_draft_response(
    *,
    pool: Any,
    user_id: UUID,
    payload: dict[str, Any] | None = None,
) -> OnboardingDraftResponse:
    from platform_api.services.onboarding_entitlement_service import (
        effective_onboarding_ai_limit,
        get_onboarding_usage,
    )

    name_used = await get_onboarding_usage(pool, user_id, "channel_name")
    name_limit = await effective_onboarding_ai_limit(pool, user_id, "channel_name")
    logo_used = await get_onboarding_usage(pool, user_id, "channel_logo")
    logo_limit = await effective_onboarding_ai_limit(pool, user_id, "channel_logo")
    cover_used = await get_onboarding_usage(pool, user_id, "channel_cover")
    cover_limit = await effective_onboarding_ai_limit(pool, user_id, "channel_cover")
    description_used = await get_onboarding_usage(pool, user_id, "channel_description")
    description_limit = await effective_onboarding_ai_limit(pool, user_id, "channel_description")
    keywords_used = await get_onboarding_usage(pool, user_id, "channel_keywords")
    keywords_limit = await effective_onboarding_ai_limit(pool, user_id, "channel_keywords")
    tags_used = await get_onboarding_usage(pool, user_id, "channel_tags")
    tags_limit = await effective_onboarding_ai_limit(pool, user_id, "channel_tags")
    return OnboardingDraftResponse(
        payload=payload or {},
        name_generate_limit=name_limit,
        name_generate_used=name_used,
        name_generate_remaining=max(0, name_limit - name_used),
        logo_generate_limit=logo_limit,
        logo_generate_used=logo_used,
        logo_generate_remaining=max(0, logo_limit - logo_used),
        cover_generate_limit=cover_limit,
        cover_generate_used=cover_used,
        cover_generate_remaining=max(0, cover_limit - cover_used),
        description_generate_limit=description_limit,
        description_generate_used=description_used,
        description_generate_remaining=max(0, description_limit - description_used),
        keywords_generate_limit=keywords_limit,
        keywords_generate_used=keywords_used,
        keywords_generate_remaining=max(0, keywords_limit - keywords_used),
        tags_generate_limit=tags_limit,
        tags_generate_used=tags_used,
        tags_generate_remaining=max(0, tags_limit - tags_used),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/generate-names",
    response_model=GenerateNamesResponse,
    status_code=200,
    summary="Generate channel name suggestions",
)
async def generate_names(
    request: GenerateNamesRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateNamesResponse:
    """Generate AI-powered channel name suggestions based on genre."""
    # Resolve AI routing for channel_name operation
    routing = await routing_service.resolve("channel_name")
    text_chain = [
        (item.provider, item.sub_model or "")
        for item in await routing_service.resolve_text_chain("channel_name")
    ]

    # Resolve prompt BEFORE charging — don't charge if no prompt available
    lookup_key = (request.match_key or request.genre or "").strip()
    prompt = await _get_channel_prompt("title", request.genre, "", match_key=lookup_key)
    if not prompt:
        if request.description:
            prompt = (
                "Please provide a list of recommended YouTube channel names "
                f"for the '{request.genre}' music genre."
            )
        else:
            raise ValidationError(
                f"No 'Channel Name' prompt found for match key '{lookup_key}'. "
                "Create one in the admin portal (Music Prompts → Channel Prompts) "
                "with a match key equal to this genre's match key.",
            )

    prompt = _build_prompt_with_variation(
        prompt,
        "title",
        genre=request.genre,
        role=request.role,
        description=request.description,
    )

    system = "You are a creative music branding expert. Return ONLY a JSON array of strings, no explanation."
    if request.description:
        prompt += f"\n\nExtra user context: {request.description}"

    async def _do_generate() -> list[str]:
        from platform_api.ai.purposes.channel_generation import generate_channel_text
        from platform_api.ai.purposes.channel_text import parse_string_list

        result = await generate_channel_text(
            gen,
            provider=routing.provider,
            model=routing.sub_model,
            system_prompt=system,
            user_prompt=prompt,
            temperature=0.95,
            max_tokens=1200,
            provider_chain=text_chain,
        )
        names = parse_string_list(result)
        return names[:10] if names else []

    try:
        names = await _run_onboarding_ai(
            ctx,
            "channel_name",
            _do_generate,
            usage_metadata={
                "provider": routing.provider,
                "model": routing.sub_model,
                "sub_model": routing.sub_model,
                "genre": request.genre,
                "role": request.role,
                "match_key": request.match_key,
                "request_count": request.count,
            },
        )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate channel names: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate channel names: {str(exc)}",
            is_retryable=True,
        )

    return GenerateNamesResponse(names=names[:request.count])


@router.get(
    "/profiles-status",
    status_code=200,
    summary="Check if user has completed channel onboarding",
)
async def profiles_status(
    ctx: AuthContext = Depends(get_current_user),
) -> dict:
    """Return whether the user has channel profiles set up."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) as cnt FROM channel_profiles WHERE user_id = $1",
        ctx.user_id,
    )
    count = row["cnt"] if row else 0
    return {"has_profiles": count >= 2, "profile_count": count}


@router.get(
    "/draft",
    response_model=OnboardingDraftResponse,
    status_code=200,
    summary="Get the current user's onboarding draft",
)
async def get_onboarding_draft(
    ctx: AuthContext = Depends(get_current_user),
) -> OnboardingDraftResponse:
    """Return the persisted onboarding draft for the authenticated user."""
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        SELECT payload
        FROM onboarding_drafts
        WHERE user_id = $1
        """,
        ctx.user_id,
    )
    payload = row["payload"] if row and isinstance(row["payload"], dict) else {}
    return await _build_onboarding_draft_response(
        pool=pool,
        user_id=UUID(str(ctx.user_id)),
        payload=payload,
    )


@router.put(
    "/draft",
    response_model=OnboardingDraftResponse,
    status_code=200,
    summary="Save the current user's onboarding draft",
)
async def save_onboarding_draft(
    request: SaveOnboardingDraftRequest,
    ctx: AuthContext = Depends(get_current_user),
) -> OnboardingDraftResponse:
    """Persist onboarding draft state so the user can resume later."""
    from platform_api.dependencies import get_db_pool
    import json as _json

    pool = get_db_pool()
    payload = request.payload if isinstance(request.payload, dict) else {}
    await pool.execute(
        """
        INSERT INTO onboarding_drafts (user_id, payload, created_at, updated_at)
        VALUES ($1, $2::jsonb, NOW(), NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            payload = EXCLUDED.payload,
            updated_at = NOW()
        """,
        ctx.user_id,
        _json.dumps(payload),
    )
    return await _build_onboarding_draft_response(
        pool=pool,
        user_id=UUID(str(ctx.user_id)),
        payload=payload,
    )


@router.post(
    "/generate-logo",
    response_model=GenerateImageResponse,
    status_code=200,
    summary="Generate a channel logo",
)
async def generate_logo(
    request: GenerateLogoRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateImageResponse:
    """Generate a circular channel logo using image generation via the pool."""
    routing_chain = await routing_service.resolve_image_chain("channel_logo")
    primary_routing = routing_chain[0]

    # Resolve prompt BEFORE charging
    lookup_key = (request.match_key or request.genre or "").strip()
    prompt = await _get_channel_prompt("logo", request.genre, "", match_key=lookup_key)
    if not prompt:
        # Fallback: generate a sensible prompt from the channel name + genre
        prompt = f"Create a professional circular YouTube channel logo for '{request.channel_name}' in the {request.genre or 'music'} genre. Modern, clean, dark background."

    # Inject channel name into the prompt if it's a template
    prompt = _build_prompt_with_variation(
        prompt.replace("{channel_name}", request.channel_name),
        "logo",
        genre=request.genre,
        role=request.role,
    )

    usage_metadata: dict[str, Any] = {
        "provider": primary_routing.provider,
        "model": primary_routing.sub_model,
        "sub_model": primary_routing.sub_model,
        "genre": request.genre,
        "role": request.role,
        "match_key": request.match_key,
        "channel_name": request.channel_name,
    }

    async def _do_generate() -> tuple[str, str, str | None]:
        import base64 as _b64
        import io

        from platform_api.ports.generation_port import ImageRequest

        image_request = ImageRequest(
            prompt=prompt,
            provider=primary_routing.provider,
            model_id=primary_routing.sub_model,
            resolution="512x512",
            style_strength=0.6,
            base_image=None,
        )
        outcome = await gen.submit_image_outcome(
            ctx.user_id,
            image_request,
            operation="channel_logo",
            skip_pricing=True,
        )
        usage_metadata["provider"] = outcome.provider
        usage_metadata["model"] = outcome.sub_model
        usage_metadata["sub_model"] = outcome.sub_model
        image_bytes = outcome.image_bytes

        if outcome.provider == "openai":
            try:
                from PIL import Image as _PILImage

                img = _PILImage.open(io.BytesIO(image_bytes))
                img = img.convert("RGBA")
                img = img.resize((512, 512), _PILImage.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
            except ImportError:
                pass

        return _b64.b64encode(image_bytes).decode(), outcome.provider, outcome.sub_model

    async def _do_generate_image() -> str:
        image_b64, _, _ = await _do_generate()
        return image_b64

    try:
        image_b64 = await _run_onboarding_ai(
            ctx,
            "channel_logo",
            _do_generate_image,
            usage_metadata=usage_metadata,
        )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate logo: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate logo: {str(exc)}",
            is_retryable=True,
        )

    return GenerateImageResponse(image_base64=image_b64, width=512, height=512)


@router.post(
    "/generate-covers",
    response_model=GenerateCoversResponse,
    status_code=200,
    summary="Generate channel cover images",
)
async def generate_covers(
    request: GenerateCoversRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateCoversResponse:
    """Generate channel cover/banner images using image generation via the pool."""
    routing_chain = await routing_service.resolve_image_chain("channel_cover")
    primary_routing = routing_chain[0]

    # Resolve prompt BEFORE charging
    lookup_key = (getattr(request, 'match_key', '') or request.genre or "").strip()
    prompt = await _get_channel_prompt("cover", request.genre, "", match_key=lookup_key)
    if not prompt:
        prompt = (
            f"Create a professional YouTube channel banner for '{request.channel_name}' "
            f"in the {request.genre or 'music'} genre. Cinematic 16:9 widescreen composition, dark theme."
        )

    prompt = _build_prompt_with_variation(
        prompt.replace("{channel_name}", request.channel_name),
        "cover",
        genre=request.genre,
        role=request.role,
    )

    usage_metadata: dict[str, Any] = {
        "provider": primary_routing.provider,
        "model": primary_routing.sub_model,
        "sub_model": primary_routing.sub_model,
        "genre": request.genre,
        "role": request.role,
        "match_key": request.match_key,
        "channel_name": request.channel_name,
        "request_count": request.count,
    }

    async def _generate_one_cover() -> tuple[str, str, str | None]:
        import base64 as _b64
        import io

        from platform_api.ports.generation_port import ImageRequest

        image_request = ImageRequest(
            prompt=prompt,
            provider=primary_routing.provider,
            model_id=primary_routing.sub_model,
            resolution="1920x1080",
            style_strength=0.6,
            base_image=None,
        )
        outcome = await gen.submit_image_outcome(
            ctx.user_id,
            image_request,
            operation="channel_cover",
            skip_pricing=True,
        )
        usage_metadata["provider"] = outcome.provider
        usage_metadata["model"] = outcome.sub_model
        usage_metadata["sub_model"] = outcome.sub_model
        image_bytes = outcome.image_bytes

        if outcome.provider == "openai":
            try:
                from PIL import Image as _PILImage

                img = _PILImage.open(io.BytesIO(image_bytes))
                img = img.convert("RGBA")
                scale = 1920.0 / float(img.width or 1)
                new_w = 1920
                new_h = max(1, int(float(img.height) * scale))
                img = img.resize((new_w, new_h), _PILImage.Resampling.LANCZOS)
                if new_h > 1080:
                    y_offset = (new_h - 1080) // 2
                    img = img.crop((0, y_offset, 1920, y_offset + 1080))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
            except ImportError:
                pass

        return _b64.b64encode(image_bytes).decode(), outcome.provider, outcome.sub_model

    try:
        images: list[str] = []
        for _ in range(request.count):
            async def _one_cover() -> str:
                image_b64, _, _ = await _generate_one_cover()
                return image_b64

            images.append(
                await _run_onboarding_ai(
                    ctx,
                    "channel_cover",
                    _one_cover,
                    usage_metadata=usage_metadata,
                )
            )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate covers: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate cover: {str(exc)}",
            is_retryable=True,
        )

    return GenerateCoversResponse(images=images)


@router.post(
    "/generate-description",
    response_model=GenerateDescriptionResponse,
    status_code=200,
    summary="Generate channel description, keywords, and tags",
)
async def generate_description(
    request: GenerateDescriptionRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateDescriptionResponse:
    """Generate a YouTube channel description, keywords, and tags using LLM."""
    # Resolve AI routing for channel_description operation
    routing = await routing_service.resolve("channel_description")
    text_chain = [
        (item.provider, item.sub_model or "")
        for item in await routing_service.resolve_text_chain("channel_description")
    ]

    # Resolve prompt BEFORE charging
    system = (
        "You are a YouTube SEO expert. Return a JSON object with three fields: "
        "'description' (string), 'keywords' (array), and 'tags' (array). "
        "No explanation, just the JSON."
    )

    lookup_key = (request.match_key or request.genre).strip()
    prompt = await _get_channel_prompt("description", request.genre, "", match_key=lookup_key)
    if not prompt:
        raise ValidationError(
            f"No 'Channel Description' prompt found for match key '{lookup_key}'. "
            "Create one in the admin portal (Music Prompts → Channel Prompts) "
            "with category 'description' and a matching match key."
        )

    prompt = _build_prompt_with_variation(
        prompt.replace("{channel_name}", request.channel_name),
        "description",
        genre=request.genre,
        description=request.description,
    )

    user_prompt = (
        f"{prompt}\n\n"
        "Return ONLY a JSON object with exactly these keys:\n"
        "- description: string\n"
        "- keywords: array of strings\n"
        "- tags: array of strings\n"
        f"{_YOUTUBE_KEYWORD_RULES}\n"
        f"{_YOUTUBE_TAG_RULES}\n"
        "No markdown, no extra keys, no extra text."
    )

    async def _do_generate() -> GenerateDescriptionResponse:
        from platform_api.ai.purposes.channel_generation import generate_channel_text
        from platform_api.ai.purposes.channel_text import parse_channel_description

        result = await generate_channel_text(
            gen,
            provider=routing.provider,
            model=routing.sub_model,
            system_prompt=system,
            user_prompt=user_prompt,
            temperature=0.45,
            max_tokens=1200,
            provider_chain=text_chain,
        )
        logger.info("Description LLM raw (first 500): %s", repr(result[:500]) if result else "EMPTY")
        parsed = parse_channel_description(result)
        return GenerateDescriptionResponse(
            description=str(parsed.get("description", "")),
            keywords=[str(k) for k in parsed.get("keywords", [])],
            tags=[str(t) for t in parsed.get("tags", [])],
        )

    try:
        response = await _run_onboarding_ai(
            ctx,
            "channel_description",
            _do_generate,
            usage_metadata={
                "provider": routing.provider,
                "model": routing.sub_model,
                "sub_model": routing.sub_model,
                "genre": request.genre,
                "match_key": request.match_key,
                "channel_name": request.channel_name,
            },
        )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate description: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate description: {str(exc)}",
            is_retryable=True,
        )

    return response


@router.post(
    "/generate-description-text",
    response_model=GenerateDescriptionTextResponse,
    status_code=200,
    summary="Generate channel description text only",
)
async def generate_description_text(
    request: GenerateDescriptionRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateDescriptionTextResponse:
    routing = await routing_service.resolve("channel_description")
    text_chain = [
        (item.provider, item.sub_model or "")
        for item in await routing_service.resolve_text_chain("channel_description")
    ]

    lookup_key = (request.match_key or request.genre).strip()
    prompt = await _get_channel_prompt("description", request.genre, "", match_key=lookup_key)
    if not prompt:
        raise ValidationError(
            f"No 'Channel Description' prompt found for match key '{lookup_key}'. "
            "Create one in the admin portal (Music Prompts → Channel Prompts) "
            "with category 'description' and a matching match key."
        )

    prompt = _build_prompt_with_variation(
        prompt.replace("{channel_name}", request.channel_name),
        "description",
        genre=request.genre,
        description=request.description,
    )

    system = "Return ONLY a JSON object with exactly one key: 'description' (string). No markdown, no extra keys, no extra text."
    user_prompt = (
        "Return ONLY a JSON object with exactly one key: 'description' (string). "
        "No markdown, no extra keys, no extra text.\n\n"
        f"{prompt}"
    )

    async def _do_generate() -> GenerateDescriptionTextResponse:
        from platform_api.ai.purposes.channel_generation import generate_channel_text
        from platform_api.ai.purposes.channel_text import parse_description_text

        result = await generate_channel_text(
            gen,
            provider=routing.provider,
            model=routing.sub_model,
            system_prompt=system,
            user_prompt=user_prompt,
            temperature=0.5,
            max_tokens=1200,
            provider_chain=text_chain,
        )
        return GenerateDescriptionTextResponse(
            description=parse_description_text(result),
        )

    try:
        response = await _run_onboarding_ai(
            ctx,
            "channel_description",
            _do_generate,
            usage_metadata={
                "provider": routing.provider,
                "model": routing.sub_model,
                "sub_model": routing.sub_model,
                "genre": request.genre,
                "match_key": request.match_key,
                "channel_name": request.channel_name,
                "mode": "description_text",
            },
        )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate description text: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate description text: {str(exc)}",
            is_retryable=True,
        )

    return response


@router.post(
    "/generate-keywords",
    response_model=GenerateKeywordsResponse,
    status_code=200,
    summary="Generate channel SEO keywords only",
)
async def generate_keywords(
    request: GenerateDescriptionRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateKeywordsResponse:
    routing = await routing_service.resolve("channel_keywords")
    text_chain = [
        (item.provider, item.sub_model or "")
        for item in await routing_service.resolve_text_chain("channel_keywords")
    ]

    lookup_key = (request.match_key or request.genre).strip()
    prompt = await _get_channel_prompt("keyword", request.genre, "", match_key=lookup_key)
    if not prompt:
        raise ValidationError(
            f"No 'Channel Keywords' prompt found for match key '{lookup_key}'. "
            "Create one in the admin portal (Music Prompts → Channel Prompts) "
            "with category 'keyword' and a matching match key."
        )

    prompt = _build_prompt_with_variation(
        prompt.replace("{channel_name}", request.channel_name),
        "keyword",
        genre=request.genre,
        description=request.description,
    )

    system = (
        "Return ONLY a JSON object with exactly one key: 'keywords' (array of strings). "
        "No markdown, no extra keys, no extra text."
    )
    user_prompt = (
        "Return ONLY a JSON object with exactly one key: 'keywords' (array of strings). "
        "No markdown, no extra keys, no extra text.\n\n"
        f"{prompt}\n"
        f"{_YOUTUBE_KEYWORD_RULES}"
    )

    async def _do_generate() -> GenerateKeywordsResponse:
        from platform_api.ai.purposes.channel_generation import generate_channel_text
        from platform_api.ai.purposes.channel_text import parse_keywords

        result = await generate_channel_text(
            gen,
            provider=routing.provider,
            model=routing.sub_model,
            system_prompt=system,
            user_prompt=user_prompt,
            temperature=0.35,
            max_tokens=1200,
            provider_chain=text_chain,
        )
        return GenerateKeywordsResponse(keywords=parse_keywords(result))

    try:
        response = await _run_onboarding_ai(
            ctx,
            "channel_keywords",
            _do_generate,
            usage_metadata={
                "provider": routing.provider,
                "model": routing.sub_model,
                "sub_model": routing.sub_model,
                "genre": request.genre,
                "match_key": request.match_key,
                "channel_name": request.channel_name,
            },
        )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate keywords: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate keywords: {str(exc)}",
            is_retryable=True,
        )

    return response


@router.post(
    "/generate-tags",
    response_model=GenerateTagsResponse,
    status_code=200,
    summary="Generate channel tags only",
)
async def generate_tags(
    request: GenerateDescriptionRequest,
    gen: GenerationServiceDep,
    routing_service: AIRoutingServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateTagsResponse:
    routing = await routing_service.resolve("channel_tags")
    text_chain = [
        (item.provider, item.sub_model or "")
        for item in await routing_service.resolve_text_chain("channel_tags")
    ]

    lookup_key = (request.match_key or request.genre).strip()
    prompt = await _get_channel_prompt("tag", request.genre, "", match_key=lookup_key)
    if not prompt:
        raise ValidationError(
            f"No 'Channel Tags' prompt found for match key '{lookup_key}'. "
            "Create one in the admin portal (Music Prompts → Channel Prompts) "
            "with category 'tag' and a matching match key."
        )

    prompt = _build_prompt_with_variation(
        prompt.replace("{channel_name}", request.channel_name),
        "tag",
        genre=request.genre,
        description=request.description,
    )

    system = (
        "Return ONLY a JSON object with exactly one key: 'tags' (array of strings). "
        "No markdown, no extra keys, no extra text."
    )
    user_prompt = (
        "Return ONLY a JSON object with exactly one key: 'tags' (array of strings). "
        "No markdown, no extra keys, no extra text.\n\n"
        f"{prompt}\n"
        f"{_YOUTUBE_TAG_RULES}"
    )

    async def _do_generate() -> GenerateTagsResponse:
        from platform_api.ai.purposes.channel_generation import generate_channel_text
        from platform_api.ai.purposes.channel_text import parse_tags

        result = await generate_channel_text(
            gen,
            provider=routing.provider,
            model=routing.sub_model,
            system_prompt=system,
            user_prompt=user_prompt,
            temperature=0.35,
            max_tokens=1200,
            provider_chain=text_chain,
        )
        return GenerateTagsResponse(tags=parse_tags(result))

    try:
        response = await _run_onboarding_ai(
            ctx,
            "channel_tags",
            _do_generate,
            usage_metadata={
                "provider": routing.provider,
                "model": routing.sub_model,
                "sub_model": routing.sub_model,
                "genre": request.genre,
                "match_key": request.match_key,
                "channel_name": request.channel_name,
            },
        )
    except PlatformAPIError:
        raise
    except Exception as exc:
        logger.error("Failed to generate tags: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate tags: {str(exc)}",
            is_retryable=True,
        )

    return response


@router.post(
    "/create-profile",
    response_model=CreateProfileResponse,
    status_code=201,
    summary="Create channel profile from onboarding",
)
async def create_profile(
    request: CreateProfileRequest,
    ctx: AuthContext = Depends(get_current_user),
) -> CreateProfileResponse:
    """Create a channel profile from the onboarding wizard.

    Stores the full profile data (name, genre, role, logo, covers,
    description, keywords, tags) tied to the authenticated user.
    Called once per channel at the end of the onboarding journey.
    """
    from platform_api.dependencies import get_db_pool
    import uuid
    import os
    import json as _json

    pool = get_db_pool()
    user_id = ctx.user_id
    user_uuid = UUID(user_id)

    from platform_api.dependencies import get_profile_service

    profile_service = get_profile_service()
    await profile_service.ensure_profile_capacity(user_uuid)

    # Generate folder name from channel name
    folder_name = request.name.lower().replace(" ", "-").replace("/", "-")
    folder_name = "".join(c for c in folder_name if c.isalnum() or c == "-")[:50]

    # Save logo to filesystem if provided
    logo_path = None
    if request.logo_base64:
        try:
            logo_dir = os.path.join("uploads", "logos", str(user_id))
            os.makedirs(logo_dir, exist_ok=True)
            logo_path = os.path.join(logo_dir, f"{folder_name}-logo.png")
            with open(logo_path, "wb") as f:
                f.write(base64.b64decode(request.logo_base64))
        except Exception as exc:
            logger.error("Failed to save logo: %s", exc)

    # Save cover images to filesystem if provided
    cover_paths: list[str] = []
    if request.cover_images:
        try:
            covers_dir = os.path.join("uploads", "covers", str(user_id))
            os.makedirs(covers_dir, exist_ok=True)
            for i, cover_b64 in enumerate(request.cover_images[:5]):
                if not cover_b64:
                    continue
                cover_path = os.path.join(covers_dir, f"{folder_name}-cover-{i}.png")
                with open(cover_path, "wb") as f:
                    f.write(base64.b64decode(cover_b64))
                cover_paths.append(cover_path)
        except Exception as exc:
            logger.error("Failed to save covers: %s", exc)

    # Build config JSONBs with full onboarding data
    image_config = {
        "genre": request.genre,
        "match_key": request.match_key,
        "role": request.role,
        "description": request.description,
        "cover_paths": cover_paths,
    }
    youtube_config = {
        "keywords": request.keywords,
        "tags": request.tags,
        "description": request.description,
    }

    # Create (or update) the profile — upsert on (user_id, name) unique constraint
    profile_id = uuid.uuid4()
    await pool.execute(
        """INSERT INTO channel_profiles
           (id, user_id, name, folder_name, logo_path, output_resolution, image_config, youtube_config, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, '1920x1080', $6, $7, NOW(), NOW())
           ON CONFLICT (user_id, name) DO UPDATE SET
               folder_name = EXCLUDED.folder_name,
               logo_path = EXCLUDED.logo_path,
               image_config = EXCLUDED.image_config,
               youtube_config = EXCLUDED.youtube_config,
               updated_at = NOW()""",
        profile_id,
        user_id,
        request.name,
        folder_name,
        logo_path,
        _json.dumps(image_config),
        _json.dumps(youtube_config),
    )

    return CreateProfileResponse(
        profile_id=str(profile_id),
        name=request.name,
        message=f"{request.role.title()} channel profile created successfully.",
    )
