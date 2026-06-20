"""Generation service implementing GenerationServicePort.

Orchestrates song draft generation (LLM), Suno music generation,
and image generation with credit deduction, validation, and error handling.

Requirements: 10.1, 10.3, 10.4, 10.5, 10.6, 10.7, 11.1, 11.5, 11.7,
              12.1, 12.2, 12.5, 12.6, 7.1, 7.2, 7.3, 7.6, 8.1, 8.2, 8.3
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import unicodedata
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.exceptions import (
    ExternalServiceError,
    InsufficientCreditsError,
    ValidationError,
)
from platform_api.models.domain import SunoTask
from platform_api.models.enums import TaskStatus
from platform_api.ports.generation_port import (
    DraftRequest,
    ImageRequest,
    SongDraft,
    SunoRequest,
)
from platform_api.ports.key_pool_service_port import KeyPoolServicePort

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DRAFT_ATTEMPTS = 8
MAX_TITLE_ALBUM_ATTEMPTS = 6
IMAGE_MIN_RESOLUTION = 512
IMAGE_MAX_RESOLUTION = 2048
IMAGE_MAX_PROMPT_LENGTH = 2000
IMAGE_MAX_BASE64_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Repository / Client Protocols
# ---------------------------------------------------------------------------


class CreditServiceProtocol(Protocol):
    """Minimal protocol for credit deduction and refund operations."""

    async def deduct(self, user_id: str, amount: int, reason: str, ref_id: str) -> bool:
        ...

    async def refund(self, user_id: str, amount: int, reason: str, ref_id: str) -> None:
        ...


class CreditPricingRepository(Protocol):
    """Looks up per-model credit pricing."""

    async def get_price(self, model_identifier: str, operation_type: str) -> int | None:
        ...


class TaskRepository(Protocol):
    """Minimal protocol for Suno task persistence."""

    async def find_by_hash(self, user_id: UUID, request_hash: str) -> SunoTask | None:
        ...

    async def create(self, task: SunoTask) -> SunoTask:
        ...


class LlmClientProtocol(Protocol):
    """Minimal protocol for the LLM client."""

    async def generate_song_draft(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> dict[str, Any]:
        ...


class SunoClientProtocol(Protocol):
    """Minimal protocol for the Suno client."""

    async def submit_task(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool,
        callback_url: str | None,
    ) -> dict[str, Any]:
        ...


class FalClientProtocol(Protocol):
    """Minimal protocol for the Fal AI image client."""

    async def generate_image(
        self,
        *,
        prompt: str,
        model_id: str,
        width: int,
        height: int,
        num_images: int,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ...


class SlaiClientProtocol(Protocol):
    """Minimal protocol for the SLAI image client."""

    async def generate_image(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        style_strength: float,
        reference_image_base64: str | None,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# Pure Helper Functions
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """Normalize text for avoid-list comparison.

    Lowercases, strips whitespace, removes accents, and collapses spaces.
    """
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text


def validate_lyrics_structure(lyrics: str, structure_headers: list[str]) -> bool:
    """Validate that lyrics follow the required song structure.

    Rules (Requirement 10.3):
    - No content before the first header (if headers provided).
    - Headers appear in exact order.
    - Minimum content lines = max(16, len(headers) * 4) if headers,
      or 32 if no headers are provided.

    Args:
        lyrics: The full lyrics text.
        structure_headers: List of expected headers like "[Verse]", "[Chorus]".

    Returns:
        True if lyrics meet all structure constraints.
    """
    lines = [line.strip() for line in lyrics.strip().splitlines() if line.strip()]
    if not lines:
        return False

    if structure_headers:
        # No content before first header
        if not re.match(r"^\[.+\]$", lines[0]):
            return False

        # Headers appear in exact order
        found_headers = [line for line in lines if re.match(r"^\[.+\]$", line)]
        if found_headers != structure_headers:
            return False

        # Minimum content lines
        content_lines = [line for line in lines if not re.match(r"^\[.+\]$", line)]
        min_required = max(16, len(structure_headers) * 4)
        return len(content_lines) >= min_required
    else:
        # No headers provided — need at least 32 content lines
        content_lines = [line for line in lines if not re.match(r"^\[.+\]$", line)]
        return len(content_lines) >= 32


def compute_suno_request_hash(
    model: str, title: str, lyrics: str, style: str, instrumental: bool
) -> str:
    """Compute SHA-256 hash of a Suno request for deduplication (Requirement 11.5).

    Normalizes fields by stripping whitespace before hashing.
    """
    normalized = {
        "model": model.strip(),
        "title": title.strip(),
        "lyrics": lyrics.strip(),
        "style": style.strip(),
        "instrumental": bool(instrumental),
    }
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _check_avoid_list(value: str, avoid_list: list[str]) -> bool:
    """Return True if `value` matches any entry in the avoid list (normalized)."""
    normalized_value = _normalize_text(value)
    return any(_normalize_text(entry) == normalized_value for entry in avoid_list)


def _parse_resolution(resolution: str) -> tuple[int, int] | None:
    """Parse a resolution string like '1920x1080' into (width, height).

    Returns None if the format is invalid.
    """
    match = re.match(r"^(\d+)x(\d+)$", resolution.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


# ---------------------------------------------------------------------------
# Generation Service
# ---------------------------------------------------------------------------


class GenerationService:
    """Orchestrates AI generation requests with credit management.

    Implements GenerationServicePort: submit_draft, submit_suno, submit_image.

    Constructor Parameters:
        credit_service: Service for deducting/refunding credits.
        pricing_repo: Repository for looking up per-model pricing.
        task_repo: Repository for Suno task persistence and dedup lookup.
        llm_client: Client for LLM song draft generation.
        suno_client: Client for Suno music generation.
        fal_client: Client for Fal AI image generation.
        slai_client: Client for SLAI image generation.
        key_pool_service: Optional key pool service for multi-key management.
            When provided and the pool has entries for a provider, requests
            are routed through KeyPoolClientWrapper with automatic key selection
            and failover. When None or pool has zero entries for a provider,
            falls back to the existing single-key behavior (Req 8.1, 8.2, 8.3).
    """

    def __init__(
        self,
        credit_service: CreditServiceProtocol,
        pricing_repo: CreditPricingRepository,
        task_repo: TaskRepository,
        llm_client: LlmClientProtocol,
        suno_client: SunoClientProtocol,
        fal_client: FalClientProtocol,
        slai_client: SlaiClientProtocol,
        key_pool_service: KeyPoolServicePort | None = None,
    ) -> None:
        self._credit_service = credit_service
        self._pricing_repo = pricing_repo
        self._task_repo = task_repo
        self._llm_client = llm_client
        self._suno_client = suno_client
        self._fal_client = fal_client
        self._slai_client = slai_client
        self._key_pool_service = key_pool_service

        # Create client wrappers when key pool service is available (Req 8.1, 8.2)
        if key_pool_service is not None:
            from platform_api.clients.key_pool_client_wrapper import KeyPoolClientWrapper

            self._suno_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="suno")
            self._fal_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="fal")
            self._slai_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="slai")
            self._llm_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="openai")
            self._deepseek_pool_wrapper = KeyPoolClientWrapper(key_pool_service, provider="deepseek")
        else:
            self._suno_pool_wrapper = None
            self._fal_pool_wrapper = None
            self._slai_pool_wrapper = None
            self._llm_pool_wrapper = None
            self._deepseek_pool_wrapper = None

    # ------------------------------------------------------------------
    # Key Pool Integration Helpers (Requirements 8.1, 8.2, 8.3)
    # ------------------------------------------------------------------

    async def _pool_has_entries(self, provider: str) -> bool:
        """Check if the key pool has any entries for a provider.

        Returns False if key_pool_service is None or has zero entries,
        which triggers fallback to the system_settings single-key behavior.
        """
        if self._key_pool_service is None:
            return False
        try:
            status = await self._key_pool_service.get_pool_status(provider)
            return status.get("total_keys", 0) > 0
        except Exception:
            # If checking fails, fall back to direct client calls
            logger.warning(
                "Failed to check key pool entries for provider '%s', "
                "falling back to direct client call",
                provider,
            )
            return False

    # ------------------------------------------------------------------
    # submit_draft (Requirements 10.1, 10.3-10.7, 7.3, 7.6)
    # ------------------------------------------------------------------

    async def submit_draft(self, user_id: str, request: DraftRequest) -> SongDraft:
        """Generate a song draft (title, album, lyrics) via LLM.

        Workflow:
        1. Look up LLM pricing and deduct credits.
        2. Call LLM up to MAX_DRAFT_ATTEMPTS times.
        3. Validate lyrics structure on each response.
        4. Check title/album against avoid lists (up to MAX_TITLE_ALBUM_ATTEMPTS).
        5. Handle forced values (bypass LLM for those fields).
        6. On total failure, refund credits and raise error.
        """
        ref_id = str(uuid4())

        # Get pricing for LLM operation
        price = await self._pricing_repo.get_price("deepseek", "draft")
        if price is None:
            raise ValidationError(
                "Draft generation pricing is not configured.",
                details={"model": "deepseek", "operation": "draft"},
            )

        # Atomic credit deduction (Req 7.3)
        success = await self._credit_service.deduct(user_id, price, "llm_draft", ref_id)
        if not success:
            raise InsufficientCreditsError(
                "Insufficient credits for song draft generation.",
                details={"required": price},
            )

        # Extract structure headers from the structure text
        structure_headers = self._extract_headers(request.structure)

        # Build prompts
        system_prompt = self._build_draft_system_prompt(request)
        user_prompt = self._build_draft_user_prompt(request)

        # Map creativity_level (0-100) to temperature (0.0-1.5)
        temperature = request.creativity_level / 100.0 * 1.5

        last_failure_reason = "Unknown failure"
        title_album_attempts = 0

        try:
            for attempt in range(1, MAX_DRAFT_ATTEMPTS + 1):
                try:
                    response = await self._call_llm(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model="deepseek-chat",
                        temperature=temperature,
                    )
                except ExternalServiceError:
                    last_failure_reason = f"LLM provider error on attempt {attempt}"
                    logger.warning("LLM error on attempt %d/%d", attempt, MAX_DRAFT_ATTEMPTS)
                    continue

                # Parse LLM response (Req 10.7)
                parsed = self._parse_llm_response(response)
                if parsed is None:
                    last_failure_reason = f"Unparseable LLM response on attempt {attempt}"
                    logger.warning(
                        "Unparseable LLM response on attempt %d/%d",
                        attempt,
                        MAX_DRAFT_ATTEMPTS,
                    )
                    continue

                title = parsed["title"]
                album = parsed["album"]
                lyrics = parsed["lyrics"]

                # Handle forced values (Req 10.6)
                if request.forced_title:
                    title = request.forced_title
                if request.forced_album:
                    album = request.forced_album
                if request.forced_opening:
                    lyrics = self._inject_forced_opening(lyrics, request.forced_opening)

                # Validate lyrics structure (Req 10.3)
                if not validate_lyrics_structure(lyrics, structure_headers):
                    last_failure_reason = (
                        f"Lyrics structure validation failed on attempt {attempt}"
                    )
                    logger.warning(
                        "Structure validation failed attempt %d/%d",
                        attempt,
                        MAX_DRAFT_ATTEMPTS,
                    )
                    continue

                # Check title/album against avoid lists (Req 10.4)
                if not request.forced_title and _check_avoid_list(
                    title, request.avoid_titles
                ):
                    title_album_attempts += 1
                    if title_album_attempts >= MAX_TITLE_ALBUM_ATTEMPTS:
                        last_failure_reason = (
                            "Title uniqueness check exhausted all attempts"
                        )
                        break
                    last_failure_reason = (
                        f"Title '{title}' found in avoid list (attempt {title_album_attempts})"
                    )
                    continue

                if not request.forced_album and _check_avoid_list(
                    album, request.avoid_albums
                ):
                    title_album_attempts += 1
                    if title_album_attempts >= MAX_TITLE_ALBUM_ATTEMPTS:
                        last_failure_reason = (
                            "Album uniqueness check exhausted all attempts"
                        )
                        break
                    last_failure_reason = (
                        f"Album '{album}' found in avoid list (attempt {title_album_attempts})"
                    )
                    continue

                # All validations passed
                logger.info(
                    "Draft generated successfully for user %s on attempt %d",
                    user_id,
                    attempt,
                )
                return SongDraft(title=title, album=album, lyrics=lyrics)

            # All attempts exhausted (Req 10.5) — refund and raise
            await self._credit_service.refund(
                user_id, price, "draft_generation_failed", ref_id
            )
            raise ExternalServiceError(
                f"Song draft generation failed after all attempts. "
                f"Last failure: {last_failure_reason}",
                is_retryable=False,
                details={"last_failure_reason": last_failure_reason},
            )
        except (InsufficientCreditsError, ValidationError):
            raise
        except ExternalServiceError:
            raise
        except Exception as exc:
            # Unexpected error — refund credits (Req 7.6)
            await self._credit_service.refund(
                user_id, price, "draft_generation_error", ref_id
            )
            raise ExternalServiceError(
                f"Unexpected error during draft generation: {exc}",
                is_retryable=False,
                details={"error": str(exc)},
            ) from exc

    # ------------------------------------------------------------------
    # submit_suno (Requirements 11.1, 11.5, 11.7, 7.1, 7.6)
    # ------------------------------------------------------------------

    async def submit_suno(self, user_id: str, request: SunoRequest) -> str:
        """Submit a music generation request to Suno.

        Workflow:
        1. Compute SHA-256 request hash for dedup (Req 11.5).
        2. Check for existing task with same hash for the user.
        3. If not duplicate: deduct credits, forward to Suno, create record.
        4. On delivery failure: refund credits (Req 7.6).

        Returns:
            The Suno-assigned task ID (from existing record or new submission).
        """
        user_uuid = UUID(user_id)
        ref_id = str(uuid4())

        # Compute request hash for dedup (Req 11.5)
        request_hash = compute_suno_request_hash(
            model=request.model,
            title=request.title,
            lyrics=request.lyrics,
            style=request.style,
            instrumental=request.instrumental,
        )

        # Check for existing task with same hash
        existing_task = await self._task_repo.find_by_hash(user_uuid, request_hash)
        if existing_task is not None:
            logger.info(
                "Duplicate Suno request detected for user %s (hash=%s). "
                "Returning existing task %s",
                user_id,
                request_hash[:12],
                existing_task.id,
            )
            return str(existing_task.id)

        # Get pricing for Suno operation
        price = await self._pricing_repo.get_price(request.model.lower(), "suno")
        if price is None:
            raise ValidationError(
                "Suno generation pricing is not configured.",
                details={"model": request.model, "operation": "suno"},
            )

        # Atomic credit deduction (Req 7.1)
        success = await self._credit_service.deduct(user_id, price, "suno_generation", ref_id)
        if not success:
            raise InsufficientCreditsError(
                "Insufficient credits for Suno music generation.",
                details={"required": price},
            )

        # Forward to Suno API (Req 11.1)
        try:
            suno_response = await self._call_suno(
                model=request.model,
                title=request.title,
                lyrics=request.lyrics,
                style=request.style,
                instrumental=request.instrumental,
                callback_url=None,  # Client uses configured callback URL
            )
        except ExternalServiceError as exc:
            # Delivery failure — refund credits (Req 7.6)
            await self._credit_service.refund(
                user_id, price, "suno_delivery_failed", ref_id
            )
            raise exc

        # Extract external task ID from Suno response
        external_task_id = suno_response.get("taskId") or suno_response.get("task_id")
        if not external_task_id:
            # Unexpected response format — refund
            await self._credit_service.refund(
                user_id, price, "suno_invalid_response", ref_id
            )
            raise ExternalServiceError(
                "Suno API returned a response without a task ID.",
                is_retryable=False,
                details={"response": str(suno_response)[:500]},
            )

        # Create Suno_Task record
        task = SunoTask(
            id=uuid4(),
            user_id=user_uuid,
            request_hash=request_hash,
            model=request.model,
            title=request.title,
            lyrics=request.lyrics,
            style=request.style,
            instrumental=request.instrumental,
            external_task_id=external_task_id,
            status=TaskStatus.PENDING,
        )
        await self._task_repo.create(task)

        logger.info(
            "Suno task created for user %s: task_id=%s, external=%s",
            user_id,
            task.id,
            external_task_id,
        )
        return str(task.id)

    # ------------------------------------------------------------------
    # submit_image (Requirements 12.1, 12.2, 12.5, 12.6, 7.2, 7.6)
    # ------------------------------------------------------------------

    async def submit_image(self, user_id: str, request: ImageRequest) -> bytes:
        """Submit an image generation request to the configured provider.

        Workflow:
        1. Validate request parameters (resolution, style_strength, prompt, base64).
        2. Deduct credits atomically.
        3. Forward to provider (Fal AI or SLAI).
        4. Return generated PNG bytes.
        5. On failure: refund credits.

        Returns:
            The generated image as PNG bytes.
        """
        ref_id = str(uuid4())

        # --- Validation (Req 12.1, 12.6) ---
        self._validate_image_request(request)

        # Parse resolution
        dims = _parse_resolution(request.resolution)
        if dims is None:
            raise ValidationError(
                f"Invalid resolution format: '{request.resolution}'. Expected WIDTHxHEIGHT.",
                details={"resolution": request.resolution},
            )
        width, height = dims

        # Validate resolution bounds
        if not (IMAGE_MIN_RESOLUTION <= width <= IMAGE_MAX_RESOLUTION):
            raise ValidationError(
                f"Image width must be between {IMAGE_MIN_RESOLUTION} and {IMAGE_MAX_RESOLUTION}.",
                details={"width": width},
            )
        if not (IMAGE_MIN_RESOLUTION <= height <= IMAGE_MAX_RESOLUTION):
            raise ValidationError(
                f"Image height must be between {IMAGE_MIN_RESOLUTION} and {IMAGE_MAX_RESOLUTION}.",
                details={"height": height},
            )

        # Get pricing for image operation
        price = await self._pricing_repo.get_price(request.provider, "image")
        if price is None:
            raise ValidationError(
                "Image generation pricing is not configured.",
                details={"provider": request.provider, "operation": "image"},
            )

        # Atomic credit deduction (Req 7.2)
        success = await self._credit_service.deduct(user_id, price, "image_generation", ref_id)
        if not success:
            raise InsufficientCreditsError(
                "Insufficient credits for image generation.",
                details={"required": price},
            )

        # Forward to provider
        try:
            if request.provider == "fal":
                image_bytes = await self._generate_fal_image(request, width, height)
            elif request.provider == "slai":
                image_bytes = await self._generate_slai_image(request, width, height)
            else:
                await self._credit_service.refund(
                    user_id, price, "image_invalid_provider", ref_id
                )
                raise ValidationError(
                    f"Unsupported image provider: '{request.provider}'.",
                    details={"provider": request.provider},
                )
        except ExternalServiceError as exc:
            # Delivery failure — refund (Req 7.6)
            await self._credit_service.refund(
                user_id, price, "image_generation_failed", ref_id
            )
            raise exc

        except (InsufficientCreditsError, ValidationError):
            raise
        except Exception as exc:
            # Unexpected error — refund (Req 7.6)
            await self._credit_service.refund(
                user_id, price, "image_generation_error", ref_id
            )
            raise ExternalServiceError(
                f"Unexpected error during image generation: {exc}",
                is_retryable=False,
                details={"error": str(exc)},
            ) from exc

        logger.info(
            "Image generated for user %s via %s (%dx%d). Size: %d bytes",
            user_id,
            request.provider,
            width,
            height,
            len(image_bytes),
        )
        return image_bytes

    # ------------------------------------------------------------------
    # Private Helpers — Draft
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_headers(structure: str) -> list[str]:
        """Extract section headers like [Verse], [Chorus] from structure text."""
        if not structure or not structure.strip():
            return []
        return [
            line.strip()
            for line in structure.strip().splitlines()
            if line.strip() and re.match(r"^\[.+\]$", line.strip())
        ]

    @staticmethod
    def _build_draft_system_prompt(request: DraftRequest) -> str:
        """Build the system prompt for the LLM song draft generation."""
        return (
            "You are a professional songwriter. Generate a song with a title, "
            "album name, and lyrics. Return your response as valid JSON with "
            'exactly these keys: "title", "album", "lyrics".\n'
            "The lyrics must follow the provided song structure exactly, "
            "with section headers in square brackets on their own lines.\n"
            f"Language: {request.language}\n"
        )

    @staticmethod
    def _build_draft_user_prompt(request: DraftRequest) -> str:
        """Build the user prompt for draft generation with avoid lists."""
        parts = [f"Description: {request.description}"]
        if request.structure:
            parts.append(f"Structure:\n{request.structure}")
        if request.avoid_titles:
            avoid_str = ", ".join(request.avoid_titles[:200])
            parts.append(f"Avoid these titles: {avoid_str}")
        if request.avoid_albums:
            avoid_str = ", ".join(request.avoid_albums[:200])
            parts.append(f"Avoid these album names: {avoid_str}")
        if request.avoid_openings:
            avoid_str = ", ".join(request.avoid_openings[:200])
            parts.append(f"Avoid these opening lines: {avoid_str}")
        if request.forced_title:
            parts.append(f"The title MUST be: {request.forced_title}")
        if request.forced_album:
            parts.append(f"The album name MUST be: {request.forced_album}")
        if request.forced_opening:
            parts.append(
                f"The lyrics MUST start with: {request.forced_opening}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _parse_llm_response(response: dict[str, Any]) -> dict[str, str] | None:
        """Parse LLM chat completion response into title/album/lyrics.

        Requirement 10.7: Returns None if the response is unparseable
        (invalid JSON or missing required keys).
        """
        try:
            choices = response.get("choices", [])
            if not choices:
                return None

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return None

            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return None

            title = parsed.get("title")
            album = parsed.get("album")
            lyrics = parsed.get("lyrics")

            if not title or not album or not lyrics:
                return None

            if (
                not isinstance(title, str)
                or not isinstance(album, str)
                or not isinstance(lyrics, str)
            ):
                return None

            return {"title": title.strip(), "album": album.strip(), "lyrics": lyrics}
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _inject_forced_opening(lyrics: str, forced_opening: str) -> str:
        """Inject the forced opening as the first content lines after the first header.

        If the lyrics start with a header, insert the forced opening after it.
        Otherwise, prepend it to the beginning of the lyrics.
        """
        lines = lyrics.splitlines()
        if not lines:
            return forced_opening

        # If first line is a header, insert after it
        if re.match(r"^\[.+\]$", lines[0].strip()):
            return lines[0] + "\n" + forced_opening + "\n" + "\n".join(lines[1:])

        # Otherwise prepend
        return forced_opening + "\n" + lyrics

    # ------------------------------------------------------------------
    # Private Helpers — Image
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_image_request(request: ImageRequest) -> None:
        """Validate image request parameters (Req 12.1, 12.6).

        Checks:
        - style_strength in [0, 1]
        - prompt length 1-2000 chars
        - base_image (if provided) ≤ 10 MB
        """
        if not (0.0 <= request.style_strength <= 1.0):
            raise ValidationError(
                "style_strength must be between 0.0 and 1.0.",
                details={"style_strength": request.style_strength},
            )

        if not request.prompt or len(request.prompt) < 1:
            raise ValidationError(
                "Image prompt is required (1-2000 characters).",
                details={"prompt_length": 0},
            )

        if len(request.prompt) > IMAGE_MAX_PROMPT_LENGTH:
            raise ValidationError(
                f"Image prompt exceeds maximum length of {IMAGE_MAX_PROMPT_LENGTH} characters.",
                details={"prompt_length": len(request.prompt)},
            )

        if request.base_image is not None:
            if len(request.base_image) > IMAGE_MAX_BASE64_BYTES:
                raise ValidationError(
                    f"Base image exceeds maximum size of 10 MB.",
                    details={"base_image_bytes": len(request.base_image)},
                )

    async def _generate_fal_image(
        self, request: ImageRequest, width: int, height: int
    ) -> bytes:
        """Generate an image via Fal AI and return PNG bytes."""
        extra_params: dict[str, Any] = {}
        if request.base_image is not None:
            extra_params["image"] = base64.b64encode(request.base_image).decode()
            extra_params["strength"] = request.style_strength

        response = await self._call_fal(
            prompt=request.prompt,
            model_id="fal-ai/flux/schnell",
            width=width,
            height=height,
            num_images=1,
            extra_params=extra_params or None,
        )

        # Extract image bytes from response
        return self._extract_image_bytes(response, provider="fal")

    async def _generate_slai_image(
        self, request: ImageRequest, width: int, height: int
    ) -> bytes:
        """Generate an image via SLAI and return PNG bytes."""
        reference_b64: str | None = None
        if request.base_image is not None:
            reference_b64 = base64.b64encode(request.base_image).decode()

        response = await self._call_slai(
            prompt=request.prompt,
            width=width,
            height=height,
            style_strength=request.style_strength,
            reference_image_base64=reference_b64,
            extra_params=None,
        )

        # Extract image bytes from response
        return self._extract_image_bytes(response, provider="slai")

    # ------------------------------------------------------------------
    # Private Helpers — Key Pool Routing (Requirements 8.1, 8.2, 8.3)
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
    ) -> dict[str, Any]:
        """Route LLM call through key pool or fall back to direct client.

        If the key pool has entries for the 'openai' provider, uses the
        KeyPoolClientWrapper to inject keys with automatic failover.
        Otherwise, calls the LLM client directly (backward compat, Req 8.3).
        """
        if self._llm_pool_wrapper and await self._pool_has_entries("openai"):
            return await self._llm_pool_wrapper.execute(
                lambda api_key: self._llm_client.generate_song_draft(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=temperature,
                    api_key=api_key,
                )
            )
        if self._deepseek_pool_wrapper and await self._pool_has_entries("deepseek"):
            return await self._deepseek_pool_wrapper.execute(
                lambda api_key: self._llm_client.generate_song_draft(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model="deepseek-chat",
                    temperature=temperature,
                    api_key=api_key,
                )
            )
        if self._slai_pool_wrapper and await self._pool_has_entries("slai"):
            from platform_api.config import get_settings as _get_settings
            _slai_url = _get_settings().slai_api_base_url
            try:
                return await self._slai_pool_wrapper.execute(
                    lambda api_key: self._llm_client.generate_song_draft(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=model,
                        temperature=temperature,
                        api_key=api_key,
                        base_url=_slai_url,
                    )
                )
            except Exception as exc:
                # SLAI failed — fall through to direct client (DeepSeek)
                logger.warning("SLAI LLM draft failed, falling back to direct client: %s", exc)
        return await self._llm_client.generate_song_draft(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
        )

    async def generate_chat_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str = "deepseek-chat",
        temperature: float = 0.8,
        max_tokens: int = 600,
    ) -> str:
        """Generic LLM chat call with cross-provider fallback.

        Priority order:
        1. DeepSeek pool (provider 'deepseek') → api.deepseek.com
        2. SLAI pool (provider 'slai') → api.slai.shop
        3. OpenAI pool (provider 'openai') → legacy
        4. Direct LlmClient (static .env key) — last resort

        If DeepSeek fails, automatically retries with SLAI, then direct.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response: dict | None = None
        last_error: Exception | None = None

        # --- Attempt 1: DeepSeek pool (fastest, most reliable) ---
        if self._deepseek_pool_wrapper and await self._pool_has_entries("deepseek"):
            try:
                response = await self._deepseek_pool_wrapper.execute(
                    lambda api_key: self._llm_client.chat_completion(
                        messages=messages,
                        model="deepseek-chat",
                        temperature=temperature,
                        max_tokens=max_tokens,
                        api_key=api_key,
                    )
                )
            except Exception as exc:
                logger.warning("DeepSeek pool LLM failed, trying SLAI: %s", exc)
                last_error = exc

        # --- Attempt 2: SLAI pool (fallback) ---
        if response is None and self._slai_pool_wrapper and await self._pool_has_entries("slai"):
            try:
                from platform_api.config import get_settings as _get_settings
                _slai_url = _get_settings().slai_api_base_url
                response = await self._slai_pool_wrapper.execute(
                    lambda api_key: self._llm_client.chat_completion(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        api_key=api_key,
                        base_url=_slai_url,
                    )
                )
            except Exception as exc:
                logger.warning("SLAI LLM failed: %s", exc)
                last_error = exc

        # --- Attempt 3: OpenAI pool (legacy) ---
        if response is None and self._llm_pool_wrapper and await self._pool_has_entries("openai"):
            try:
                response = await self._llm_pool_wrapper.execute(
                    lambda api_key: self._llm_client.chat_completion(
                        messages=messages,
                        model="deepseek-chat",
                        temperature=temperature,
                        max_tokens=max_tokens,
                        api_key=api_key,
                    )
                )
            except Exception as exc:
                logger.warning("OpenAI pool LLM failed: %s", exc)
                last_error = exc

        # --- Attempt 4: Direct LlmClient (static .env key) ---
        if response is None:
            try:
                response = await self._llm_client.chat_completion(
                    messages=messages,
                    model="deepseek-chat",
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                logger.error("All LLM providers failed: %s", exc)
                last_error = exc

        if response is None:
            raise ExternalServiceError(
                f"All LLM providers failed. Last error: {last_error}",
                is_retryable=True,
                details={"provider": "llm"},
            )

        try:
            return (response["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalServiceError(
                "LLM returned an unexpected response shape.",
                is_retryable=False,
                details={"provider": "llm"},
            ) from exc

    async def _call_suno(
        self,
        *,
        model: str,
        title: str,
        lyrics: str,
        style: str,
        instrumental: bool,
        callback_url: str | None,
    ) -> dict[str, Any]:
        """Route Suno call through key pool or fall back to direct client.

        If the key pool has entries for the 'suno' provider, uses the
        KeyPoolClientWrapper to inject keys with automatic failover.
        Otherwise, calls the Suno client directly (backward compat, Req 8.3).
        """
        if self._suno_pool_wrapper and await self._pool_has_entries("suno"):
            return await self._suno_pool_wrapper.execute(
                lambda api_key: self._suno_client.submit_task(
                    model=model,
                    title=title,
                    lyrics=lyrics,
                    style=style,
                    instrumental=instrumental,
                    callback_url=callback_url,
                )
            )
        return await self._suno_client.submit_task(
            model=model,
            title=title,
            lyrics=lyrics,
            style=style,
            instrumental=instrumental,
            callback_url=callback_url,
        )

    async def _call_fal(
        self,
        *,
        prompt: str,
        model_id: str,
        width: int,
        height: int,
        num_images: int,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Route Fal AI call through key pool or fall back to direct client.

        If the key pool has entries for the 'fal' provider, uses the
        KeyPoolClientWrapper to inject keys with automatic failover.
        Otherwise, calls the Fal client directly (backward compat, Req 8.3).
        """
        if self._fal_pool_wrapper and await self._pool_has_entries("fal"):
            return await self._fal_pool_wrapper.execute(
                lambda api_key: self._fal_client.generate_image(
                    prompt=prompt,
                    model_id=model_id,
                    width=width,
                    height=height,
                    num_images=num_images,
                    extra_params=extra_params,
                )
            )
        return await self._fal_client.generate_image(
            prompt=prompt,
            model_id=model_id,
            width=width,
            height=height,
            num_images=num_images,
            extra_params=extra_params,
        )

    async def _call_slai(
        self,
        *,
        prompt: str,
        width: int,
        height: int,
        style_strength: float,
        reference_image_base64: str | None,
        extra_params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Route SLAI call through key pool or fall back to direct client.

        If the key pool has entries for the 'slai' provider, uses the
        KeyPoolClientWrapper to inject keys with automatic failover.
        Otherwise, calls the SLAI client directly (backward compat, Req 8.3).
        """
        if self._slai_pool_wrapper and await self._pool_has_entries("slai"):
            return await self._slai_pool_wrapper.execute(
                lambda api_key: self._slai_client.generate_image(
                    prompt=prompt,
                    width=width,
                    height=height,
                    style_strength=style_strength,
                    reference_image_base64=reference_image_base64,
                    extra_params=extra_params,
                )
            )
        return await self._slai_client.generate_image(
            prompt=prompt,
            width=width,
            height=height,
            style_strength=style_strength,
            reference_image_base64=reference_image_base64,
            extra_params=extra_params,
        )

    @staticmethod
    def _extract_image_bytes(response: dict[str, Any], *, provider: str) -> bytes:
        """Extract PNG image bytes from a provider response.

        Providers may return image data as base64 in various fields.
        Tries common response structures.
        """
        # Try common response shapes
        # Shape 1: {"images": [{"url": "data:image/png;base64,..."}]}
        images = response.get("images", [])
        if images and isinstance(images, list):
            first_image = images[0]
            if isinstance(first_image, dict):
                # base64 data URL
                url = first_image.get("url", "")
                if url.startswith("data:"):
                    # Extract base64 portion
                    _, _, b64_data = url.partition(",")
                    if b64_data:
                        return base64.b64decode(b64_data)
                # Direct base64 field
                b64 = first_image.get("base64") or first_image.get("data")
                if b64:
                    return base64.b64decode(b64)
            elif isinstance(first_image, str):
                # Direct base64 string
                return base64.b64decode(first_image)

        # Shape 2: {"image": "base64..."}
        image_data = response.get("image") or response.get("data")
        if image_data and isinstance(image_data, str):
            # Could be data URL or raw base64
            if image_data.startswith("data:"):
                _, _, b64_data = image_data.partition(",")
                return base64.b64decode(b64_data)
            return base64.b64decode(image_data)

        # Shape 3: {"output": "base64..."}
        output = response.get("output")
        if output and isinstance(output, str):
            return base64.b64decode(output)

        raise ExternalServiceError(
            f"Unable to extract image bytes from {provider} response.",
            is_retryable=False,
            details={"provider": provider, "response_keys": list(response.keys())},
        )
