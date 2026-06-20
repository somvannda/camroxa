"""Batch orchestration service.

Manages batch creation with pre-cost checks, orchestrates draft generation
for each song, tracks per-song status through the pipeline, handles partial
failures, and creates image jobs when Suno tasks complete.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

from platform_api.exceptions import (
    InsufficientCreditsError,
    NotFoundError,
    ValidationError,
)
from platform_api.models.domain import Batch, ImageJob, Song, SunoTask
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Song status constants (matching DB schema)
# ---------------------------------------------------------------------------

SONG_STATUS_PENDING = "pending"
SONG_STATUS_DRAFT_READY = "draft_ready"
SONG_STATUS_DRAFT_FAILED = "draft_failed"
SONG_STATUS_SUNO_PENDING = "suno_pending"
SONG_STATUS_SUNO_SUCCESS = "suno_success"
SONG_STATUS_SUNO_FAILED = "suno_failed"

BATCH_STATUS_PENDING = "pending"
BATCH_STATUS_PROCESSING = "processing"
BATCH_STATUS_COMPLETED = "completed"
BATCH_STATUS_PARTIAL = "partial"
BATCH_STATUS_FAILED = "failed"


# ---------------------------------------------------------------------------
# Dependency Protocols
# ---------------------------------------------------------------------------


class BatchRepositoryProtocol(Protocol):
    """Protocol for the batch repository dependency."""

    async def create_batch(self, batch: Batch) -> Batch: ...
    async def get_batch_by_id(self, batch_id: UUID) -> Batch | None: ...
    async def get_batch_for_user(self, batch_id: UUID, user_id: UUID) -> Batch | None: ...
    async def update_batch_status(self, batch_id: UUID, status: str) -> None: ...
    async def create_songs(self, songs: list[Song]) -> list[Song]: ...
    async def get_songs_by_batch(self, batch_id: UUID) -> list[Song]: ...
    async def update_song_status(self, song_id: UUID, status: str) -> None: ...
    async def update_song_draft(
        self, song_id: UUID, title: str, album: str, lyrics: str
    ) -> None: ...
    async def create_suno_task(self, task: SunoTask) -> SunoTask: ...
    async def create_image_jobs(self, jobs: list[ImageJob]) -> list[ImageJob]: ...
    async def get_batch_status_counters(self, batch_id: UUID) -> dict[str, int]: ...


class CreditServiceProtocol(Protocol):
    """Protocol for the credit service dependency."""

    async def get_balance(self, user_id: str) -> int: ...
    async def deduct(self, user_id: str, amount: int, reason: str, ref_id: str) -> bool: ...
    async def refund(self, user_id: str, amount: int, reason: str, ref_id: str) -> None: ...


class CreditPricingProtocol(Protocol):
    """Protocol for credit pricing lookups."""

    async def get_price(self, model_identifier: str, operation_type: str) -> int: ...


class GenerationServiceProtocol(Protocol):
    """Protocol for the generation service dependency."""

    async def submit_draft(self, user_id: str, request: Any) -> Any: ...
    async def submit_suno(self, user_id: str, request: Any) -> str: ...


class ProfileRepositoryProtocol(Protocol):
    """Protocol for profile repository to look up image config."""

    async def get_by_id(self, profile_id: UUID) -> Any | None: ...


# ---------------------------------------------------------------------------
# Batch Service
# ---------------------------------------------------------------------------


class BatchService:
    """Batch orchestration service.

    Manages the lifecycle of batch generation runs:
    1. Pre-check total cost (LLM + Suno credits × song_count) before starting.
    2. Create batch and song records.
    3. Orchestrate draft generation for each song.
    4. Track per-song status through the pipeline.
    5. Handle partial failures (mark failed drafts, continue with successful ones).
    6. Create image jobs when Suno tasks complete based on profile image config.

    Args:
        batch_repo: Repository for batch and song persistence.
        credit_service: Service for balance queries and deductions.
        pricing_service: Service for looking up per-model credit pricing.
        generation_service: Service for draft and Suno generation.
        profile_repo: Repository for profile lookups (image config).
    """

    def __init__(
        self,
        batch_repo: BatchRepositoryProtocol,
        credit_service: CreditServiceProtocol,
        pricing_service: CreditPricingProtocol,
        generation_service: GenerationServiceProtocol,
        profile_repo: ProfileRepositoryProtocol,
    ) -> None:
        self._batch_repo = batch_repo
        self._credit_service = credit_service
        self._pricing_service = pricing_service
        self._generation_service = generation_service
        self._profile_repo = profile_repo

    # ------------------------------------------------------------------
    # Create Batch (Requirements 13.1, 13.6)
    # ------------------------------------------------------------------

    async def create_batch(
        self,
        user_id: str,
        ok_profile_id: str,
        alt_profile_id: str,
        song_count: int,
        language: str = "en",
        creativity_level: int = 50,
        pairing_mode: str = "match_key",
    ) -> Batch:
        """Create a new batch run after pre-checking total cost.

        Validates song_count (1-50), calculates total cost as
        (LLM_credits + Suno_credits) × song_count, checks user balance,
        and creates batch + song records.

        Args:
            user_id: The string UUID of the requesting user.
            ok_profile_id: UUID of the OK channel profile.
            alt_profile_id: UUID of the ALT channel profile.
            song_count: Number of songs to generate (1-50).
            language: Language code for generation (default "en").
            creativity_level: Creativity level 0-100 (default 50).
            pairing_mode: Description/structure pairing mode (default "match_key").

        Returns:
            The created Batch domain object.

        Raises:
            ValidationError: If song_count is outside [1, 50].
            InsufficientCreditsError: If user balance is insufficient for
                the total batch cost.
        """
        # Validate song_count
        if song_count < 1 or song_count > 50:
            raise ValidationError(
                "song_count must be between 1 and 50.",
                details={"song_count": song_count, "min": 1, "max": 50},
            )

        # Pre-check total cost (Requirement 13.6)
        total_cost = await self._calculate_batch_cost(song_count)
        current_balance = await self._credit_service.get_balance(user_id)

        if current_balance < total_cost:
            raise InsufficientCreditsError(
                f"Insufficient credits for batch of {song_count} songs. "
                f"Required: {total_cost}, available: {current_balance}.",
                details={
                    "required": total_cost,
                    "available": current_balance,
                    "song_count": song_count,
                },
            )

        # Create batch record
        batch = Batch(
            id=uuid4(),
            user_id=UUID(user_id),
            ok_profile_id=UUID(ok_profile_id),
            alt_profile_id=UUID(alt_profile_id),
            song_count=song_count,
            language=language,
            creativity_level=creativity_level,
            pairing_mode=pairing_mode,
            status=BATCH_STATUS_PENDING,
        )
        batch = await self._batch_repo.create_batch(batch)

        # Create song records (all start as 'pending')
        songs = [
            Song(
                id=uuid4(),
                batch_id=batch.id,
                batch_index=i,
                user_id=UUID(user_id),
                status=SONG_STATUS_PENDING,
            )
            for i in range(song_count)
        ]
        await self._batch_repo.create_songs(songs)

        logger.info(
            "Batch %s created for user %s with %d songs. Total cost: %d credits.",
            batch.id,
            user_id,
            song_count,
            total_cost,
        )
        return batch

    # ------------------------------------------------------------------
    # Get Batch Status (Requirement 13.5)
    # ------------------------------------------------------------------

    async def get_batch_status(
        self, batch_id: str, user_id: str
    ) -> dict[str, Any]:
        """Get batch status with all counters.

        Args:
            batch_id: The string UUID of the batch.
            user_id: The string UUID of the requesting user.

        Returns:
            Dict with batch_id and all status counters.

        Raises:
            NotFoundError: If batch doesn't exist or doesn't belong to user.
        """
        batch = await self._batch_repo.get_batch_for_user(
            UUID(batch_id), UUID(user_id)
        )
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": batch_id},
            )

        counters = await self._batch_repo.get_batch_status_counters(batch.id)

        return {
            "batch_id": str(batch.id),
            "status": batch.status,
            **counters,
        }

    # ------------------------------------------------------------------
    # Orchestrate Draft Generation (Requirements 13.2, 13.3, 13.4)
    # ------------------------------------------------------------------

    async def orchestrate_drafts(
        self,
        batch_id: UUID,
        user_id: str,
        draft_requests: list[Any],
    ) -> list[Song]:
        """Orchestrate draft generation for all songs in a batch.

        Generates drafts for each song sequentially, handling partial
        failures: failed drafts are marked as 'draft_failed' while
        successful ones proceed.

        Args:
            batch_id: The UUID of the batch.
            user_id: The string UUID of the user.
            draft_requests: List of DraftRequest objects, one per song.

        Returns:
            List of songs with their updated statuses.
        """
        await self._batch_repo.update_batch_status(batch_id, BATCH_STATUS_PROCESSING)

        songs = await self._batch_repo.get_songs_by_batch(batch_id)
        successful_songs: list[Song] = []

        for song, draft_request in zip(songs, draft_requests):
            try:
                # Submit draft generation
                draft = await self._generation_service.submit_draft(
                    user_id, draft_request
                )

                # Update song with generated draft data
                await self._batch_repo.update_song_draft(
                    song.id, draft.title, draft.album, draft.lyrics
                )
                song.title = draft.title
                song.album = draft.album
                song.lyrics = draft.lyrics
                song.status = SONG_STATUS_DRAFT_READY
                successful_songs.append(song)

                logger.info(
                    "Draft generated for song %s (batch %s, index %d): '%s'",
                    song.id,
                    batch_id,
                    song.batch_index,
                    draft.title,
                )

            except Exception as exc:
                # Mark failed drafts (Requirement 13.4)
                await self._batch_repo.update_song_status(
                    song.id, SONG_STATUS_DRAFT_FAILED
                )
                song.status = SONG_STATUS_DRAFT_FAILED
                logger.warning(
                    "Draft generation failed for song %s (batch %s, index %d): %s",
                    song.id,
                    batch_id,
                    song.batch_index,
                    str(exc),
                )

        # Update batch status based on results
        if not successful_songs:
            await self._batch_repo.update_batch_status(batch_id, BATCH_STATUS_FAILED)
        elif len(successful_songs) < len(songs):
            await self._batch_repo.update_batch_status(batch_id, BATCH_STATUS_PARTIAL)
        else:
            # All drafts succeeded — still processing (Suno next)
            pass

        logger.info(
            "Draft orchestration complete for batch %s: %d/%d succeeded.",
            batch_id,
            len(successful_songs),
            len(songs),
        )
        return songs

    # ------------------------------------------------------------------
    # Track Song Status (Requirement 13.3)
    # ------------------------------------------------------------------

    async def update_song_to_suno_pending(self, song_id: UUID) -> None:
        """Mark a song as suno_pending when Suno task is submitted.

        Args:
            song_id: The UUID of the song.
        """
        await self._batch_repo.update_song_status(song_id, SONG_STATUS_SUNO_PENDING)

    async def update_song_to_suno_success(self, song_id: UUID) -> None:
        """Mark a song as suno_success when Suno task completes.

        Args:
            song_id: The UUID of the song.
        """
        await self._batch_repo.update_song_status(song_id, SONG_STATUS_SUNO_SUCCESS)

    async def update_song_to_suno_failed(self, song_id: UUID) -> None:
        """Mark a song as suno_failed when Suno task fails.

        Args:
            song_id: The UUID of the song.
        """
        await self._batch_repo.update_song_status(song_id, SONG_STATUS_SUNO_FAILED)

    # ------------------------------------------------------------------
    # Image Job Creation on Suno Completion (Requirements 13.7, 13.8)
    # ------------------------------------------------------------------

    async def create_image_jobs_for_song(
        self,
        song: Song,
        batch: Batch,
    ) -> list[ImageJob]:
        """Create image jobs when a Suno task completes successfully.

        Determines which image jobs to create based on the profile's
        image_config mode:
        - bg_thumb: Create both background and thumbnail jobs.
        - thumb_only: Create only a thumbnail job.
        - bg_only: Create only a background job.

        Jobs are created for both OK and ALT profiles if both are configured.

        Args:
            song: The song that completed Suno generation.
            batch: The parent batch containing profile references.

        Returns:
            List of created ImageJob domain objects.
        """
        jobs: list[ImageJob] = []

        # Process OK profile
        if batch.ok_profile_id:
            ok_jobs = await self._create_jobs_for_profile(
                song=song,
                batch=batch,
                profile_id=batch.ok_profile_id,
                channel_role=ChannelRole.OK,
            )
            jobs.extend(ok_jobs)

        # Process ALT profile
        if batch.alt_profile_id:
            alt_jobs = await self._create_jobs_for_profile(
                song=song,
                batch=batch,
                profile_id=batch.alt_profile_id,
                channel_role=ChannelRole.ALT,
            )
            jobs.extend(alt_jobs)

        if jobs:
            await self._batch_repo.create_image_jobs(jobs)
            logger.info(
                "Created %d image jobs for song %s (batch %s).",
                len(jobs),
                song.id,
                batch.id,
            )

        return jobs

    async def on_suno_task_completed(
        self,
        song_id: UUID,
        batch_id: UUID,
    ) -> list[ImageJob]:
        """Handle Suno task completion for a song in a batch.

        Updates song status and creates image jobs based on profile config.

        Args:
            song_id: The UUID of the song whose Suno task completed.
            batch_id: The UUID of the batch.

        Returns:
            List of created image jobs (may be empty if no image config).
        """
        # Update song status
        await self.update_song_to_suno_success(song_id)

        # Get batch and song
        batch = await self._batch_repo.get_batch_by_id(batch_id)
        if batch is None:
            logger.warning("Batch %s not found for Suno completion.", batch_id)
            return []

        songs = await self._batch_repo.get_songs_by_batch(batch_id)
        song = next((s for s in songs if s.id == song_id), None)
        if song is None:
            logger.warning("Song %s not found in batch %s.", song_id, batch_id)
            return []

        # Create image jobs
        return await self.create_image_jobs_for_song(song, batch)

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    async def _calculate_batch_cost(self, song_count: int) -> int:
        """Calculate total batch cost: (LLM + Suno credits) × song_count.

        Looks up the configured pricing for LLM draft and Suno operations,
        then multiplies by the number of songs.

        Args:
            song_count: Number of songs in the batch.

        Returns:
            Total credit cost for the batch.

        Raises:
            ValidationError: If pricing is not configured for required operations.
        """
        try:
            llm_price = await self._pricing_service.get_price("deepseek", "draft")
        except Exception:
            raise ValidationError(
                "LLM draft generation pricing is not configured. Cannot estimate batch cost.",
                details={"model": "deepseek", "operation": "draft"},
            )

        try:
            suno_price = await self._pricing_service.get_price("v5", "suno")
        except Exception:
            # Try alternate model name
            try:
                suno_price = await self._pricing_service.get_price("v5_5", "suno")
            except Exception:
                raise ValidationError(
                    "Suno generation pricing is not configured. Cannot estimate batch cost.",
                    details={"model": "v5/v5_5", "operation": "suno"},
                )

        total_cost = (llm_price + suno_price) * song_count
        return total_cost

    async def _create_jobs_for_profile(
        self,
        song: Song,
        batch: Batch,
        profile_id: UUID,
        channel_role: ChannelRole,
    ) -> list[ImageJob]:
        """Create image jobs for a specific profile based on its image_config.

        Args:
            song: The song to generate images for.
            batch: The parent batch.
            profile_id: The UUID of the channel profile.
            channel_role: OK or ALT role.

        Returns:
            List of ImageJob domain objects (not yet persisted).
        """
        profile = await self._profile_repo.get_by_id(profile_id)
        if profile is None:
            logger.warning(
                "Profile %s not found for image job creation (batch %s).",
                profile_id,
                batch.id,
            )
            return []

        # Get image config from profile
        image_config = getattr(profile, "image_config", None) or {}
        mode = image_config.get("mode", "bg_thumb")

        # Determine which image kinds to create based on mode (Requirement 13.8)
        kinds: list[ImageKind] = []
        if mode == "bg_thumb":
            kinds = [ImageKind.BACKGROUND, ImageKind.THUMBNAIL]
        elif mode == "thumb_only":
            kinds = [ImageKind.THUMBNAIL]
        elif mode == "bg_only":
            kinds = [ImageKind.BACKGROUND]
        else:
            # Default to bg_thumb for unknown modes
            kinds = [ImageKind.BACKGROUND, ImageKind.THUMBNAIL]

        jobs: list[ImageJob] = []
        for kind in kinds:
            # Extract prompt from image_config based on kind
            if kind == ImageKind.BACKGROUND:
                prompt = image_config.get("background_prompt", "")
            else:
                prompt = image_config.get("thumbnail_prompt", "")

            # Substitute song title into prompt if placeholder present
            if song.title and prompt:
                prompt = prompt.replace("{title}", song.title)
                prompt = prompt.replace("{album}", song.album or "")

            job = ImageJob(
                id=uuid4(),
                song_id=song.id,
                user_id=batch.user_id,
                batch_id=batch.id,
                profile_id=profile_id,
                kind=kind,
                channel_role=channel_role,
                prompt=prompt or None,
                provider=image_config.get("provider", "fal"),
                resolution=image_config.get("resolution", "1920x1080"),
                style_strength=float(image_config.get("style_strength", 0.6)),
                status=TaskStatus.PENDING,
                attempt_count=0,
            )
            jobs.append(job)

        return jobs
