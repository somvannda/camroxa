"""Generation router endpoints.

Provides endpoints for song draft generation, Suno music generation,
Suno task status retrieval, and image generation. All endpoints require
User authentication.

Requirements: 11.1, 11.4, 12.1, 12.2, 12.3
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.models.enums import TaskStatus
from platform_api.ports.generation_port import DraftRequest, ImageRequest, SunoRequest
from platform_api.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/generation", tags=["generation"])


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------


class DraftGenerationRequest(BaseModel):
    """Request body for generating a song draft via LLM."""

    language: str = Field(default="en", max_length=20)
    creativity_level: int = Field(ge=0, le=100, default=50)
    description: str = Field(min_length=1, max_length=5000)
    structure: str = Field(default="", max_length=5000)
    avoid_titles: list[str] = Field(default_factory=list, max_length=200)
    avoid_albums: list[str] = Field(default_factory=list, max_length=200)
    avoid_openings: list[str] = Field(default_factory=list, max_length=200)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None


class DraftGenerationResponse(BaseModel):
    """Response containing the generated song draft."""

    title: str
    album: str
    lyrics: str


class SunoGenerationRequest(BaseModel):
    """Request body for submitting a Suno music generation task."""

    model: str = Field(pattern=r"^(V5|V5_5)$")
    title: str = Field(min_length=1, max_length=255)
    lyrics: str = Field(min_length=1)
    style: str = Field(min_length=1, max_length=255)
    instrumental: bool = False


class SunoGenerationResponse(BaseModel):
    """Response containing the Suno task ID."""

    task_id: str


class SunoTaskStatusResponse(BaseModel):
    """Response containing the status of a Suno generation task.

    Requirement 11.4: Return status, audio URLs (if SUCCESS), and download state.
    """

    task_id: str
    status: str  # PENDING, SUCCESS, or FAILED
    audio_url_ok: str | None = None
    audio_url_alt: str | None = None
    downloaded_ok: bool = False
    downloaded_alt: bool = False


class ImageGenerationRequest(BaseModel):
    """Request body for image generation.

    Requirements 12.1, 12.2, 12.3: Validate prompt, resolution, style_strength,
    base_image size, and forward to provider.
    """

    prompt: str = Field(min_length=1, max_length=2000)
    provider: str = Field(pattern=r"^(fal|slai)$")
    resolution: str = Field(default="1920x1080", pattern=r"^\d+x\d+$")
    style_strength: float = Field(ge=0.0, le=1.0, default=0.6)
    base_image: str | None = None  # base64-encoded image (optional, ≤10MB)


class ImageGenerationResponse(BaseModel):
    """Response containing the generated image as base64-encoded PNG."""

    image_base64: str


# ---------------------------------------------------------------------------
# Dependency Stubs
# ---------------------------------------------------------------------------


async def _get_generation_service() -> GenerationService:
    """Placeholder dependency for GenerationService — override via app.dependency_overrides."""
    raise NotImplementedError(
        "GenerationService dependency not configured. Wire via app.dependency_overrides."
    )


class TaskLookupPort:
    """Protocol for looking up Suno task status."""

    async def get_task_by_id(self, task_id: UUID, user_id: UUID) -> dict | None:
        """Return task details or None if not found / not owned by user."""
        ...


async def _get_task_lookup() -> TaskLookupPort:
    """Placeholder dependency for TaskLookupPort — override via app.dependency_overrides."""
    raise NotImplementedError(
        "TaskLookupPort dependency not configured. Wire via app.dependency_overrides."
    )


# Type aliases for dependency injection
GenerationServiceDep = Annotated[GenerationService, Depends(_get_generation_service)]
TaskLookupDep = Annotated[TaskLookupPort, Depends(_get_task_lookup)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/draft",
    response_model=DraftGenerationResponse,
    status_code=200,
    summary="Generate a song draft",
)
async def generate_draft(
    request: DraftGenerationRequest,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
) -> DraftGenerationResponse:
    """Generate a song draft (title, album, lyrics) via LLM.

    Requirement 10.1: Forward to configured LLM provider, return generated draft.
    """
    draft_request = DraftRequest(
        language=request.language,
        creativity_level=request.creativity_level,
        description=request.description,
        structure=request.structure,
        avoid_titles=request.avoid_titles,
        avoid_albums=request.avoid_albums,
        avoid_openings=request.avoid_openings,
        forced_title=request.forced_title,
        forced_album=request.forced_album,
        forced_opening=request.forced_opening,
    )

    draft = await generation_service.submit_draft(ctx.user_id, draft_request)

    return DraftGenerationResponse(
        title=draft.title,
        album=draft.album,
        lyrics=draft.lyrics,
    )


@router.post(
    "/suno",
    response_model=SunoGenerationResponse,
    status_code=202,
    summary="Submit Suno music generation",
)
async def submit_suno(
    request: SunoGenerationRequest,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
) -> SunoGenerationResponse:
    """Submit a music generation request to Suno.

    Requirement 11.1: Forward to Suno API, return task ID.
    Performs deduplication via request hash (Requirement 11.5).
    """
    suno_request = SunoRequest(
        model=request.model,
        title=request.title,
        lyrics=request.lyrics,
        style=request.style,
        instrumental=request.instrumental,
    )

    task_id = await generation_service.submit_suno(ctx.user_id, suno_request)

    return SunoGenerationResponse(task_id=task_id)


@router.get(
    "/suno/{task_id}",
    response_model=SunoTaskStatusResponse,
    status_code=200,
    summary="Get Suno task status",
)
async def get_suno_task_status(
    task_id: UUID,
    ctx: CurrentUserDep,
    task_lookup: TaskLookupDep,
) -> SunoTaskStatusResponse:
    """Return the current status of a Suno generation task.

    Requirement 11.4: Return status (PENDING, SUCCESS, FAILED),
    audio URLs if SUCCESS, and download state.
    """
    from platform_api.exceptions import NotFoundError

    task_data = await task_lookup.get_task_by_id(task_id, UUID(ctx.user_id))
    if task_data is None:
        raise NotFoundError(
            f"Suno task '{task_id}' not found.",
            details={"task_id": str(task_id)},
        )

    return SunoTaskStatusResponse(
        task_id=str(task_data["id"]),
        status=task_data["status"],
        audio_url_ok=task_data.get("audio_url_ok"),
        audio_url_alt=task_data.get("audio_url_alt"),
        downloaded_ok=task_data.get("downloaded_ok", False),
        downloaded_alt=task_data.get("downloaded_alt", False),
    )


@router.post(
    "/image",
    response_model=ImageGenerationResponse,
    status_code=200,
    summary="Generate an image",
)
async def generate_image(
    request: ImageGenerationRequest,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
) -> ImageGenerationResponse:
    """Generate a background or thumbnail image.

    Requirements 12.1, 12.2, 12.3: Validate request, forward to provider,
    return result as base64-encoded PNG.
    """
    # Decode base_image from base64 string if provided
    base_image_bytes: bytes | None = None
    if request.base_image:
        try:
            base_image_bytes = base64.b64decode(request.base_image)
        except Exception:
            from platform_api.exceptions import ValidationError

            raise ValidationError(
                "Invalid base_image: not valid base64.",
                details={"field": "base_image"},
            )

    image_request = ImageRequest(
        prompt=request.prompt,
        provider=request.provider,
        resolution=request.resolution,
        style_strength=request.style_strength,
        base_image=base_image_bytes,
    )

    image_bytes = await generation_service.submit_image(ctx.user_id, image_request)

    # Encode result as base64 for JSON transport
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    return ImageGenerationResponse(image_base64=image_b64)
