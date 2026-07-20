"""Generation router endpoints.

Provides endpoints for song draft generation, Suno music generation,
Suno task status retrieval, and image generation. All endpoints require
User authentication.

Requirements: 11.1, 11.4, 12.1, 12.2, 12.3, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4
"""

from __future__ import annotations

import base64
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from platform_api.exceptions import ValidationError
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.middleware.rate_limit import enforce_rate_limit
from platform_api.models.enums import TaskStatus
from platform_api.ports.generation_port import DraftRequest, ImageRequest, SunoRequest
from platform_api.services.ai_routing_service import AIRoutingService
from platform_api.services.batch_service import BatchService
from platform_api.services.generation_service import GenerationService
from platform_api.services.prompt_service import PromptService
from platform_api.services.usage_enforcement_service import UsageEnforcementService

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
    secondary_language: str | None = Field(default=None, max_length=20)
    creativity_level: int = Field(ge=0, le=100, default=50)
    description: str | None = Field(default=None, max_length=5000)
    structure: str | None = Field(default=None, max_length=5000)
    description_id: UUID | None = None
    structure_id: UUID | None = None
    avoid_titles: list[str] = Field(default_factory=list, max_length=200)
    avoid_albums: list[str] = Field(default_factory=list, max_length=200)
    avoid_openings: list[str] = Field(default_factory=list, max_length=200)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None
    title_seed: str | None = Field(default=None, max_length=500)
    album_seed: str | None = Field(default=None, max_length=500)
    channel_profile_id: UUID | None = None


class DraftGenerationResponse(BaseModel):
    """Response containing the generated song draft."""

    title: str
    album: str
    lyrics: str


class LyricsPolishRequest(BaseModel):
    lyrics: str = Field(min_length=1, max_length=20000)
    strength: int = Field(ge=0, le=100, default=85)
    channel_profile_id: UUID | None = None
    batch_id: UUID | None = None
    song_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    album: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    structure: str | None = Field(default=None, max_length=2000)


class LyricsPolishResponse(BaseModel):
    lyrics: str
    suno_queued: bool = False


class LyricsSunoCheckRequest(BaseModel):
    lyrics: str = Field(default="", max_length=20000)
    title: str = Field(default="", max_length=255)
    learned_terms: list[str] = Field(default_factory=list, max_length=100)


class LyricsSunoRiskHitResponse(BaseModel):
    term: str
    severity: str
    start: int
    end: int
    suggestion: str


class SunoSanitizeReplacementResponse(BaseModel):
    field: str
    source: str
    target: str


class LyricsSunoCheckResponse(BaseModel):
    hits: list[LyricsSunoRiskHitResponse]
    sanitized_preview: str
    sanitized_title: str = ""
    replacements: list[SunoSanitizeReplacementResponse] = Field(default_factory=list)
    block_count: int
    warn_count: int


class SunoGenerationRequest(BaseModel):
    """Request body for submitting a Suno music generation task."""

    model: str = Field(pattern=r"^(V5|V5_5)$")
    title: str = Field(min_length=1, max_length=255)
    lyrics: str = Field(min_length=1)
    style: str = Field(min_length=1, max_length=255)
    instrumental: bool = False
    channel_profile_id: UUID | None = None


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
    provider: str = Field(pattern=r"^(fal|slai|openai|cala)$")
    kind: str = Field(default="background", pattern=r"^(background|thumbnail)$")
    resolution: str = Field(default="1920x1080", pattern=r"^\d+x\d+$")
    style_strength: float = Field(ge=0.0, le=1.0, default=0.6)
    base_image: str | None = None  # base64-encoded image (optional, ≤10MB)
    channel_profile_id: UUID | None = None


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


async def _get_enforcement_service() -> UsageEnforcementService:
    """Placeholder dependency for UsageEnforcementService — wired in wire_dependencies.py."""
    raise NotImplementedError(
        "UsageEnforcementService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_ai_routing_service() -> AIRoutingService:
    """Placeholder dependency for AIRoutingService — override via app.dependency_overrides."""
    raise NotImplementedError(
        "AIRoutingService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_prompt_service() -> PromptService:
    """Placeholder dependency for PromptService — override via app.dependency_overrides."""
    raise NotImplementedError(
        "PromptService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_profile_service():
    from platform_api.dependencies import get_profile_service

    return get_profile_service()


async def _get_batch_service() -> BatchService:
    """Placeholder dependency for BatchService — wired in wire_dependencies.py."""
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
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
EnforcementServiceDep = Annotated[UsageEnforcementService, Depends(_get_enforcement_service)]
AIRoutingServiceDep = Annotated[AIRoutingService, Depends(_get_ai_routing_service)]
PromptServiceDep = Annotated[PromptService, Depends(_get_prompt_service)]
ProfileServiceDep = Annotated[object, Depends(_get_profile_service)]
BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
TaskLookupDep = Annotated[TaskLookupPort, Depends(_get_task_lookup)]
CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]


async def _assert_owned_channel_profile(
    profile_service: object,
    *,
    user_id: str,
    channel_profile_id: UUID | None,
) -> None:
    if channel_profile_id is None:
        return
    await profile_service.require_owned_profile(UUID(user_id), channel_profile_id)


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
    http_request: Request,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
    enforcement_service: EnforcementServiceDep,
    routing_service: AIRoutingServiceDep,
    prompt_service: PromptServiceDep,
    profile_service: ProfileServiceDep,
) -> DraftGenerationResponse:
    """Generate a song draft (title, album, lyrics) via LLM.

    Requirement 10.1: Forward to configured LLM provider, return generated draft.
    Requirements 4.1, 4.2, 5.3: Resolve provider from AI routing assignments
    and use specific operation for pricing.
    Requirements 6.1–6.4: Enforce credit balance and usage quotas before generation.
    """
    await enforce_rate_limit(http_request, ctx.user_id)

    # Resolve routing — lyric/title/album slots (combined when assignments match)
    from platform_api.ai.purposes.draft_routing import build_draft_routing

    lyric_routing = await routing_service.resolve("lyric")
    title_routing = await routing_service.resolve("title")
    album_routing = await routing_service.resolve("album")
    draft_routing = build_draft_routing(lyric_routing, title_routing, album_routing)

    await _assert_owned_channel_profile(
        profile_service,
        user_id=ctx.user_id,
        channel_profile_id=request.channel_profile_id,
    )

    description_text = (request.description or "").strip()
    vocal_profile = None
    if request.description_id is not None:
        description = await prompt_service.get_description_for_access(
            request.description_id, UUID(ctx.user_id)
        )
        from platform_api.ai.purposes.vocal_profile import sanitize_production_description

        description_text = sanitize_production_description(description.content)
        vocal_profile = getattr(description, "vocal_profile", None)

    structure_text = (request.structure or "").strip()
    structure_mode = request.structure_mode
    if request.structure_id is not None:
        structure = await prompt_service.get_structure_for_access(
            request.structure_id, UUID(ctx.user_id)
        )
        structure_text = structure.content

    if not description_text.strip():
        raise ValidationError(
            "Song description is required before generating a draft.",
            details={"field": "description"},
        )

    from platform_api.services.generation_service import (
        STRUCTURE_MODE_AI_FREE,
        extract_structure_header_lines,
    )

    if structure_mode == STRUCTURE_MODE_AI_FREE:
        if request.structure_id is not None:
            raise ValidationError(
                "structure_id must be null when structure_mode is ai_free.",
                details={"field": "structure_id"},
            )
        structure_text = ""
    else:
        if not structure_text.strip():
            raise ValidationError(
                "Song structure is required before generating a draft.",
                details={"field": "structure"},
            )
        if not extract_structure_header_lines(structure_text):
            raise ValidationError(
                "Song structure must include at least one bracket section header like [Verse].",
                details={"field": "structure"},
            )

    from platform_api.ai.purposes.vocal_profile import (
        lyric_vocal_profile_for_batch,
        parse_vocal_profile,
        resolve_workspace_batch_languages,
        vocal_profile_to_dict,
    )

    description_profile = parse_vocal_profile(vocal_profile)
    primary_language, secondary_language = resolve_workspace_batch_languages(
        language=request.language,
        secondary_language=request.secondary_language,
    )
    lyric_profile = lyric_vocal_profile_for_batch(
        description_profile=description_profile,
        primary=primary_language,
        secondary=secondary_language,
    )

    draft_request = DraftRequest(
        language=primary_language,
        secondary_language=secondary_language,
        creativity_level=request.creativity_level,
        description=description_text,
        structure=structure_text,
        structure_mode=structure_mode,
        vocal_profile=vocal_profile_to_dict(lyric_profile),
        avoid_titles=request.avoid_titles,
        avoid_albums=request.avoid_albums,
        avoid_openings=request.avoid_openings,
        forced_title=request.forced_title,
        forced_album=request.forced_album,
        forced_opening=request.forced_opening,
        title_seed=request.title_seed,
        album_seed=request.album_seed,
    )

    # Match batch: charge draft meter + list price per lyric/title/album slot
    # before calling the LLM (H5).
    from platform_api.services.draft_billing import (
        deduct_split_draft_billing,
        draft_billing_slots,
    )

    draft_charged, draft_list_units = await deduct_split_draft_billing(
        enforcement_service,
        user_id=UUID(ctx.user_id),
        channel_profile_id=request.channel_profile_id,
        draft_routing=draft_routing,
        include_title=not request.forced_title,
        include_album=not request.forced_album,
    )
    draft_slots = draft_billing_slots(
        draft_routing,
        include_title=not request.forced_title,
        include_album=not request.forced_album,
    )

    try:
        draft = await generation_service.submit_draft(
            ctx.user_id,
            draft_request,
            provider=draft_routing.lyric.provider,
            model=draft_routing.lyric.sub_model or "",
            draft_routing=draft_routing,
            skip_pricing=True,
        )
    except Exception:
        refund = getattr(enforcement_service, "refund_failed_operation", None)
        if refund is not None and draft_slots:
            await refund(
                UUID(ctx.user_id),
                request.channel_profile_id,
                "lyric",
                str(draft_slots[0][1]),
                charged_credit_units=int(draft_charged or 0),
                sub_model=draft_slots[0][2],
                reason="draft_generation_failed",
                list_credit_units=int(draft_list_units or 0) or None,
                prior_ledger_recorded=True,
                count=len(draft_slots),
            )
        raise

    return DraftGenerationResponse(
        title=draft.title,
        album=draft.album,
        lyrics=draft.lyrics,
    )


@router.post(
    "/polish-lyrics",
    response_model=LyricsPolishResponse,
    status_code=200,
    summary="Rewrite lyrics text",
)
async def polish_lyrics(
    request: LyricsPolishRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
    enforcement_service: EnforcementServiceDep,
    routing_service: AIRoutingServiceDep,
    profile_service: ProfileServiceDep,
    batch_service: BatchServiceDep,
    background_tasks: BackgroundTasks,
) -> LyricsPolishResponse:
    """Rewrite existing lyrics via LLM (1 rewrite = 1 draft/lyric quota)."""
    await enforce_rate_limit(http_request, ctx.user_id)

    await _assert_owned_channel_profile(
        profile_service,
        user_id=ctx.user_id,
        channel_profile_id=request.channel_profile_id,
    )

    text_chain = await routing_service.resolve_text_chain("lyric")
    polish_chain = [
        (item.provider, item.sub_model or "")
        for item in text_chain
        if item.provider != "suno"
    ]
    if not polish_chain:
        raise ValidationError(
            "No chat LLM is available for lyrics rewrite. "
            "Configure DeepSeek, OpenAI, or SLAI for lyric generation.",
            details={"reason": "no_polish_providers"},
        )
    bill_provider, bill_model = polish_chain[0]
    charged = await enforcement_service.check_and_deduct(
        user_id=UUID(ctx.user_id),
        channel_profile_id=request.channel_profile_id,
        operation_type="lyric",
        ai_service=bill_provider,
        sub_model=bill_model or None,
    )

    try:
        suno_failure_hint: str | None = None
        if request.batch_id is not None and request.song_id is not None:
            suno_failure_hint = await batch_service.latest_suno_failure_hint(request.song_id)

        polished = await generation_service.polish_lyrics_text(
            ctx.user_id,
            request.lyrics,
            request.strength,
            bill_provider,
            bill_model,
            provider_chain=polish_chain,
            description=request.description,
            structure=request.structure,
            title=request.title,
            suno_failure_hint=suno_failure_hint,
        )
    except Exception:
        try:
            await enforcement_service.refund_failed_operation(
                UUID(ctx.user_id),
                request.channel_profile_id,
                "lyric",
                bill_provider,
                charged_credit_units=int(charged or 0),
                sub_model=bill_model or None,
                reason="polish_failed",
            )
        except Exception:
            logger.exception(
                "Failed to refund lyric polish for user=%s",
                ctx.user_id,
            )
        raise

    suno_queued = False
    if request.batch_id is not None and request.song_id is not None:
        try:
            await batch_service.validate_song_suno_retry(
                batch_id=request.batch_id,
                song_id=request.song_id,
                user_id=ctx.user_id,
                lyrics_override=polished,
                title_override=request.title,
            )
            background_tasks.add_task(
                batch_service.retry_song_suno,
                batch_id=request.batch_id,
                song_id=request.song_id,
                user_id=ctx.user_id,
                title=request.title,
                album=request.album,
                lyrics=polished,
            )
            suno_queued = True
        except Exception:
            logger.exception(
                "Polish succeeded but Suno queue failed for user=%s batch=%s song=%s",
                ctx.user_id,
                request.batch_id,
                request.song_id,
            )

    return LyricsPolishResponse(lyrics=polished, suno_queued=suno_queued)


@router.post(
    "/lyrics-suno-check",
    response_model=LyricsSunoCheckResponse,
    status_code=200,
    summary="Scan lyrics for Suno submission risks",
)
async def check_lyrics_for_suno(
    request: LyricsSunoCheckRequest,
    http_request: Request,
    ctx: CurrentUserDep,
) -> LyricsSunoCheckResponse:
    """Return hard-block and warning hits plus a sanitized preview for Suno lyrics."""
    await enforce_rate_limit(http_request, ctx.user_id)

    from platform_api.dependencies import get_suno_blocklist_service
    from platform_api.services.suno_lyrics_sanitize import (
        find_suno_risk_terms_in_text,
        sanitize_text_for_suno_with_changes,
    )

    runtime_config = await get_suno_blocklist_service().get_runtime_config()
    lyrics_hits = find_suno_risk_terms_in_text(
        request.lyrics,
        learned_terms=request.learned_terms,
        runtime_config=runtime_config,
    )
    title_hits = find_suno_risk_terms_in_text(
        request.title,
        learned_terms=request.learned_terms,
        runtime_config=runtime_config,
    )
    hits = lyrics_hits + title_hits
    sanitized_preview, lyrics_replacements = sanitize_text_for_suno_with_changes(
        request.lyrics,
        field="lyrics",
        blocked_terms=request.learned_terms,
        runtime_config=runtime_config,
    )
    sanitized_title, title_replacements = sanitize_text_for_suno_with_changes(
        request.title,
        field="title",
        blocked_terms=request.learned_terms,
        runtime_config=runtime_config,
    )
    block_count = sum(1 for hit in hits if hit.severity == "block")
    warn_count = sum(1 for hit in hits if hit.severity == "warn")
    return LyricsSunoCheckResponse(
        hits=[
            LyricsSunoRiskHitResponse(
                term=hit.term,
                severity=hit.severity,
                start=hit.start,
                end=hit.end,
                suggestion=hit.suggestion,
            )
            for hit in hits
        ],
        sanitized_preview=sanitized_preview,
        sanitized_title=sanitized_title,
        replacements=[
            SunoSanitizeReplacementResponse(
                field=item.field,
                source=item.source,
                target=item.target,
            )
            for item in [*lyrics_replacements, *title_replacements]
        ],
        block_count=block_count,
        warn_count=warn_count,
    )


@router.post(
    "/suno",
    response_model=SunoGenerationResponse,
    status_code=202,
    summary="Submit Suno music generation",
)
async def submit_suno(
    request: SunoGenerationRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
    enforcement_service: EnforcementServiceDep,
    routing_service: AIRoutingServiceDep,
    profile_service: ProfileServiceDep,
) -> SunoGenerationResponse:
    """Submit a music generation request to Suno.

    Requirement 11.1: Forward to Suno API, return task ID.
    Performs deduplication via request hash (Requirement 11.5).
    Requirements 4.1, 4.2, 5.3: Resolve provider from AI routing assignments
    and use specific operation for pricing.
    Requirements 6.1–6.4: Enforce credit balance and usage quotas before generation.
    """
    await enforce_rate_limit(http_request, ctx.user_id)

    await _assert_owned_channel_profile(
        profile_service,
        user_id=ctx.user_id,
        channel_profile_id=request.channel_profile_id,
    )
    # Resolve routing for music generation
    routing = await routing_service.resolve("music")

    # Enforce credit balance, daily limit, and monthly limit before generation.
    # Raises InsufficientCreditsError (402), QuotaExceededError (429),
    # or ExternalServiceError (503) if checks fail.
    await enforcement_service.check_and_deduct(
        user_id=UUID(ctx.user_id),
        channel_profile_id=request.channel_profile_id,
        operation_type="music",
        ai_service=routing.provider,
    )

    suno_request = SunoRequest(
        model=request.model,
        title=request.title,
        lyrics=request.lyrics,
        style=request.style,
        instrumental=request.instrumental,
    )

    task_id = await generation_service.submit_suno(ctx.user_id, suno_request, skip_pricing=True)

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
    http_request: Request,
    ctx: CurrentUserDep,
    generation_service: GenerationServiceDep,
    enforcement_service: EnforcementServiceDep,
    routing_service: AIRoutingServiceDep,
    profile_service: ProfileServiceDep,
) -> ImageGenerationResponse:
    """Generate a background or thumbnail image.

    Requirements 12.1, 12.2, 12.3: Validate request, forward to provider,
    return result as base64-encoded PNG.
    Requirements 4.6, 5.3: Resolve provider from AI routing assignments,
    override client-supplied provider, and use specific operation for pricing.
    Requirements 6.1–6.4: Enforce credit balance and usage quotas before generation.
    """
    await enforce_rate_limit(http_request, ctx.user_id)

    # Resolve routing — override client-supplied provider with admin-assigned one.
    # Thumbnail requests use the thumbnail_image assignment; everything else uses background_image.
    operation_type = (
        "thumbnail_image" if str(request.kind or "").strip().lower() == "thumbnail" else "background_image"
    )
    await _assert_owned_channel_profile(
        profile_service,
        user_id=ctx.user_id,
        channel_profile_id=request.channel_profile_id,
    )
    routing_chain = await routing_service.resolve_image_chain(operation_type)
    provider_models = [
        (item.provider, item.sub_model) for item in routing_chain
    ]
    max_credits = await enforcement_service.resolve_max_credits(
        operation_type, provider_models
    )
    await enforcement_service.preflight_quotas_and_balance(
        user_id=UUID(ctx.user_id),
        channel_profile_id=request.channel_profile_id,
        operation_type=operation_type,
        min_credits=max_credits,
    )
    primary_routing = routing_chain[0]

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
        provider=primary_routing.provider,
        model_id=primary_routing.sub_model,
        resolution=request.resolution,
        style_strength=request.style_strength,
        base_image=base_image_bytes,
    )

    quota_reserved = False
    operation_hold = None
    try:
        operation_hold = await enforcement_service.reserve_and_hold_before_provider(
            user_id=UUID(ctx.user_id),
            channel_profile_id=request.channel_profile_id,
            operation_type=operation_type,
            hold_credit_units=max_credits,
            ai_service=primary_routing.provider,
            sub_model=getattr(primary_routing, "sub_model", None),
        )
        quota_reserved = True

        outcome = await generation_service.submit_image_outcome(
            ctx.user_id,
            image_request,
            operation=operation_type,
            skip_pricing=True,
        )
        await enforcement_service.finalize_held_operation(
            user_id=UUID(ctx.user_id),
            operation_type=operation_type,
            ai_service=outcome.provider,
            sub_model=outcome.sub_model,
            hold=operation_hold,
        )
    except Exception:
        if quota_reserved:
            refund = getattr(enforcement_service, "refund_failed_operation", None)
            held = int(getattr(operation_hold, "held_units", 0) or 0) if operation_hold else 0
            if refund is not None:
                await refund(
                    UUID(ctx.user_id),
                    request.channel_profile_id,
                    operation_type,
                    primary_routing.provider,
                    charged_credit_units=held,
                    sub_model=getattr(primary_routing, "sub_model", None),
                    reason="image_generation_failed",
                    prior_ledger_recorded=held > 0,
                )
            else:
                await enforcement_service.release_operation_quota(
                    user_id=UUID(ctx.user_id),
                    channel_profile_id=request.channel_profile_id,
                    operation_type=operation_type,
                )
        raise

    image_bytes = outcome.image_bytes

    # Encode result as base64 for JSON transport
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    return ImageGenerationResponse(image_base64=image_b64)


# ---------------------------------------------------------------------------
# Local video / merge billing (desktop export + auto-merge)
# ---------------------------------------------------------------------------

_LOCAL_VIDEO_OPS = frozenset({"video", "video_manual", "video_merge"})
_LOCAL_AI_SERVICE = "local"


class LocalVideoConsumeRequest(BaseModel):
    """Bill one local video export or merge before desktop work starts."""

    operation_type: str = Field(
        ...,
        description=(
            "Must be 'video' (studio/pipeline per-track), "
            "'video_manual' (manual Video-page per-track), or 'video_merge' (concat)"
        ),
    )
    channel_profile_id: UUID | None = None
    count: int = Field(default=1, ge=1, le=50)
    ref_id: str | None = Field(default=None, max_length=200)


class LocalVideoConsumeResponse(BaseModel):
    operation_type: str
    billing: str
    charged_credit_units: int
    list_credit_units: int
    charge_key: str | None = None


class LocalVideoRefundRequest(BaseModel):
    operation_type: str
    channel_profile_id: UUID | None = None
    charged_credit_units: int = Field(default=0, ge=0)
    count: int = Field(default=1, ge=1, le=50)
    ref_id: str | None = Field(default=None, max_length=200)
    reason: str = Field(default="Local video operation failed", max_length=500)


@router.post(
    "/video/consume",
    response_model=LocalVideoConsumeResponse,
    status_code=200,
    summary="Consume plan/wallet for local video export or merge",
)
async def consume_local_video_operation(
    request: LocalVideoConsumeRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    enforcement_service: EnforcementServiceDep,
    profile_service: ProfileServiceDep,
) -> LocalVideoConsumeResponse:
    """Gate desktop Generate Video / Merge on plan remaining or wallet credits.

    Local FFmpeg COGS is $0; list prices come from credit_pricing (local/video,
    local/video_merge). Under plan allowance: meter +1, wallet $0 ledger.
    """
    await enforce_rate_limit(http_request, ctx.user_id)
    op = str(request.operation_type or "").strip().lower()
    if op not in _LOCAL_VIDEO_OPS:
        raise ValidationError(
            "operation_type must be 'video', 'video_manual', or 'video_merge'.",
            details={"operation_type": request.operation_type},
        )
    await _assert_owned_channel_profile(
        profile_service,
        user_id=ctx.user_id,
        channel_profile_id=request.channel_profile_id,
    )

    total_charged = 0
    list_units = 0
    billing = "plan_allowance"
    for _ in range(int(request.count)):
        charged = await enforcement_service.check_and_deduct(
            user_id=UUID(ctx.user_id),
            channel_profile_id=request.channel_profile_id,
            operation_type=op,
            ai_service=_LOCAL_AI_SERVICE,
        )
        total_charged += int(charged or 0)
        if charged and charged > 0:
            billing = "wallet"

    # Resolve list price once for response (micro-units).
    from platform_api.dependencies import get_credit_repo
    from platform_api.services.credit_pricing_service import lookup_pricing_entry

    pricing_repo = get_credit_repo()
    pricing_op = "video" if op == "video_manual" else op
    entry = await lookup_pricing_entry(pricing_repo, _LOCAL_AI_SERVICE, pricing_op, None)
    if entry is None and op == "video_manual":
        entry = await lookup_pricing_entry(pricing_repo, _LOCAL_AI_SERVICE, "video", None)
    list_units = int(entry["credits_per_operation"]) if entry else total_charged

    return LocalVideoConsumeResponse(
        operation_type=op,
        billing=billing,
        charged_credit_units=total_charged,
        list_credit_units=list_units * int(request.count),
        charge_key=request.ref_id,
    )


@router.post(
    "/video/refund",
    status_code=200,
    summary="Refund local video/merge after failed desktop export",
)
async def refund_local_video_operation(
    request: LocalVideoRefundRequest,
    http_request: Request,
    ctx: CurrentUserDep,
    enforcement_service: EnforcementServiceDep,
    profile_service: ProfileServiceDep,
) -> dict[str, str]:
    await enforce_rate_limit(http_request, ctx.user_id)
    op = str(request.operation_type or "").strip().lower()
    if op not in _LOCAL_VIDEO_OPS:
        raise ValidationError(
            "operation_type must be 'video', 'video_manual', or 'video_merge'.",
            details={"operation_type": request.operation_type},
        )
    await _assert_owned_channel_profile(
        profile_service,
        user_id=ctx.user_id,
        channel_profile_id=request.channel_profile_id,
    )
    await enforcement_service.refund_failed_operation(
        user_id=UUID(ctx.user_id),
        channel_profile_id=request.channel_profile_id,
        operation_type=op,
        ai_service=_LOCAL_AI_SERVICE,
        charged_credit_units=int(request.charged_credit_units or 0),
        reason=request.reason,
        ref_id=request.ref_id,
        count=int(request.count),
    )
    return {"status": "refunded", "operation_type": op}


class LocalVideoTelemetryRequest(BaseModel):
    """Desktop posts this after an export/merge finishes (success or user-stop)."""

    operation_type: str = Field(
        ...,
        description="'video' (studio/pipeline), 'video_manual', or 'video_merge'",
    )
    ref_id: str | None = Field(default=None, max_length=255)
    track_count: int = Field(default=0, ge=0, le=500)
    completed_count: int = Field(default=0, ge=0, le=500)
    duration_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    codec: str | None = Field(default=None, max_length=64)
    resolution: str | None = Field(default=None, max_length=32)
    fps: int | None = Field(default=None, ge=1, le=120)
    export_tier: str | None = Field(default=None, max_length=32)
    speed_mode: str | None = Field(default=None, max_length=32)
    hw_cpu: str | None = Field(default=None, max_length=255)
    hw_gpu: str | None = Field(default=None, max_length=255)
    hw_encoder: str | None = Field(default=None, max_length=64)
    app_version: str | None = Field(default=None, max_length=64)


@router.post(
    "/video/telemetry",
    status_code=200,
    summary="Record desktop export duration and hardware hints",
)
async def record_local_video_telemetry(
    request: LocalVideoTelemetryRequest,
    http_request: Request,
    ctx: CurrentUserDep,
) -> dict[str, str]:
    await enforce_rate_limit(http_request, ctx.user_id)
    op = str(request.operation_type or "").strip().lower()
    if op not in _LOCAL_VIDEO_OPS:
        raise ValidationError(
            "operation_type must be 'video', 'video_manual', or 'video_merge'.",
            details={"operation_type": request.operation_type},
        )
    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    await pool.execute(
        """
        INSERT INTO video_export_telemetry (
            user_id, operation_type, ref_id, track_count, completed_count,
            duration_ms, codec, resolution, fps, export_tier, speed_mode,
            hw_cpu, hw_gpu, hw_encoder, app_version
        ) VALUES (
            $1::uuid, $2::varchar, $3::varchar, $4, $5,
            $6, $7::varchar, $8::varchar, $9, $10::varchar, $11::varchar,
            $12::varchar, $13::varchar, $14::varchar, $15::varchar
        )
        """,
        ctx.user_id,
        op,
        request.ref_id,
        int(request.track_count or 0),
        int(request.completed_count or 0),
        request.duration_ms,
        request.codec,
        request.resolution,
        request.fps,
        request.export_tier,
        request.speed_mode,
        request.hw_cpu,
        request.hw_gpu,
        request.hw_encoder,
        request.app_version,
    )
    return {"status": "recorded", "operation_type": op}
