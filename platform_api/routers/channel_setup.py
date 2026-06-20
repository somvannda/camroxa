"""Channel setup router for onboarding wizard.

Provides endpoints to generate channel names, logos, covers,
and descriptions using AI (DeepSeek LLM + SLAI image generation).
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.exceptions import PlatformAPIError, ExternalServiceError, ValidationError
from platform_api.routers.generation import GenerationServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channel-setup", tags=["channel-setup"])

# Module-level references, set by wire_dependencies
_llm_client: Any = None
_slai_client: Any = None


def set_clients(llm_client: Any, slai_client: Any) -> None:
    global _llm_client, _slai_client
    _llm_client = llm_client
    _slai_client = slai_client


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class GenerateNamesRequest(BaseModel):
    """Request to generate channel name suggestions."""

    genre: str = Field(..., min_length=1, max_length=100, description="Music genre (e.g. EDM, R&B, Pop)")
    role: str = Field("primary", description="'primary' or 'secondary' channel")
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
    count: int = Field(3, ge=1, le=5)
    role: str = Field("primary", description="'primary' or 'secondary' channel")
    match_key: str = Field("", max_length=100, description="Match key for prompt lookup")


class GenerateCoversResponse(BaseModel):
    """Response with generated cover images."""

    images: list[str]  # list of base64 strings


class GenerateDescriptionRequest(BaseModel):
    """Request to generate channel description + keywords."""

    channel_name: str = Field(..., min_length=1, max_length=100)
    genre: str = Field(..., min_length=1, max_length=100)


class GenerateDescriptionResponse(BaseModel):
    """Response with generated description, keywords, and tags."""

    description: str
    keywords: list[str]
    tags: list[str]


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


# ---------------------------------------------------------------------------
# Helper: call DeepSeek LLM
# ---------------------------------------------------------------------------


async def _call_llm(prompt: str, system: str = "") -> str:
    """Call DeepSeek LLM API."""
    import os

    settings = __import__("platform_api.config", fromlist=["get_settings"]).get_settings()
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
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.8, "max_tokens": 500},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


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
                   ORDER BY name ASC LIMIT 1""",
                category, match_key,
            )
            if row:
                return row["content"]
        # Try genre-specific
        if genre:
            row = await pool.fetchrow(
                """SELECT content FROM channel_prompts
                   WHERE category = $1 AND genre = $2 AND is_active = true
                   ORDER BY name ASC LIMIT 1""",
                category, genre,
            )
            if row:
                return row["content"]
        # Fall back to default (empty genre)
        row = await pool.fetchrow(
            """SELECT content FROM channel_prompts
               WHERE category = $1 AND genre = '' AND is_active = true
               ORDER BY name ASC LIMIT 1""",
            category,
        )
        if row:
            return row["content"]
    except Exception as exc:
        logger.debug("Could not fetch channel prompt for %s/%s: %s", category, genre, exc)
    return default


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
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateNamesResponse:
    """Generate AI-powered channel name suggestions based on genre."""
    # The admin channel prompt is keyed on the music description's match_key.
    # The onboarding genre dropdown is a music description, so prefer its
    # match_key for the lookup and fall back to the genre name.
    lookup_key = (request.match_key or request.genre or "").strip()
    prompt = await _get_channel_prompt("title", request.genre, "", match_key=lookup_key)
    if not prompt:
        if request.description:
            # No admin preset matched, but the user supplied a custom prompt —
            # generate from a sensible base instruction instead of failing.
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

    system = "You are a creative music branding expert. Return ONLY a JSON array of strings, no explanation."
    if request.description:
        # Augment (do not replace) the admin preset with the user's custom prompt.
        prompt += f" Context: {request.description}"

    try:
        result = await gen.generate_chat_text(system_prompt=system, user_prompt=prompt, model="gpt-5.5")
        import json
        start = result.find("[")
        end = result.rfind("]") + 1
        if start >= 0 and end > start:
            names = json.loads(result[start:end])
        else:
            # Fallback: split by newlines
            names = [n.strip().strip('"').strip("'") for n in result.split("\n") if n.strip()][:10]
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


@router.post(
    "/generate-logo",
    response_model=GenerateImageResponse,
    status_code=200,
    summary="Generate a channel logo",
)
async def generate_logo(
    request: GenerateLogoRequest,
    gen: GenerationServiceDep,
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateImageResponse:
    """Generate a circular channel logo using SLAI image generation via the pool."""
    lookup_key = (request.match_key or request.genre or "").strip()
    prompt = await _get_channel_prompt("logo", request.genre, "", match_key=lookup_key)
    if not prompt:
        # Fallback: generate a sensible prompt from the channel name + genre
        prompt = f"Create a professional circular YouTube channel logo for '{request.channel_name}' in the {request.genre or 'music'} genre. Modern, clean, dark background."

    # Inject channel name into the prompt if it's a template
    prompt = prompt.replace("{channel_name}", request.channel_name)
    prompt = prompt.replace("{genre}", request.genre or "music")

    try:
        # Call the SLAI image generation directly via GenerationService's
        # internal pool-routed method (bypasses credit pricing for now —
        # onboarding uses trial credits with a flat deduction).
        response = await gen._call_slai(
            prompt=prompt,
            width=512,
            height=512,
            style_strength=0.7,
            reference_image_base64=None,
            extra_params=None,
        )
        image_bytes = gen._extract_image_bytes(response, provider="slai")
        import base64 as _b64
        image_b64 = _b64.b64encode(image_bytes).decode()
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
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateCoversResponse:
    """Generate channel cover/banner images using SLAI via the pool."""
    lookup_key = (getattr(request, 'match_key', '') or request.genre or "").strip()
    prompt = await _get_channel_prompt("cover", request.genre, "", match_key=lookup_key)
    if not prompt:
        prompt = f"Create a professional YouTube channel banner for '{request.channel_name}' in the {request.genre or 'music'} genre. Wide cinematic composition, dark theme."

    prompt = prompt.replace("{channel_name}", request.channel_name)
    prompt = prompt.replace("{genre}", request.genre or "music")

    images = []
    for i in range(request.count):
        try:
            response = await gen._call_slai(
                prompt=prompt,
                width=1920,
                height=480,
                style_strength=0.7,
                reference_image_base64=None,
                extra_params=None,
            )
            image_bytes = gen._extract_image_bytes(response, provider="slai")
            import base64 as _b64
            images.append(_b64.b64encode(image_bytes).decode())
        except Exception as exc:
            logger.error("Failed to generate cover %d: %s", i + 1, exc)
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
    ctx: AuthContext = Depends(get_current_user),
) -> GenerateDescriptionResponse:
    """Generate a YouTube channel description, keywords, and tags using LLM."""
    system = "You are a YouTube SEO expert. Return a JSON object with three fields: 'description' (string), 'keywords' (array), and 'tags' (array). No explanation, just the JSON."

    prompt = await _get_channel_prompt("description", request.genre, "", match_key=request.genre)
    if not prompt:
        raise ValidationError(
            f"No channel prompt found for category 'Description' with match_key '{request.genre}'. Please create one in the admin portal.",
        )

    try:
        result = await gen.generate_chat_text(system_prompt=system, user_prompt=prompt, model="gpt-5.5")
        import json
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(result[start:end])
            return GenerateDescriptionResponse(
                description=data.get("description", ""),
                keywords=data.get("keywords", []),
                tags=data.get("tags", []),
            )
    except Exception as exc:
        logger.error("Failed to generate description: %s", exc)
        raise ExternalServiceError(
            f"Failed to generate description: {str(exc)}",
            is_retryable=True,
        )


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