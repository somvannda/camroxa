"""Batch orchestration service.

Manages batch creation with pre-cost checks, orchestrates draft generation
for each song, tracks per-song status through the pipeline, handles partial
failures, and creates image jobs when Suno tasks complete.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from platform_api.services.billing_calendar import billing_today
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from platform_api.exceptions import (
    InsufficientCreditsError,
    NotFoundError,
    NoAvailableKeysError,
    QuotaExceededError,
    ValidationError,
)
from platform_api.models.billing_context import DraftBillingContext
from platform_api.models.domain import Batch, BatchChannelAssets, ImageJob, Song, SunoTask
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.ports.generation_port import DraftRequest, SongDraft, SunoRequest
from platform_api.services.channel_asset_service import (
    build_batch_channel_assets,
    compute_long_ready,
    compute_reel_ready,
    resolve_channel_asset_paths,
)
from platform_api.services.content_pool_service import (
    ClaimedPoolItem,
    build_forced_opening_text,
    claim_pool_item,
    finalize_pool_item,
    release_claimed_items,
)
from platform_api.services.credit_units import format_credit_log_amount
from platform_api.services import draft_progress_log as draft_log
from platform_api.services import credit_progress_log as credit_log
from platform_api.services.image_sample_rotation import ImageSampleRotationService
from platform_api.services.run_directory_planner import (
    build_run_folder_label,
    list_run_folder_entries,
    plan_run_directories,
    resolve_channel_run_dir,
)
from platform_api.services.suno_status_messages import (
    classify_suno_failure_type,
    is_suno_failure_status,
    is_suno_pending_status,
)
from platform_api.services.thumbnail_composite import (
    enrich_background_prompt,
    enrich_thumbnail_prompt,
    normalize_thumbnail_reference_mode,
)

if TYPE_CHECKING:
    from platform_api.services.image_job_service import ImageJobService

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


@dataclass(frozen=True)
class SunoSanitizedPayload:
    title: str
    lyrics: str
    style: str
    replacements: tuple[Any, ...]
    blocked_terms: tuple[str, ...]
    is_retry: bool


def _read_bool_setting(settings: dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = settings.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return default


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
    async def link_suno_task(self, task_id: UUID, song_id: UUID, batch_id: UUID) -> None: ...
    async def create_image_jobs(self, jobs: list[ImageJob]) -> list[ImageJob]: ...
    async def get_image_jobs_by_batch(self, batch_id: UUID) -> list[ImageJob]: ...
    async def upsert_batch_channel_assets(self, asset: BatchChannelAssets) -> BatchChannelAssets: ...
    async def update_image_job_status(
        self,
        job_id: UUID,
        user_id: UUID,
        *,
        status: TaskStatus,
        output_image_path: str | None = None,
        error: str | None = None,
        provider: str | None = None,
        attempt_count: int | None = None,
    ) -> None: ...
    async def get_batch_status_counters(self, batch_id: UUID) -> dict[str, int]: ...
    async def list_pending_suno_downloads(
        self, *, user_id: UUID, limit: int = 20
    ) -> list[dict[str, Any]]: ...
    async def update_suno_download_state(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        downloaded_ok: bool | None = None,
        downloaded_alt: bool | None = None,
        output_dir_ok: str | None = None,
        output_dir_alt: str | None = None,
    ) -> bool: ...
    async def get_latest_suno_task_for_song(self, song_id: UUID) -> SunoTask | None: ...


class CreditServiceProtocol(Protocol):
    """Protocol for the credit service dependency."""

    async def get_balance(self, user_id: str) -> int: ...
    async def deduct(self, user_id: str, amount: int, reason: str, ref_id: str) -> bool: ...
    async def refund(self, user_id: str, amount: int, reason: str, ref_id: str) -> None: ...


class CreditPricingProtocol(Protocol):
    """Protocol for credit pricing lookups."""

    async def get_price(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str | None = None,
    ) -> int: ...


class GenerationServiceProtocol(Protocol):
    """Protocol for the generation service dependency."""

    async def submit_draft(self, user_id: str, request: Any, *, provider: str, model: str) -> Any: ...
    async def submit_suno(self, user_id: str, request: Any) -> str: ...

class AIRoutingServiceProtocol(Protocol):
    async def resolve(self, operation: str) -> Any: ...


class ProfileRepositoryProtocol(Protocol):
    """Protocol for profile repository to look up image config."""

    async def get_by_id(self, profile_id: UUID) -> Any | None: ...


class PromptServiceProtocol(Protocol):
    """Protocol for resolving hidden admin-managed prompt content."""

    async def get_description(self, desc_id: UUID) -> Any: ...
    async def get_description_for_access(self, desc_id: UUID, user_id: UUID) -> Any: ...
    async def get_structure(self, struct_id: UUID) -> Any: ...
    async def get_structure_for_access(self, struct_id: UUID, user_id: UUID) -> Any: ...
    async def list_structures_workspace(self, user_id: UUID) -> list[Any]: ...


class SettingsServiceProtocol(Protocol):
    """Protocol for reading merged user settings during batch execution."""

    async def get_merged_settings(
        self, user_id: UUID, *, include_sensitive: bool = False
    ) -> dict[str, Any]: ...


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
        enforcement_service: Optional quota-first preflight for batch affordability.
    """

    def __init__(
        self,
        batch_repo: BatchRepositoryProtocol,
        credit_service: CreditServiceProtocol,
        pricing_service: CreditPricingProtocol,
        generation_service: GenerationServiceProtocol,
        profile_repo: ProfileRepositoryProtocol,
        ai_routing_service: AIRoutingServiceProtocol | None,
        prompt_service: PromptServiceProtocol | None = None,
        settings_service: SettingsServiceProtocol | None = None,
        enforcement_service: Any | None = None,
        image_job_service: ImageJobService | None = None,
        image_sample_rotation: ImageSampleRotationService | None = None,
    ) -> None:
        self._batch_repo = batch_repo
        self._credit_service = credit_service
        self._pricing_service = pricing_service
        self._generation_service = generation_service
        self._profile_repo = profile_repo
        self._ai_routing_service = ai_routing_service
        self._prompt_service = prompt_service
        self._settings_service = settings_service
        self._enforcement_service = enforcement_service
        self._image_job_service = image_job_service
        self._image_sample_rotation = image_sample_rotation

    # ------------------------------------------------------------------
    # Create Batch (Requirements 13.1, 13.6)
    # ------------------------------------------------------------------

    async def preflight_music_plan(
        self,
        user_id: str,
        *,
        ok_profile_ids: list[str],
        alt_profile_ids: list[str],
        from_date: date,
        to_date: date,
        song_count: int,
        auto_gen_image: bool,
        auto_gsuno: bool,
    ) -> dict[str, Any]:
        """Validate whether an entire automation plan can run before creating batches."""
        from collections import defaultdict

        from platform_api.services.credit_units import units_to_credits
        from platform_api.services.quota_display_service import get_monthly_quota_status

        if len(ok_profile_ids) != len(alt_profile_ids):
            return {
                "can_generate": False,
                "reason": "Primary and Secondary channel counts must match.",
            }
        if from_date > to_date:
            return {
                "can_generate": False,
                "reason": "Choose a valid inclusive date range.",
            }
        if song_count < 1 or song_count > 50:
            return {
                "can_generate": False,
                "reason": "Song count must be between 1 and 50.",
            }

        user_uuid = UUID(user_id)
        profile_pairs: list[tuple[UUID, UUID]] = []
        for ok_profile_id, alt_profile_id in zip(ok_profile_ids, alt_profile_ids):
            if ok_profile_id == alt_profile_id:
                return {
                    "can_generate": False,
                    "reason": "Primary and Secondary channels must be different.",
                }
            ok_profile = await self._profile_repo.get_by_id_for_user(
                UUID(ok_profile_id), user_uuid
            )
            alt_profile = await self._profile_repo.get_by_id_for_user(
                UUID(alt_profile_id), user_uuid
            )
            if ok_profile is None or alt_profile is None:
                return {
                    "can_generate": False,
                    "reason": "All selected channels must belong to your account.",
                }
            profile_pairs.append((UUID(ok_profile_id), UUID(alt_profile_id)))

        run_dates: list[date] = []
        cursor = from_date
        while cursor <= to_date:
            run_dates.append(cursor)
            cursor += timedelta(days=1)
        if not run_dates:
            return {
                "can_generate": False,
                "reason": "Choose a valid inclusive date range.",
            }

        settings: dict[str, Any] = {}
        if self._settings_service is not None:
            settings = await self._settings_service.get_merged_settings(
                user_id=user_uuid,
                include_sensitive=False,
            )
        billable_auto_gen_image = auto_gen_image and self._normalize_image_source_mode(settings) != "manual"

        batch_count = len(run_dates) * len(profile_pairs)
        total_songs = batch_count * song_count
        # Lyric + title per song + one album ≈ 2N+1 draft ops per batch.
        draft_ops_per_batch = song_count * 2 + 1
        total_draft_ops = batch_count * draft_ops_per_batch
        # Song packages are only burned when Auto-GSuno is enabled.
        billable_song_count = total_songs if auto_gsuno else 0
        total_wallet_cost = 0
        total_image_jobs = 0
        for run_date in run_dates:
            for ok_profile_id, alt_profile_id in profile_pairs:
                batch_cost = await self._calculate_batch_cost(
                    user_id=user_uuid,
                    song_count=song_count,
                    ok_profile_id=ok_profile_id,
                    alt_profile_id=alt_profile_id,
                    auto_gen_image=billable_auto_gen_image,
                    auto_gsuno=auto_gsuno,
                )
                total_wallet_cost += batch_cost
                if billable_auto_gen_image:
                    # One BG/TH set per album/channel — not per song.
                    total_image_jobs += (
                        await self._estimate_profile_image_job_count(ok_profile_id)
                        + await self._estimate_profile_image_job_count(alt_profile_id)
                    )

        wallet_balance = await self._credit_service.get_balance(user_id)
        songs_remaining: int | None = None
        images_remaining: int | None = None
        drafts_remaining: int | None = None
        covered_by_subscription = False

        if self._enforcement_service is not None:
            daily_songs: dict[tuple[UUID, date], int] = defaultdict(int)
            daily_images: dict[tuple[UUID, date], int] = defaultdict(int)
            daily_drafts: dict[tuple[UUID, date], int] = defaultdict(int)
            today = billing_today()
            for run_date in run_dates:
                for ok_profile_id, alt_profile_id in profile_pairs:
                    if run_date == today:
                        # Draft billing uses Primary (ok) profile only.
                        daily_drafts[(ok_profile_id, run_date)] += draft_ops_per_batch
                        if auto_gsuno:
                            daily_songs[(ok_profile_id, run_date)] += song_count
                            daily_songs[(alt_profile_id, run_date)] += song_count
                    if billable_auto_gen_image and run_date == today:
                        ok_jobs = await self._estimate_profile_image_job_count(ok_profile_id)
                        alt_jobs = await self._estimate_profile_image_job_count(alt_profile_id)
                        daily_images[(ok_profile_id, run_date)] += ok_jobs
                        daily_images[(alt_profile_id, run_date)] += alt_jobs

            try:
                await self._enforcement_service.enforce_fail_absorb_budget(user_uuid)
                ctx = await self._enforcement_service._resolve_subscription_context(user_uuid)
                for (profile_id, _run_date), count in daily_drafts.items():
                    if count <= 0:
                        continue
                    await self._enforcement_service._enforce_plan_quotas(
                        user_id=user_uuid,
                        channel_profile_id=profile_id,
                        operation_type="draft",
                        subscription_context=ctx,
                        additional_count=count,
                    )
                for (profile_id, _run_date), count in daily_songs.items():
                    if count <= 0:
                        continue
                    await self._enforcement_service._enforce_plan_quotas(
                        user_id=user_uuid,
                        channel_profile_id=profile_id,
                        operation_type="music",
                        subscription_context=ctx,
                        additional_count=count,
                    )
                for (profile_id, _run_date), count in daily_images.items():
                    if count <= 0:
                        continue
                    await self._enforcement_service._enforce_plan_quotas(
                        user_id=user_uuid,
                        channel_profile_id=profile_id,
                        operation_type="background_image",
                        subscription_context=ctx,
                        additional_count=count,
                    )

                from platform_api.services.billing_mode_service import subscription_covers_batch

                period_start = self._enforcement_service._period_start(ctx, billing_today())
                if ctx and ctx.plan is not None:
                    covered_by_subscription = await subscription_covers_batch(
                        plan=ctx.plan,
                        user_id=user_uuid,
                        song_count=billable_song_count,
                        usage_repo=self._enforcement_service._usage_repo,
                        period_start=period_start,
                        image_jobs=total_image_jobs,
                        draft_ops=total_draft_ops,
                    )
                if not covered_by_subscription and wallet_balance < total_wallet_cost:
                    return {
                        "can_generate": False,
                        "reason": (
                            f"Insufficient credits for this plan. "
                            f"Required {total_wallet_cost}, available {wallet_balance}."
                        ),
                        "batch_count": batch_count,
                        "total_songs": total_songs,
                        "total_wallet_cost": total_wallet_cost,
                        "wallet_balance": units_to_credits(wallet_balance),
                        "covered_by_subscription": False,
                        "credit_shortfall": total_wallet_cost - wallet_balance,
                    }
            except QuotaExceededError as exc:
                return {
                    "can_generate": False,
                    "reason": exc.message,
                    "batch_count": batch_count,
                    "total_songs": total_songs,
                    "total_wallet_cost": total_wallet_cost,
                    "wallet_balance": units_to_credits(wallet_balance),
                }
            except InsufficientCreditsError as exc:
                details = exc.details or {}
                return {
                    "can_generate": False,
                    "reason": exc.message,
                    "batch_count": batch_count,
                    "total_songs": total_songs,
                    "total_wallet_cost": int(details.get("required", total_wallet_cost)),
                    "wallet_balance": int(details.get("available", wallet_balance)),
                    "credit_shortfall": max(
                        0,
                        int(details.get("required", total_wallet_cost))
                        - int(details.get("available", wallet_balance)),
                    ),
                }
        elif wallet_balance < total_wallet_cost:
            return {
                "can_generate": False,
                "reason": (
                    f"Insufficient credits for this plan. "
                    f"Required {total_wallet_cost}, available {wallet_balance}."
                ),
                "batch_count": batch_count,
                "total_songs": total_songs,
                "total_wallet_cost": total_wallet_cost,
                "wallet_balance": units_to_credits(wallet_balance),
                "credit_shortfall": total_wallet_cost - wallet_balance,
            }

        if self._enforcement_service is not None:
            plan_repo = self._enforcement_service._plan_repo
            usage_repo = self._enforcement_service._usage_repo
            _songs_quota, songs_remaining = await get_monthly_quota_status(
                user_id=user_uuid,
                plan_repo=plan_repo,
                usage_repo=usage_repo,
                quota_field="songs",
            )
            _images_quota, images_remaining = await get_monthly_quota_status(
                user_id=user_uuid,
                plan_repo=plan_repo,
                usage_repo=usage_repo,
                quota_field="images",
            )
            _drafts_quota, drafts_remaining = await get_monthly_quota_status(
                user_id=user_uuid,
                plan_repo=plan_repo,
                usage_repo=usage_repo,
                quota_field="drafts",
            )

        return {
            "can_generate": True,
            "reason": None,
            "batch_count": batch_count,
            "total_songs": total_songs,
            "total_wallet_cost": total_wallet_cost,
            "wallet_balance": units_to_credits(wallet_balance),
            "covered_by_subscription": covered_by_subscription,
            "songs_remaining": songs_remaining,
            "images_remaining": images_remaining,
            "drafts_remaining": drafts_remaining,
            "credit_shortfall": None,
        }

    async def create_batch(
        self,
        user_id: str,
        ok_profile_id: str,
        alt_profile_id: str,
        song_count: int,
        description_id: str | None = None,
        structure_id: str | None = None,
        structure_mode: str = "template",
        shuffle_structure: bool = False,
        auto_gen_image: bool = False,
        auto_gsuno: bool = False,
        language: str = "en",
        secondary_language: str | None = None,
        creativity_level: int = 50,
        pairing_mode: str = "match_key",
        from_date: date | None = None,
        to_date: date | None = None,
        ok_run_dir: str | None = None,
        alt_run_dir: str | None = None,
        album: str | None = None,
    ) -> Batch:
        """Create a new batch run after pre-checking total cost.

        Validates song_count (1-50), calculates total cost for the enabled
        draft/Suno/image automation path, checks user balance, and creates
        batch + song records.

        Args:
            user_id: The string UUID of the requesting user.
            ok_profile_id: UUID of the Primary channel profile.
            alt_profile_id: UUID of the Secondary channel profile.
            song_count: Number of songs to generate (1-50).
            language: Language code for generation (default "en").
            creativity_level: Creativity level 0-100 (default 50).
            pairing_mode: Description/structure pairing mode (default "match_key").
            from_date: Inclusive planned start date for the batch window.
            to_date: Inclusive planned end date for the batch window.

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
        if from_date is None or to_date is None:
            raise ValidationError(
                "from_date and to_date are required.",
                details={"from_date": from_date, "to_date": to_date},
            )
        if to_date < from_date:
            raise ValidationError(
                "to_date must be on or after from_date.",
                details={"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
            )

        from platform_api.services.generation_service import STRUCTURE_MODE_AI_FREE, STRUCTURE_MODE_TEMPLATE

        normalized_mode = str(structure_mode or STRUCTURE_MODE_TEMPLATE).strip()
        if normalized_mode not in {STRUCTURE_MODE_TEMPLATE, STRUCTURE_MODE_AI_FREE}:
            raise ValidationError(
                "structure_mode must be 'template' or 'ai_free'.",
                details={"structure_mode": structure_mode},
            )
        if normalized_mode == STRUCTURE_MODE_AI_FREE:
            if structure_id:
                raise ValidationError(
                    "structure_id must be null when structure_mode is ai_free.",
                    details={"structure_id": structure_id},
                )
            if shuffle_structure:
                raise ValidationError(
                    "shuffle_structure cannot be enabled when structure_mode is ai_free.",
                    details={"shuffle_structure": shuffle_structure},
                )
            structure_id = None

        user_uuid = UUID(user_id)
        ok_profile = await self._profile_repo.get_by_id_for_user(
            UUID(ok_profile_id), user_uuid
        )
        alt_profile = await self._profile_repo.get_by_id_for_user(
            UUID(alt_profile_id), user_uuid
        )
        if ok_profile is None or alt_profile is None:
            raise ValidationError(
                "Both channel profiles must exist and belong to your account.",
                details={
                    "ok_profile_id": ok_profile_id,
                    "alt_profile_id": alt_profile_id,
                },
            )

        resolved_language, resolved_secondary = await self._resolve_batch_languages(
            user_id=user_id,
            description_id=description_id,
            language=language,
            secondary_language=secondary_language,
        )

        settings: dict[str, Any] = {}
        if self._settings_service is not None:
            settings = await self._settings_service.get_merged_settings(
                user_id=UUID(user_id),
                include_sensitive=False,
            )
        billable_auto_gen_image = auto_gen_image and self._normalize_image_source_mode(settings) != "manual"

        # Run folders are planned after the first successful draft album exists.
        resolved_ok = str(ok_run_dir or "").strip() or None
        resolved_alt = str(alt_run_dir or "").strip() or None

        # Pre-check total cost (Requirement 13.6)
        total_cost = await self._calculate_batch_cost(
            user_id=UUID(user_id),
            song_count=song_count,
            ok_profile_id=UUID(ok_profile_id),
            alt_profile_id=UUID(alt_profile_id),
            auto_gen_image=billable_auto_gen_image,
            auto_gsuno=auto_gsuno,
        )
        image_jobs = 0
        if billable_auto_gen_image:
            image_jobs = (
                await self._estimate_profile_image_job_count(UUID(ok_profile_id))
                + await self._estimate_profile_image_job_count(UUID(alt_profile_id))
            )

        if self._enforcement_service is not None:
            await self._enforcement_service.preflight_batch_cost(
                UUID(user_id),
                song_count=song_count if auto_gsuno else 0,
                total_wallet_cost=total_cost,
                image_jobs=image_jobs,
                draft_ops=song_count * 2 + 1,
                ok_profile_id=UUID(ok_profile_id),
                alt_profile_id=UUID(alt_profile_id),
            )
        else:
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
            language=resolved_language,
            secondary_language=resolved_secondary,
            creativity_level=creativity_level,
            pairing_mode=pairing_mode,
            status=BATCH_STATUS_PENDING,
            auto_gen_image=auto_gen_image,
            auto_gsuno=auto_gsuno,
            planned_from_date=from_date,
            planned_to_date=to_date,
            ok_run_dir=resolved_ok,
            alt_run_dir=resolved_alt,
            ok_album=str(album or "").strip() or None,
            structure_mode=normalized_mode,
        )
        batch = await self._batch_repo.create_batch(batch)

        current_balance = await self._credit_service.get_balance(user_id)
        credit_log.log_batch_preflight(
            user_id=user_id,
            batch_id=batch.id,
            song_count=song_count,
            total_cost_units=total_cost,
            current_balance_units=current_balance,
        )

        # Create song records (all start as 'pending')
        structure_ids = await self._resolve_song_structure_ids(
            user_id=UUID(user_id),
            batch_id=batch.id,
            song_count=song_count,
            structure_id=structure_id,
            shuffle_structure=shuffle_structure
            or _read_bool_setting(settings, "shuffleStructure"),
            structure_mode=normalized_mode,
        )
        songs = [
            Song(
                id=uuid4(),
                batch_id=batch.id,
                batch_index=i,
                user_id=UUID(user_id),
                description_id=UUID(description_id) if description_id else None,
                structure_id=structure_ids[i],
                status=SONG_STATUS_PENDING,
            )
            for i in range(song_count)
        ]
        await self._batch_repo.create_songs(songs)

        draft_log.log_batch_created(
            batch_id=str(batch.id),
            user_id=user_id,
            song_count=song_count,
            total_cost=format_credit_log_amount(total_cost),
        )
        return batch

    async def execute_batch(self, batch_id: UUID | str, user_id: str) -> Batch | None:
        """Run the created batch through draft generation and optional Suno submission.

        This is intended for background execution after the public `POST /batches`
        route persists the batch and song rows.
        """
        batch_uuid = UUID(str(batch_id))
        batch = await self._batch_repo.get_batch_for_user(batch_uuid, UUID(user_id))
        if batch is None:
            logger.warning(
                "Skipping batch execution because batch %s was not found for user %s.",
                batch_uuid,
                user_id,
            )
            return None

        try:
            draft_requests = self._build_draft_requests(batch)
            use_content_pools, unique_opening = await self._load_music_pool_settings(user_id)
            songs = await self._batch_repo.get_songs_by_batch(batch.id)
            draft_log.log_batch_execution_started(
                batch_id=str(batch.id),
                song_count=len(songs),
            )
            songs = await self.orchestrate_drafts(
                batch_id=batch.id,
                user_id=user_id,
                draft_requests=draft_requests,
                channel_profile_id=batch.ok_profile_id,
                use_content_pools=use_content_pools,
                unique_opening=unique_opening,
            )
            successful_songs = [song for song in songs if song.status == SONG_STATUS_DRAFT_READY]

            if successful_songs:
                batch = await self._batch_repo.get_batch_by_id(batch.id) or batch
                ok_album = str(batch.ok_album or successful_songs[0].album or "").strip()
                alt_album = str(batch.alt_album or "").strip() or None
                batch = await self._assign_batch_run_directories_if_needed(
                    batch,
                    ok_album=ok_album,
                    alt_album=alt_album,
                )

            if not successful_songs:
                await self.refresh_batch_status(batch.id)
                return batch

            if not batch.auto_gsuno:
                await self.refresh_batch_status(batch.id)
                return batch

            suno_model = await self._resolve_suno_model(batch.user_id)
            draft_log.log_suno_batch_started(
                batch_id=str(batch.id),
                song_count=len(successful_songs),
                model=suno_model,
            )
            submitted_count = 0
            failed_count = 0
            for song in successful_songs:
                title = str(song.title or "").strip() or "Untitled"
                try:
                    draft_log.log_suno_submit_started(
                        batch_id=str(batch.id),
                        song_number=song.batch_index + 1,
                        title=title,
                        model=suno_model,
                    )
                    task_id = await self._submit_song_to_suno(
                        song=song,
                        batch=batch,
                        user_id=user_id,
                        model=suno_model,
                    )
                    draft_log.log_suno_submitted(
                        batch_id=str(batch.id),
                        song_number=song.batch_index + 1,
                        title=title,
                        task_id=task_id,
                    )
                    submitted_count += 1
                except Exception as exc:
                    await self.update_song_to_suno_failed(song.id)
                    reason = str(exc) or exc.__class__.__name__
                    draft_log.log_suno_submit_failed(
                        batch_id=str(batch.id),
                        song_number=song.batch_index + 1,
                        title=title,
                        reason=reason,
                        song_id=str(song.id),
                    )
                    self._log_suno_failure_metric(
                        batch_id=batch.id,
                        song_id=song.id,
                        error_message=reason,
                        is_retry=False,
                    )
                    logger.warning(
                        "Suno submission failed for song %s in batch %s: %s",
                        song.id,
                        batch.id,
                        reason,
                    )
                    failed_count += 1
            draft_log.log_suno_batch_submit_summary(
                batch_id=str(batch.id),
                submitted=submitted_count,
                failed=failed_count,
                total=len(successful_songs),
            )

            await self.refresh_batch_status(batch.id)
            return batch
        except Exception:
            await self._batch_repo.update_batch_status(batch.id, BATCH_STATUS_FAILED)
            logger.exception(
                "Batch execution failed unexpectedly for batch %s and user %s.",
                batch.id,
                user_id,
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
            "ok_run_dir": batch.ok_run_dir,
            "alt_run_dir": batch.alt_run_dir,
            **counters,
        }

    async def get_batch_for_user(self, *, batch_id: UUID, user_id: UUID) -> Batch | None:
        return await self._batch_repo.get_batch_for_user(batch_id, user_id)

    # ------------------------------------------------------------------
    # Orchestrate Draft Generation (Requirements 13.2, 13.3, 13.4)
    # ------------------------------------------------------------------

    async def _generate_song_draft(
        self,
        *,
        batch_id: UUID,
        user_id: str,
        song: Song,
        draft_request: DraftRequest,
        draft_routing: Any,
        channel_profile_id: UUID | None,
        use_content_pools: bool,
        unique_opening: bool,
        batch_album: str | None,
        batch_titles: list[str],
    ) -> tuple[Song, str | None, list[str]]:
        """Generate a draft for one song and return updated batch album/title context."""
        claimed_items: list[ClaimedPoolItem] = []
        draft_charged = 0
        draft_list_units = 0
        draft_billing_applied = False
        try:
            prepared_request = await self._resolve_song_prompt_content(song, draft_request)
            if batch_album:
                prepared_request = replace(prepared_request, forced_album=batch_album)
            if batch_titles:
                prepared_request = replace(
                    prepared_request,
                    avoid_titles=[*prepared_request.avoid_titles, *batch_titles],
                )

            if use_content_pools:
                reservation_token = str(uuid4())
                reservation_owner = f"{user_id}:{batch_id}:{song.batch_index}"
                title_item = await claim_pool_item(
                    kind="titles",
                    reservation_owner=reservation_owner,
                    reservation_token=reservation_token,
                )
                claimed_items.append(title_item)
                album_item: ClaimedPoolItem | None = None
                if not batch_album:
                    album_item = await claim_pool_item(
                        kind="albums",
                        reservation_owner=reservation_owner,
                        reservation_token=reservation_token,
                    )
                    claimed_items.append(album_item)
                opening_item: ClaimedPoolItem | None = None
                if unique_opening:
                    opening_item = await claim_pool_item(
                        kind="openings",
                        reservation_owner=reservation_owner,
                        reservation_token=reservation_token,
                    )
                    claimed_items.append(opening_item)

                forced_opening = (
                    build_forced_opening_text(
                        line1=opening_item.text,
                        line2=opening_item.secondary_text,
                    )
                    if opening_item is not None
                    else prepared_request.forced_opening
                )
                prepared_request = replace(
                    prepared_request,
                    title_seed=title_item.text,
                    album_seed=album_item.text if album_item is not None else None,
                    forced_opening=forced_opening or None,
                )

            prepared_request = replace(
                prepared_request,
                batch_id=str(batch_id),
                song_number=song.batch_index + 1,
                song_id=str(song.id),
            )

            if self._enforcement_service is not None:
                draft_charged, draft_list_units = await self._deduct_split_draft_billing(
                    user_id=user_id,
                    channel_profile_id=channel_profile_id,
                    draft_routing=draft_routing,
                    draft_request=prepared_request,
                )
                draft_billing_applied = True

            draft = await self._generation_service.submit_draft(
                user_id,
                prepared_request,
                provider=draft_routing.lyric.provider,
                model=draft_routing.lyric.sub_model or "",
                draft_routing=draft_routing,
                billing_context=DraftBillingContext(
                    source="batch",
                    batch_id=str(batch_id),
                    song_id=str(song.id),
                    batch_index=song.batch_index,
                ),
                skip_pricing=self._enforcement_service is not None,
            )

            if use_content_pools and claimed_items:
                for item in claimed_items:
                    await finalize_pool_item(item=item)
                claimed_items = []

            album = str(draft.album or "").strip()
            if not batch_album and album:
                batch_album = album
            elif batch_album:
                album = batch_album
                draft = SongDraft(title=draft.title, album=album, lyrics=draft.lyrics)

            title = str(draft.title or "").strip()
            if title:
                batch_titles = [*batch_titles, title]

            await self._batch_repo.update_song_draft(
                song.id, draft.title, album, draft.lyrics
            )
            song.title = draft.title
            song.album = album
            song.lyrics = draft.lyrics
            song.status = SONG_STATUS_DRAFT_READY

            logger.info(
                "Draft generated for song %s (batch %s, index %d): '%s'",
                song.id,
                batch_id,
                song.batch_index,
                draft.title,
            )
            return song, batch_album, batch_titles
        except Exception as exc:
            if claimed_items:
                await release_claimed_items(claimed_items)
            if draft_billing_applied and self._enforcement_service is not None:
                # Drafts never burn song units; still refund wallet and mark
                # plan_allowance failures as platform-absorbed COGS.
                try:
                    await self._enforcement_service.refund_failed_operation(
                        UUID(user_id),
                        channel_profile_id,
                        "lyric",
                        str(draft_routing.lyric.provider),
                        charged_credit_units=draft_charged,
                        sub_model=draft_routing.lyric.sub_model,
                        reason="draft_generation_failed",
                        ref_id=str(song.id),
                        list_credit_units=draft_list_units or None,
                        prior_ledger_recorded=True,
                    )
                except Exception:
                    logger.exception(
                        "Failed to refund draft billing for song %s after draft failure.",
                        song.id,
                    )
            await self._batch_repo.update_song_status(song.id, SONG_STATUS_DRAFT_FAILED)
            song.status = SONG_STATUS_DRAFT_FAILED
            logger.warning(
                "Draft generation failed for song %s (batch %s, index %d): %s",
                song.id,
                batch_id,
                song.batch_index,
                str(exc),
            )
            draft_log.log_song_draft_failed(
                batch_id=str(batch_id),
                song_number=song.batch_index + 1,
                reason=str(exc),
                song_id=str(song.id),
            )
            raise

    async def _resolve_draft_routing(self) -> Any:
        if self._ai_routing_service is None:
            raise NoAvailableKeysError("deepseek", {})
        routing = await self._ai_routing_service.resolve("lyric")
        title_routing = await self._ai_routing_service.resolve("title")
        album_routing = await self._ai_routing_service.resolve("album")
        from platform_api.ai.purposes.draft_routing import build_draft_routing

        return build_draft_routing(routing, title_routing, album_routing)

    @staticmethod
    def _channel_album_label(batch: Batch, channel_role: ChannelRole) -> str:
        if channel_role == ChannelRole.ALT:
            return str(batch.alt_album or batch.ok_album or "").strip()
        return str(batch.ok_album or "").strip()

    async def _resolve_alt_channel_album(
        self,
        *,
        batch: Batch,
        user_id: str,
        ok_album: str,
        use_content_pools: bool,
        draft_request: DraftRequest,
        draft_routing: Any,
    ) -> str:
        existing = str(batch.alt_album or "").strip()
        if existing and existing.lower() != ok_album.strip().lower():
            return existing
        if not batch.alt_profile_id:
            return ok_album

        if use_content_pools:
            reservation_owner = f"{user_id}:{batch.id}:alt-album"
            alt_item = await claim_pool_item(
                kind="albums",
                reservation_owner=reservation_owner,
                avoid_texts=[ok_album],
            )
            await finalize_pool_item(item=alt_item)
            alt_album = str(alt_item.text or "").strip()
            if alt_album and alt_album.lower() != ok_album.strip().lower():
                return alt_album
            raise RuntimeError("No distinct secondary album is available in the content pool.")

        from platform_api.ai.parsing.response_parser import parse_string_field
        from platform_api.ai.purposes.metadata_text import sanitize_metadata_name
        from platform_api.services.generation_service import build_album_slot_prompts

        user_context = str(draft_request.description or "").strip() or "Instrumental electronic music."
        album_system, album_user = build_album_slot_prompts(
            user_context=user_context,
            avoid_albums=[ok_album, *(draft_request.avoid_albums or [])],
            language=draft_request.language,
            secondary_language=draft_request.secondary_language,
        )
        album_raw = await self._generation_service.generate_text(
            system_prompt=album_system,
            user_prompt=album_user,
            provider=draft_routing.album.provider,
            model=draft_routing.album.sub_model or "",
            temperature=0.8,
            max_tokens=256,
            prefer_json=True,
        )
        album = sanitize_metadata_name(parse_string_field(album_raw, "album"), field="album")
        if not album or album.strip().lower() == ok_album.strip().lower():
            raise RuntimeError("Failed to generate a distinct secondary album name.")
        return album.strip()

    async def _persist_batch_channel_albums(
        self,
        *,
        batch_id: UUID,
        user_id: str,
        successful_songs: list[Song],
        use_content_pools: bool,
        draft_requests: list[Any],
        draft_routing: Any,
        channel_profile_id: UUID | None,
    ) -> Batch | None:
        if not successful_songs:
            return None
        batch = await self._batch_repo.get_batch_by_id(batch_id)
        if batch is None:
            return None

        ok_album = str(getattr(batch, "ok_album", None) or successful_songs[0].album or "").strip()
        if not ok_album:
            return batch

        alt_album = str(getattr(batch, "alt_album", None) or "").strip()
        if getattr(batch, "alt_profile_id", None) and (not alt_album or alt_album.lower() == ok_album.lower()):
            draft_request = draft_requests[getattr(successful_songs[0], "batch_index", 0)]
            try:
                alt_album = await self._resolve_alt_channel_album(
                    batch=batch,
                    user_id=user_id,
                    ok_album=ok_album,
                    use_content_pools=use_content_pools,
                    draft_request=draft_request,
                    draft_routing=draft_routing,
                )
            except Exception as exc:
                logger.warning(
                    "Secondary album resolution failed for batch %s: %s",
                    batch_id,
                    exc,
                )
                alt_album = ""

        await self._batch_repo.update_batch_channel_albums(
            batch_id,
            ok_album=ok_album,
            alt_album=alt_album or None,
        )
        batch.ok_album = ok_album
        batch.alt_album = alt_album or None
        return batch

    async def orchestrate_drafts(
        self,
        batch_id: UUID,
        user_id: str,
        draft_requests: list[Any],
        *,
        channel_profile_id: UUID | None = None,
        use_content_pools: bool = False,
        unique_opening: bool = False,
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

        if self._ai_routing_service is None:
            raise NoAvailableKeysError("deepseek", {})

        draft_routing = await self._resolve_draft_routing()

        batch_album: str | None = None
        batch_titles: list[str] = []

        for song, draft_request in zip(songs, draft_requests):
            try:
                song, batch_album, batch_titles = await self._generate_song_draft(
                    batch_id=batch_id,
                    user_id=user_id,
                    song=song,
                    draft_request=draft_request,
                    draft_routing=draft_routing,
                    channel_profile_id=channel_profile_id,
                    use_content_pools=use_content_pools,
                    unique_opening=unique_opening,
                    batch_album=batch_album,
                    batch_titles=batch_titles,
                )
                successful_songs.append(song)
            except Exception:
                continue

        if successful_songs:
            await self._persist_batch_channel_albums(
                batch_id=batch_id,
                user_id=user_id,
                successful_songs=successful_songs,
                use_content_pools=use_content_pools,
                draft_requests=draft_requests,
                draft_routing=draft_routing,
                channel_profile_id=channel_profile_id,
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
        draft_log.log_batch_draft_summary(
            batch_id=str(batch_id),
            succeeded=len(successful_songs),
            total=len(songs),
        )
        return songs

    async def validate_song_draft_retry(
        self,
        *,
        batch_id: UUID,
        song_id: UUID,
        user_id: str,
    ) -> None:
        """Validate ownership/status and mark the song pending before a background retry."""
        batch = await self._batch_repo.get_batch_for_user(batch_id, UUID(user_id))
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": str(batch_id)},
            )

        songs = await self._batch_repo.get_songs_for_user_batch(batch_id, UUID(user_id))
        song = next((item for item in songs if item.id == song_id), None)
        if song is None:
            raise NotFoundError(
                f"Song '{song_id}' not found in batch '{batch_id}'.",
                details={"batch_id": str(batch_id), "song_id": str(song_id)},
            )
        if song.status not in {SONG_STATUS_DRAFT_FAILED, SONG_STATUS_PENDING}:
            raise ValidationError(
                "Only songs with pending or draft_failed status can retry draft generation.",
                details={"status": song.status},
            )
        if self._ai_routing_service is None:
            raise NoAvailableKeysError("deepseek", {})

        if song.status != SONG_STATUS_PENDING:
            await self._batch_repo.update_song_status(song_id, SONG_STATUS_PENDING)

    async def _assert_song_allows_suno_retry(self, song: Song) -> None:
        """Ensure a song may submit or resubmit Suno."""
        if song.status in {SONG_STATUS_SUNO_FAILED, SONG_STATUS_DRAFT_READY}:
            return
        if song.status == SONG_STATUS_SUNO_PENDING:
            latest = await self._batch_repo.get_latest_suno_task_for_song(song.id)
            if latest is not None and is_suno_failure_status(latest.status):
                return
            if latest is not None and is_suno_pending_status(latest.status):
                raise ValidationError(
                    "Suno is still in progress for this song. Wait for it to finish before retrying.",
                    details={
                        "status": song.status,
                        "suno_task_status": str(latest.status or ""),
                    },
                )
        raise ValidationError(
            "Only songs with draft_ready or suno_failed status can submit Suno.",
            details={"status": song.status},
        )

    async def validate_song_suno_retry(
        self,
        *,
        batch_id: UUID,
        song_id: UUID,
        user_id: str,
        lyrics_override: str | None = None,
        title_override: str | None = None,
    ) -> None:
        """Validate ownership/status before a background Suno retry."""
        batch = await self._batch_repo.get_batch_for_user(batch_id, UUID(user_id))
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": str(batch_id)},
            )

        songs = await self._batch_repo.get_songs_for_user_batch(batch_id, UUID(user_id))
        song = next((item for item in songs if item.id == song_id), None)
        if song is None:
            raise NotFoundError(
                f"Song '{song_id}' not found in batch '{batch_id}'.",
                details={"batch_id": str(batch_id), "song_id": str(song_id)},
            )
        await self._assert_song_allows_suno_retry(song)
        title = str(title_override if title_override is not None else song.title or "").strip()
        lyrics = str(lyrics_override if lyrics_override is not None else song.lyrics or "").strip()
        if not title or not lyrics:
            raise ValidationError(
                "Song draft is incomplete. Retry draft generation first.",
                details={"song_id": str(song_id)},
            )

    async def latest_suno_failure_hint(self, song_id: UUID) -> str | None:
        """Return the latest Suno rejection message for rewrite context."""
        from platform_api.services.suno_status_messages import is_suno_failure_status

        latest = await self._batch_repo.get_latest_suno_task_for_song(song_id)
        if latest is None or not is_suno_failure_status(latest.status):
            return None
        message = str(latest.error_message or "").strip()
        return message or None

    async def retry_song_draft(
        self,
        *,
        batch_id: UUID,
        song_id: UUID,
        user_id: str,
    ) -> Song:
        """Retry draft generation for a single failed song in a batch."""
        batch = await self._batch_repo.get_batch_for_user(batch_id, UUID(user_id))
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": str(batch_id)},
            )

        songs = await self._batch_repo.get_songs_for_user_batch(batch_id, UUID(user_id))
        song = next((item for item in songs if item.id == song_id), None)
        if song is None:
            raise NotFoundError(
                f"Song '{song_id}' not found in batch '{batch_id}'.",
                details={"batch_id": str(batch_id), "song_id": str(song_id)},
            )
        if song.status not in {SONG_STATUS_DRAFT_FAILED, SONG_STATUS_PENDING}:
            raise ValidationError(
                "Only songs with pending or draft_failed status can retry draft generation.",
                details={"status": song.status},
            )

        if self._ai_routing_service is None:
            raise NoAvailableKeysError("deepseek", {})

        draft_routing = await self._resolve_draft_routing()
        use_content_pools, unique_opening = await self._load_music_pool_settings(user_id)

        batch_album: str | None = None
        batch_titles: list[str] = []
        for sibling in songs:
            if sibling.id == song_id:
                continue
            if sibling.title:
                batch_titles.append(str(sibling.title))
            if sibling.album and batch_album is None:
                batch_album = str(sibling.album)

        draft_requests = self._build_draft_requests(batch)
        draft_request = draft_requests[song.batch_index]

        if song.status != SONG_STATUS_PENDING:
            await self._batch_repo.update_song_status(song_id, SONG_STATUS_PENDING)
            song.status = SONG_STATUS_PENDING

        song, batch_album, _batch_titles = await self._generate_song_draft(
            batch_id=batch_id,
            user_id=user_id,
            song=song,
            draft_request=draft_request,
            draft_routing=draft_routing,
            channel_profile_id=batch.ok_profile_id,
            use_content_pools=use_content_pools,
            unique_opening=unique_opening,
            batch_album=batch_album,
            batch_titles=batch_titles,
        )
        album = str(song.album or batch_album or "").strip()
        if album:
            batch = (
                await self._persist_batch_channel_albums(
                    batch_id=batch.id,
                    user_id=user_id,
                    successful_songs=[song],
                    use_content_pools=use_content_pools,
                    draft_requests=draft_requests,
                    draft_routing=draft_routing,
                    channel_profile_id=batch.ok_profile_id,
                )
                or batch
            )
            ok_album = str(batch.ok_album or album).strip()
            alt_album = str(batch.alt_album or "").strip() or None
            batch = await self._assign_batch_run_directories_if_needed(
                batch,
                ok_album=ok_album,
                alt_album=alt_album,
            )

        if batch.auto_gsuno:
            title = str(song.title or "").strip() or "Untitled"
            try:
                suno_model = await self._resolve_suno_model(batch.user_id)
                draft_log.log_suno_submit_started(
                    batch_id=str(batch.id),
                    song_number=song.batch_index + 1,
                    title=title,
                    model=suno_model,
                )
                task_id = await self._submit_song_to_suno(
                    song=song,
                    batch=batch,
                    user_id=user_id,
                    model=suno_model,
                )
                draft_log.log_suno_submitted(
                    batch_id=str(batch.id),
                    song_number=song.batch_index + 1,
                    title=title,
                    task_id=task_id,
                )
            except Exception as exc:
                await self.update_song_to_suno_failed(song.id)
                reason = str(exc) or exc.__class__.__name__
                draft_log.log_suno_submit_failed(
                    batch_id=str(batch.id),
                    song_number=song.batch_index + 1,
                    title=title,
                    reason=reason,
                    song_id=str(song.id),
                )
                self._log_suno_failure_metric(
                    batch_id=batch.id,
                    song_id=song.id,
                    error_message=reason,
                    is_retry=True,
                )
                logger.warning(
                    "Suno submission failed for retried song %s in batch %s: %s",
                    song.id,
                    batch.id,
                    reason,
                )

        await self.refresh_batch_status(batch_id)
        return song

    async def retry_song_suno(
        self,
        *,
        batch_id: UUID,
        song_id: UUID,
        user_id: str,
        title: str | None = None,
        album: str | None = None,
        lyrics: str | None = None,
    ) -> Song:
        """Retry Suno submission for a song that already has a draft."""
        batch = await self._batch_repo.get_batch_for_user(batch_id, UUID(user_id))
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": str(batch_id)},
            )

        songs = await self._batch_repo.get_songs_for_user_batch(batch_id, UUID(user_id))
        song = next((item for item in songs if item.id == song_id), None)
        if song is None:
            raise NotFoundError(
                f"Song '{song_id}' not found in batch '{batch_id}'.",
                details={"batch_id": str(batch_id), "song_id": str(song_id)},
            )
        await self._assert_song_allows_suno_retry(song)

        resolved_title = str(title if title is not None else song.title or "").strip()
        resolved_album = str(album if album is not None else song.album or "").strip()
        resolved_lyrics = str(lyrics if lyrics is not None else song.lyrics or "").strip()
        if title is not None or album is not None or lyrics is not None:
            await self._batch_repo.update_song_draft(
                song_id,
                resolved_title or "Untitled",
                resolved_album,
                resolved_lyrics,
            )
            song.title = resolved_title or "Untitled"
            song.album = resolved_album
            song.lyrics = resolved_lyrics

        if not resolved_title or not resolved_lyrics:
            raise ValidationError(
                "Song draft is incomplete. Retry draft generation first.",
                details={"song_id": str(song_id)},
            )

        suno_model = await self._resolve_suno_model(batch.user_id)
        title_for_log = resolved_title or "Untitled"
        try:
            draft_log.log_suno_submit_started(
                batch_id=str(batch.id),
                song_number=song.batch_index + 1,
                title=title_for_log,
                model=suno_model,
            )
            task_id = await self._submit_song_to_suno(
                song=song,
                batch=batch,
                user_id=user_id,
                model=suno_model,
                is_retry=True,
            )
            draft_log.log_suno_submitted(
                batch_id=str(batch.id),
                song_number=song.batch_index + 1,
                title=title_for_log,
                task_id=task_id,
            )
        except Exception as exc:
            await self.update_song_to_suno_failed(song.id)
            reason = str(exc) or exc.__class__.__name__
            draft_log.log_suno_submit_failed(
                batch_id=str(batch.id),
                song_number=song.batch_index + 1,
                title=title_for_log,
                reason=reason,
                song_id=str(song.id),
            )
            self._log_suno_failure_metric(
                batch_id=batch.id,
                song_id=song.id,
                error_message=reason,
                is_retry=True,
            )
            logger.warning(
                "Suno retry failed for song %s in batch %s: %s",
                song.id,
                batch.id,
                reason,
            )
            raise

        await self.refresh_batch_status(batch_id)
        return song

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

    @staticmethod
    def _album_image_job_key(
        profile_id: UUID | None,
        kind: ImageKind | str,
        channel_role: ChannelRole | str,
    ) -> tuple[UUID | None, str, str]:
        kind_value = kind.value if isinstance(kind, ImageKind) else str(kind)
        role_value = channel_role.value if isinstance(channel_role, ChannelRole) else str(channel_role)
        return (profile_id, kind_value, role_value)

    def _pick_prompt_song(self, songs: list[Song], preferred: Song | None = None) -> Song | None:
        if preferred is not None:
            return preferred
        titled = [song for song in songs if str(song.title or "").strip()]
        if titled:
            return min(titled, key=lambda item: int(item.batch_index or 0))
        if songs:
            return min(songs, key=lambda item: int(item.batch_index or 0))
        return None

    async def create_image_jobs_for_batch(
        self,
        batch: Batch,
        *,
        prompt_song: Song | None = None,
        songs: list[Song] | None = None,
    ) -> list[ImageJob]:
        """Create shared album/channel image jobs for a batch (not per song).

        One background and/or thumbnail job per Primary/Secondary channel based on
        each profile's image_config mode. ``prompt_song`` is only used as prompt
        context / history anchor.
        """
        batch_songs = songs
        if batch_songs is None and prompt_song is None:
            batch_songs = await self._batch_repo.get_songs_by_batch(batch.id)
        song = self._pick_prompt_song(batch_songs or [], preferred=prompt_song)
        if song is None:
            logger.info(
                "Skipping image job creation for batch %s because it has no songs.",
                batch.id,
            )
            return []

        jobs: list[ImageJob] = []
        settings: dict[str, Any] = {}
        if self._settings_service is not None:
            settings = await self._settings_service.get_merged_settings(
                user_id=batch.user_id,
                include_sensitive=False,
            )

        used_samples = await self._batch_used_sample_paths(batch.id)
        if batch.ok_profile_id:
            jobs.extend(
                await self._create_jobs_for_profile(
                    song=song,
                    batch=batch,
                    profile_id=batch.ok_profile_id,
                    channel_role=ChannelRole.OK,
                    settings=settings,
                    used_samples=used_samples,
                )
            )
        if batch.alt_profile_id:
            jobs.extend(
                await self._create_jobs_for_profile(
                    song=song,
                    batch=batch,
                    profile_id=batch.alt_profile_id,
                    channel_role=ChannelRole.ALT,
                    settings=settings,
                    used_samples=used_samples,
                )
            )

        if jobs:
            existing = await self._batch_repo.get_image_jobs_by_batch(batch.id)
            existing_keys = {
                self._album_image_job_key(item.profile_id, item.kind, item.channel_role)
                for item in existing
            }
            jobs = [
                job
                for job in jobs
                if self._album_image_job_key(job.profile_id, job.kind, job.channel_role)
                not in existing_keys
            ]

        await self._sync_batch_channel_asset_manifests(batch=batch, settings=settings)

        if jobs:
            await self._batch_repo.create_image_jobs(jobs)
            logger.info(
                "Created %d album image job(s) for batch %s (prompt song %s).",
                len(jobs),
                batch.id,
                song.id,
            )

        return jobs

    async def create_image_jobs_for_song(
        self,
        song: Song,
        batch: Batch,
    ) -> list[ImageJob]:
        """Compat wrapper: album/channel jobs anchored on the completing song."""
        return await self.create_image_jobs_for_batch(batch, prompt_song=song)

    async def _batch_used_sample_paths(self, batch_id: UUID) -> dict[ImageKind, list[str]]:
        jobs = await self._batch_repo.get_image_jobs_by_batch(batch_id)
        used: dict[ImageKind, list[str]] = {
            ImageKind.BACKGROUND: [],
            ImageKind.THUMBNAIL: [],
        }
        for job in jobs:
            input_path = str(job.input_image_path or "").strip()
            if input_path and input_path not in used[ImageKind.BACKGROUND]:
                used[ImageKind.BACKGROUND].append(input_path)
            style_path = str(job.style_reference_path or "").strip()
            if style_path and style_path not in used[ImageKind.THUMBNAIL]:
                used[ImageKind.THUMBNAIL].append(style_path)
        return used

    async def enqueue_image_jobs_for_batches(
        self,
        user_id: str,
        batch_ids: list[str],
    ) -> int:
        created = 0
        user_uuid = UUID(user_id)

        for raw_batch_id in batch_ids:
            batch_id = UUID(raw_batch_id)
            batch = await self._batch_repo.get_batch_for_user(batch_id, user_uuid)
            if batch is None:
                continue

            songs = await self._batch_repo.get_songs_by_batch(batch.id)
            jobs = await self.create_image_jobs_for_batch(batch, songs=songs)
            created += len(jobs)

        return created

    async def ensure_batch_image_jobs(
        self,
        *,
        user_id: str,
        batch_id: UUID,
    ) -> int:
        """Create missing album image jobs when Suno finished but enqueue never ran."""
        batch = await self._batch_repo.get_batch_for_user(batch_id, UUID(user_id))
        if batch is None or not batch.auto_gen_image:
            return 0

        existing = await self._batch_repo.get_image_jobs_by_batch(batch_id)
        if existing:
            return 0

        songs = await self._batch_repo.get_songs_by_batch(batch_id)
        if not any(song.status == SONG_STATUS_SUNO_SUCCESS for song in songs):
            return 0

        try:
            created = await self.create_image_jobs_for_batch(batch, songs=songs)
        except Exception:
            logger.exception(
                "Failed to backfill image jobs for batch %s",
                batch_id,
            )
            return 0

        if created:
            logger.info(
                "Backfilled %d image job(s) for batch %s after Suno completion.",
                len(created),
                batch_id,
            )
            self._schedule_image_jobs_run(user_id=user_id, batch_id=batch_id)
        return len(created)

    async def sync_manual_assets_for_batch(
        self,
        *,
        user_id: str,
        batch_id: str,
    ) -> int:
        batch = await self._batch_repo.get_batch_for_user(UUID(batch_id), UUID(user_id))
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": batch_id},
            )

        settings: dict[str, Any] = {}
        if self._settings_service is not None:
            settings = await self._settings_service.get_merged_settings(
                user_id=batch.user_id,
                include_sensitive=False,
            )

        if self._normalize_image_source_mode(settings) != "manual":
            raise ValidationError(
                "Manual asset sync is only available when Image Source Mode is set to Manual.",
                details={"setting": "imageSourceMode"},
            )

        songs = await self._batch_repo.get_songs_by_batch(batch.id)
        prompt_song = self._pick_prompt_song(songs)
        if prompt_song is None:
            return 0

        existing_jobs = await self._batch_repo.get_image_jobs_by_batch(batch.id)
        existing_by_key = {
            self._album_image_job_key(job.profile_id, job.kind, job.channel_role): job
            for job in existing_jobs
        }

        created_jobs: list[ImageJob] = []
        updated = 0

        for profile_id, channel_role in (
            (batch.ok_profile_id, ChannelRole.OK),
            (batch.alt_profile_id, ChannelRole.ALT),
        ):
            if profile_id is None:
                continue

            manual_jobs = await self._create_jobs_for_profile(
                song=prompt_song,
                batch=batch,
                profile_id=profile_id,
                channel_role=channel_role,
                settings=settings,
            )

            for job in manual_jobs:
                key = self._album_image_job_key(job.profile_id, job.kind, job.channel_role)
                existing = existing_by_key.get(key)
                if existing is None:
                    created_jobs.append(job)
                    existing_by_key[key] = job
                    continue

                if (
                    existing.status == TaskStatus.SUCCESS
                    and str(existing.output_image_path or "").strip()
                    == str(job.output_image_path or "").strip()
                ):
                    continue

                await self._batch_repo.update_image_job_status(
                    existing.id,
                    batch.user_id,
                    status=TaskStatus.SUCCESS,
                    output_image_path=job.output_image_path,
                    error=None,
                    provider=job.provider,
                    attempt_count=int(existing.attempt_count or 0),
                )
                updated += 1

        if created_jobs:
            await self._batch_repo.create_image_jobs(created_jobs)

        await self._sync_batch_channel_asset_manifests(batch=batch, settings=settings)
        await self.refresh_batch_status(batch.id)
        return len(created_jobs) + updated

    async def list_pending_suno_downloads(
        self,
        *,
        user_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        await self.reconcile_pending_suno_tasks(user_id=user_id, limit=max(limit, 10))
        rows = await self._batch_repo.list_pending_suno_downloads(
            user_id=UUID(user_id),
            limit=limit,
            max_age_days=30,
        )
        batch_ids = {
            UUID(str(row["batch_id"]))
            for row in rows
            if row.get("batch_id")
        }
        for batch_id in batch_ids:
            try:
                await self.ensure_batch_image_jobs(user_id=user_id, batch_id=batch_id)
            except Exception:
                logger.exception(
                    "Failed to ensure image jobs during pending download sync for batch %s",
                    batch_id,
                )
        items: list[dict[str, Any]] = []
        for row in rows:
            track_no_raw = row.get("batch_index")
            track_no = int(track_no_raw) + 1 if isinstance(track_no_raw, int) else None
            alt_output_dir = resolve_channel_run_dir(
                role="ALT",
                ok_run_dir=str(row.get("ok_run_dir") or row.get("output_dir_ok") or ""),
                alt_run_dir=str(row.get("output_dir_alt") or row.get("alt_run_dir") or ""),
                alt_profile_folder=str(row.get("alt_profile_folder") or ""),
                alt_profile_name=str(row.get("alt_profile_name") or ""),
            )
            ok_output_dir = str(row.get("output_dir_ok") or row.get("ok_run_dir") or "").strip() or None
            alt_output_dir = str(alt_output_dir or "").strip() or None
            title = str(row.get("title") or "").strip()
            items.append(
                {
                    "task_id": str(row["id"]),
                    "song_id": str(row["song_id"]) if row.get("song_id") else None,
                    "batch_id": str(row["batch_id"]) if row.get("batch_id") else None,
                    "title": title or None,
                    "track_number": track_no,
                    "primary": {
                        "download_url": str(row.get("audio_url_ok") or "").strip() or None,
                        "downloaded": bool(row.get("downloaded_ok")),
                        "output_dir": ok_output_dir,
                        "target_path": self._build_suno_download_target_path(
                            output_dir=ok_output_dir or "",
                            title=title,
                            track_no=track_no,
                            variant="primary",
                        ),
                    },
                    "secondary": {
                        "download_url": str(row.get("audio_url_alt") or "").strip() or None,
                        "downloaded": bool(row.get("downloaded_alt")),
                        "output_dir": alt_output_dir,
                        "target_path": self._build_suno_download_target_path(
                            output_dir=alt_output_dir or "",
                            title=title,
                            track_no=track_no,
                            variant="secondary",
                        ),
                    },
                }
            )
        return [item for item in items if self._pending_download_is_actionable(item)]

    @staticmethod
    def _pending_download_is_actionable(item: dict[str, Any]) -> bool:
        for channel in ("primary", "secondary"):
            target = item.get(channel) or {}
            if target.get("downloaded"):
                continue
            if str(target.get("download_url") or "").strip() and str(target.get("target_path") or "").strip():
                return True
        return False

    async def reconcile_pending_suno_tasks(
        self,
        *,
        user_id: str,
        limit: int = 10,
    ) -> int:
        """Poll Suno for in-flight tasks when callbacks are unavailable (local dev)."""
        reconciled = await self._reconcile_stuck_suno_pending_songs(
            user_id=user_id,
            limit=max(limit, 10),
        )

        rows = await self._batch_repo.list_reconcilable_suno_tasks(
            user_id=UUID(user_id),
            limit=limit,
        )
        if not rows:
            return reconciled

        reconciled = 0
        batches_to_run_images: set[UUID] = set()
        for row in rows:
            external_task_id = str(row.get("external_task_id") or "").strip()
            if not external_task_id:
                continue
            try:
                poll_result = await self._generation_service.poll_suno_generate_status(
                    external_task_id
                )
            except Exception as exc:
                logger.warning(
                    "Suno reconcile poll failed for task %s: %s",
                    row.get("id"),
                    str(exc)[:200],
                )
                continue

            from platform_api.models.enums import TaskStatus

            if poll_result.state == "pending":
                continue

            task_id = UUID(str(row["id"]))
            song_id = UUID(str(row["song_id"])) if row.get("song_id") else None
            batch_id = UUID(str(row["batch_id"])) if row.get("batch_id") else None
            if poll_result.state == "success":
                from platform_api.services.suno_audio_resolver import normalize_http_download_url

                url_ok = normalize_http_download_url(poll_result.audio_url_ok) or None
                url_alt = normalize_http_download_url(poll_result.audio_url_alt) or None
                if not url_ok and not url_alt:
                    logger.warning(
                        "Suno reconcile success without download URLs for task %s",
                        row.get("id"),
                    )
                    continue

                await self._batch_repo.update_status(
                    task_id,
                    status=TaskStatus.SUCCESS,
                    audio_url_ok=url_ok,
                    audio_url_alt=url_alt,
                )
                if song_id and batch_id:
                    await self.handle_suno_task_update(
                        song_id=song_id,
                        batch_id=batch_id,
                        status=TaskStatus.SUCCESS,
                    )
                    batch = await self._batch_repo.get_batch_by_id(batch_id)
                    if batch and batch.auto_gen_image:
                        batches_to_run_images.add(batch_id)
                    try:
                        from platform_api.dependencies import get_db_pool
                        from platform_api.services.streaming_upload_service import StreamingUploadService

                        if url_ok or url_alt:
                            StreamingUploadService(get_db_pool()).schedule_suno_streaming_upload(
                                suno_task_id=task_id
                            )
                    except Exception as exc:
                        logger.warning(
                            "Failed to schedule streaming upload during reconcile for task %s: %s",
                            task_id,
                            exc,
                        )
                reconciled += 1
                continue

            await self._batch_repo.update_status(
                task_id,
                status=TaskStatus.FAILED,
                error_message=str(poll_result.error or "").strip() or None,
            )
            if song_id and batch_id:
                await self.handle_suno_task_update(
                    song_id=song_id,
                    batch_id=batch_id,
                    status=TaskStatus.FAILED,
                    error_message=str(poll_result.error or "").strip() or None,
                )
            reconciled += 1
        for batch_id in batches_to_run_images:
            self._schedule_image_jobs_run(user_id=user_id, batch_id=batch_id)
        return reconciled

    async def _reconcile_stuck_suno_pending_songs(
        self,
        *,
        user_id: str,
        limit: int = 25,
    ) -> int:
        """Fix songs left at suno_pending after the latest Suno task already failed."""
        rows = await self._batch_repo.list_stuck_suno_pending_songs(
            user_id=UUID(user_id),
            limit=limit,
        )
        fixed = 0
        batch_ids: set[UUID] = set()
        for row in rows:
            song_id_raw = row.get("song_id")
            if not song_id_raw:
                continue
            song_id = UUID(str(song_id_raw))
            await self.update_song_to_suno_failed(song_id)
            batch_id_raw = row.get("batch_id")
            if batch_id_raw:
                batch_ids.add(UUID(str(batch_id_raw)))
            fixed += 1
        for batch_id in batch_ids:
            await self.refresh_batch_status(batch_id)
        return fixed

    def _schedule_image_jobs_run(self, *, user_id: str, batch_id: UUID) -> None:
        if self._image_job_service is None:
            return
        from platform_api.services.image_job_runner import run_image_jobs_until_empty

        asyncio.create_task(
            run_image_jobs_until_empty(
                self._image_job_service,
                user_id=user_id,
                batch_id=str(batch_id),
            )
        )

    async def refresh_image_job_prompts_for_retry(
        self,
        *,
        user_id: str,
        job_ids: list[str] | None = None,
        batch_id: str | None = None,
    ) -> int:
        """Re-compose prompts from current profile + Image page settings before retry."""
        user_uuid = UUID(user_id)
        parsed_job_ids = [UUID(value) for value in (job_ids or []) if str(value or "").strip()]
        parsed_batch_id = UUID(batch_id) if batch_id else None
        if not parsed_job_ids and parsed_batch_id is None:
            return 0

        settings = await self._settings_service.get_merged_settings(
            user_uuid,
            include_sensitive=False,
        )
        jobs = await self._batch_repo.get_image_jobs_for_user(
            user_uuid,
            batch_id=parsed_batch_id,
            limit=500,
        )
        if parsed_job_ids:
            requested = {str(job_id) for job_id in parsed_job_ids}
            jobs = [job for job in jobs if str(job.id) in requested]

        refreshed = 0
        batch_cache: dict[UUID, Batch | None] = {}
        for job in jobs:
            if job.song_id is None or job.profile_id is None or job.batch_id is None:
                continue
            if job.batch_id not in batch_cache:
                batch_cache[job.batch_id] = await self._batch_repo.get_batch_by_id(job.batch_id)
            batch = batch_cache[job.batch_id]
            if batch is None:
                continue
            song = await self._batch_repo.get_song_by_id(job.song_id)
            profile = await self._profile_repo.get_by_id(job.profile_id)
            if song is None or profile is None:
                continue
            image_config = getattr(profile, "image_config", None) or {}
            if job.kind == ImageKind.BACKGROUND:
                profile_prompt = image_config.get("background_prompt", "")
            else:
                profile_prompt = image_config.get("thumbnail_prompt", "")
            ui_prompt = self._get_user_image_prompt(settings, job.kind)
            prompt = self._compose_image_prompt(
                song=song,
                batch=batch,
                channel_role=job.channel_role,
                profile_prompt=profile_prompt,
                user_prompt=ui_prompt,
            )
            if job.kind == ImageKind.BACKGROUND:
                prompt = enrich_background_prompt(prompt)
            elif normalize_thumbnail_reference_mode(
                str(settings.get("thumbnailReferenceMode", "composite") or "composite")
            ) == "composite":
                prompt = enrich_thumbnail_prompt(prompt)
            if not prompt.strip():
                continue
            await self._batch_repo.update_image_job_prompt(
                job.id,
                user_uuid,
                prompt=prompt,
            )
            refreshed += 1
        return refreshed

    async def sync_suno_downloads(
        self,
        *,
        user_id: str,
        items: list[dict[str, Any]],
    ) -> int:
        updated = 0
        user_uuid = UUID(user_id)
        for item in items:
            task_id_raw = str(item.get("task_id") or "").strip()
            if not task_id_raw:
                continue
            changed = await self._batch_repo.update_suno_download_state(
                task_id=UUID(task_id_raw),
                user_id=user_uuid,
                downloaded_ok=bool(item.get("downloaded_primary")) if "downloaded_primary" in item else None,
                downloaded_alt=bool(item.get("downloaded_secondary")) if "downloaded_secondary" in item else None,
                output_dir_ok=str(item.get("output_dir_primary") or "").strip() or None,
                output_dir_alt=str(item.get("output_dir_secondary") or "").strip() or None,
            )
            if changed:
                updated += 1
        return updated

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

        draft_log.log_suno_callback_succeeded(
            batch_id=str(batch_id),
            song_number=song.batch_index + 1,
            title=str(song.title or "").strip() or "Untitled",
        )

        if not batch.auto_gen_image:
            logger.info(
                "Skipping image job creation for song %s because auto_gen_image is disabled on batch %s.",
                song_id,
                batch_id,
            )
            await self.refresh_batch_status(batch_id)
            return []

        jobs: list[ImageJob] = []
        try:
            jobs = await self.create_image_jobs_for_song(song, batch)
        except Exception:
            logger.exception(
                "Image job creation failed for song %s in batch %s",
                song_id,
                batch_id,
            )
        if not jobs:
            created_count = await self.ensure_batch_image_jobs(
                user_id=str(batch.user_id),
                batch_id=batch_id,
            )
            if created_count:
                jobs = await self._batch_repo.get_image_jobs_by_batch(batch_id)
        await self.refresh_batch_status(batch_id)
        return jobs

    async def handle_suno_task_update(
        self,
        song_id: UUID,
        batch_id: UUID,
        status: TaskStatus,
        *,
        error_message: str | None = None,
    ) -> list[ImageJob]:
        """Route Suno callback status changes back into the batch lifecycle."""
        if status == TaskStatus.SUCCESS:
            if self._enforcement_service is not None:
                pop = getattr(self._enforcement_service, "pop_operation_charge", None)
                if pop is not None:
                    await pop(f"suno:{song_id}")
            return await self.on_suno_task_completed(song_id=song_id, batch_id=batch_id)

        song = await self._batch_repo.get_song_by_id(song_id)
        if status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            # Never refund after a terminal SUCCESS — blocks SUCCESS→FAILED abuse.
            if song is not None and song.status == SONG_STATUS_SUNO_SUCCESS:
                logger.warning(
                    "Ignoring Suno FAILED/CANCELLED after SUCCESS for song %s "
                    "(batch %s); skipping refund.",
                    song_id,
                    batch_id,
                )
                return []

            already_failed = (
                song is not None and song.status == SONG_STATUS_SUNO_FAILED
            )
            if song is not None:
                draft_log.log_suno_callback_failed(
                    batch_id=str(batch_id),
                    song_number=song.batch_index + 1,
                    title=str(song.title or "").strip() or "Untitled",
                    status=status.value,
                    reason=str(error_message or "").strip(),
                )
            else:
                draft_log.log_suno_callback_failed(
                    batch_id=str(batch_id),
                    song_number=None,
                    title="Unknown",
                    status=status.value,
                    reason=str(error_message or "").strip() or f"song_id={str(song_id)[:8]}",
                )
            latest_task = await self._batch_repo.get_latest_suno_task_for_song(song_id)
            from platform_api.services.suno_lyrics_sanitize import extract_blocked_terms_from_suno_error

            blocked_terms = extract_blocked_terms_from_suno_error(error_message)
            failure_type = classify_suno_failure_type(
                status=status.value,
                error_message=error_message,
            )
            self._log_suno_failure_metric(
                batch_id=batch_id,
                song_id=song_id,
                status=status.value,
                error_message=error_message,
                is_retry=latest_task is not None,
                blocked_terms=blocked_terms,
            )

            if failure_type in {"SENSITIVE_WORD_ERROR", "producer_tag"} and blocked_terms:
                await self._promote_suno_blocked_terms(blocked_terms)

            if song is not None and failure_type in {"SENSITIVE_WORD_ERROR", "producer_tag"}:
                retried = await self._try_auto_retry_suno_after_failure(
                    song=song,
                    batch_id=batch_id,
                    user_id=str(song.user_id),
                )
                if retried:
                    await self.refresh_batch_status(batch_id)
                    return []

            await self.update_song_to_suno_failed(song_id)
            if not already_failed:
                batch = await self._batch_repo.get_batch_by_id(batch_id)
                refund_user_id = ""
                if batch is not None:
                    refund_user_id = str(batch.user_id)
                elif song is not None:
                    refund_user_id = str(song.user_id)
                if refund_user_id:
                    music_provider = "suno"
                    music_sub_model = None
                    if self._ai_routing_service is not None:
                        try:
                            routing_music = await self._ai_routing_service.resolve("music")
                            music_provider = str(
                                getattr(routing_music, "provider", "") or "suno"
                            ).strip() or "suno"
                        except Exception:
                            pass
                    await self._refund_suno_billing(
                        user_id=refund_user_id,
                        channel_profile_id=(
                            batch.ok_profile_id if batch is not None else None
                        ),
                        music_provider=music_provider,
                        music_sub_model=music_sub_model,
                        charged_credit_units=None,
                        song_id=song_id,
                        reason="suno_generation_failed",
                    )
            await self.refresh_batch_status(batch_id)
        else:
            await self.refresh_batch_status(batch_id)

        return []

    async def refresh_batch_status(self, batch_id: UUID) -> str:
        """Recompute the current batch status from song and Suno counters."""
        batch = await self._batch_repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError(
                f"Batch '{batch_id}' not found.",
                details={"batch_id": str(batch_id)},
            )

        counters = await self._batch_repo.get_batch_status_counters(batch_id)
        status = self._derive_batch_status(batch, counters)
        await self._batch_repo.update_batch_status(batch_id, status)
        return status

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    async def _calculate_batch_cost(
        self,
        *,
        user_id: UUID,
        song_count: int,
        ok_profile_id: UUID,
        alt_profile_id: UUID,
        auto_gen_image: bool,
        auto_gsuno: bool,
    ) -> int:
        """Calculate total batch cost for the configured automation path.

        Looks up the configured pricing for draft generation and, when the
        matching automation toggles are enabled, adds Suno and image credits
        based on the selected Primary/Secondary profile image modes.

        Args:
            song_count: Number of songs in the batch.
            ok_profile_id: Selected Primary channel profile for the batch.
            alt_profile_id: Selected Secondary channel profile for the batch.
            auto_gen_image: Whether this batch should auto-create image jobs.
            auto_gsuno: Whether this batch should include Suno generation.

        Returns:
            Total credit cost for the batch.

        Raises:
            ValidationError: If pricing is not configured for required operations.
        """
        if self._ai_routing_service is None:
            raise NoAvailableKeysError("deepseek", {})

        from platform_api.ai.purposes.draft_routing import build_draft_routing
        from platform_api.services.draft_billing import calculate_batch_draft_cost

        routing_lyric = await self._ai_routing_service.resolve("lyric")
        routing_title = await self._ai_routing_service.resolve("title")
        routing_album = await self._ai_routing_service.resolve("album")
        draft_routing = build_draft_routing(routing_lyric, routing_title, routing_album)

        try:
            total_cost = await calculate_batch_draft_cost(
                self._pricing_service, draft_routing, song_count
            )
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(
                "LLM draft generation pricing is not configured. Cannot estimate batch cost. "
                "Add approved pricing rows for title, album, and lyric in Admin → Credits → Pricing.",
                details={"error": str(exc)},
            ) from exc

        if auto_gsuno:
            routing_music = await self._ai_routing_service.resolve("music")
            music_provider = str(getattr(routing_music, "provider", "") or "").strip()
            suno_model = await self._resolve_suno_model(user_id)

            try:
                suno_price = await self._pricing_service.get_price(
                    music_provider,
                    "music",
                    self._normalize_suno_pricing_model(suno_model),
                )
            except Exception as exc:
                model_label = str(suno_model or "default")
                raise ValidationError(
                    "Music generation pricing is not configured. Cannot estimate batch cost. "
                    f"Add pricing for provider '{music_provider}', operation 'music', "
                    f"model '{model_label}'.",
                    details={
                        "provider": music_provider,
                        "operation": "music",
                        "sub_model": suno_model,
                        "error": str(exc),
                    },
                ) from exc

            total_cost += suno_price * song_count

        if auto_gen_image:
            routing_image = await self._ai_routing_service.resolve("background_image")
            image_provider = str(getattr(routing_image, "provider", "") or "").strip()
            image_sub_model = getattr(routing_image, "sub_model", None)

            try:
                image_price = await self._pricing_service.get_price(
                    image_provider,
                    "background_image",
                    image_sub_model,
                )
            except Exception as exc:
                model_label = str(image_sub_model or "default")
                raise ValidationError(
                    "Image generation pricing is not configured. Cannot estimate batch cost. "
                    f"Add pricing for provider '{image_provider}', operation 'background_image', "
                    f"model '{model_label}'.",
                    details={
                        "provider": image_provider,
                        "operation": "background_image",
                        "sub_model": image_sub_model,
                        "error": str(exc),
                    },
                ) from exc

            image_jobs_per_channel = 0
            image_jobs_per_channel += await self._estimate_profile_image_job_count(ok_profile_id)
            image_jobs_per_channel += await self._estimate_profile_image_job_count(alt_profile_id)
            total_cost += image_jobs_per_channel * image_price

        return total_cost

    async def _resolve_batch_languages(
        self,
        *,
        user_id: str,
        description_id: str | None,
        language: str,
        secondary_language: str | None,
    ) -> tuple[str, str | None]:
        from platform_api.ai.purposes.vocal_profile import resolve_workspace_batch_languages

        _ = (user_id, description_id)
        return resolve_workspace_batch_languages(
            language=language,
            secondary_language=secondary_language,
        )

    async def _resolve_song_structure_ids(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        song_count: int,
        structure_id: str | None,
        shuffle_structure: bool,
        structure_mode: str = "template",
    ) -> list[UUID | None]:
        """Assign per-song structure ids for a batch.

        When shuffle is off, every song uses the selected structure_id.
        When on, structures are shuffled from the workspace catalog so songs in
        the same batch vary (seeded by batch_id; full pool before repeats).
        """
        from platform_api.services.generation_service import STRUCTURE_MODE_AI_FREE

        if structure_mode == STRUCTURE_MODE_AI_FREE:
            return [None for _ in range(song_count)]
        fixed = UUID(structure_id) if structure_id else None
        if song_count < 1:
            return []
        if not shuffle_structure:
            return [fixed for _ in range(song_count)]
        if self._prompt_service is None:
            return [fixed for _ in range(song_count)]

        structures = await self._prompt_service.list_structures_workspace(user_id)
        pool = [item for item in structures if getattr(item, "id", None) is not None]
        if not pool:
            return [fixed for _ in range(song_count)]

        from platform_api.services.prompt_service import PromptService

        assigned = PromptService.assign_structures_shuffle(pool, song_count, batch_id)
        return [item.id for item in assigned]

    async def _resolve_song_prompt_content(self, song: Song, draft_request: Any) -> Any:
        """Hydrate hidden prompt content from stored song ids when possible.

        This keeps the client-facing selectors name-only while ensuring the
        batch orchestration path can still use the real admin-managed prompt
        content.
        """
        if self._prompt_service is None or not isinstance(draft_request, DraftRequest):
            return draft_request

        from platform_api.ai.purposes.vocal_profile import (
            lyric_vocal_profile_for_batch,
            parse_vocal_profile,
            sanitize_production_description,
            vocal_profile_to_dict,
        )
        from platform_api.services.generation_service import STRUCTURE_MODE_AI_FREE

        description_text = draft_request.description.strip()
        structure_text = draft_request.structure.strip()
        ai_free = draft_request.structure_mode == STRUCTURE_MODE_AI_FREE
        description_profile = parse_vocal_profile(draft_request.vocal_profile)

        if song.description_id is not None:
            description = await self._prompt_service.get_description_for_access(
                song.description_id, song.user_id
            )
            description_text = sanitize_production_description(
                str(getattr(description, "content", "") or "")
            )
            description_profile = parse_vocal_profile(
                getattr(description, "vocal_profile", None)
            )

        if song.structure_id is not None and not ai_free:
            structure = await self._prompt_service.get_structure_for_access(
                song.structure_id, song.user_id
            )
            structure_text = str(getattr(structure, "content", "") or "").strip()

        lyric_profile = lyric_vocal_profile_for_batch(
            description_profile=description_profile,
            primary=draft_request.language,
            secondary=draft_request.secondary_language,
        )

        return replace(
            draft_request,
            description=description_text or draft_request.description,
            structure="" if ai_free else (structure_text or draft_request.structure),
            vocal_profile=vocal_profile_to_dict(lyric_profile),
        )

    def _build_draft_requests(self, batch: Batch) -> list[DraftRequest]:
        """Create one draft request per song using persisted batch settings."""
        secondary_language = getattr(batch, "secondary_language", None)
        structure_mode = str(getattr(batch, "structure_mode", "template") or "template")
        return [
            DraftRequest(
                language=batch.language,
                secondary_language=secondary_language,
                creativity_level=batch.creativity_level,
                description="",
                structure="",
                structure_mode=structure_mode,
            )
            for _ in range(batch.song_count)
        ]

    async def _load_music_pool_settings(self, user_id: str) -> tuple[bool, bool]:
        if self._settings_service is None:
            return False, False
        settings = await self._settings_service.get_merged_settings(
            user_id=UUID(user_id),
            include_sensitive=False,
        )
        return (
            _read_bool_setting(settings, "useContentPools"),
            _read_bool_setting(settings, "uniqueOpening"),
        )

    async def _resolve_suno_model(self, user_id: UUID) -> str:
        """Resolve the current user's preferred Suno model."""
        if self._settings_service is None:
            return "V5_5"

        settings = await self._settings_service.get_merged_settings(
            user_id=user_id,
            include_sensitive=False,
        )
        configured = str(settings.get("sunoDefaultVersion", "v5.5") or "v5.5").strip().lower()
        return "V5" if configured == "v5" else "V5_5"

    @staticmethod
    def _normalize_suno_pricing_model(model: str | None) -> str | None:
        from platform_api.services.pricing_keys import normalize_suno_pricing_sub_model

        normalized = normalize_suno_pricing_sub_model(model)
        return normalized or None

    async def _deduct_split_draft_billing(
        self,
        *,
        user_id: str,
        channel_profile_id: UUID | None,
        draft_routing: Any,
        draft_request: DraftRequest,
    ) -> tuple[int, int]:
        """Apply subscription quota or wallet billing for each LLM draft slot.

        Returns:
            (charged_credit_units, list_credit_units) — charged is wallet spend
            (0 on plan allowance); list is sum of pricing list units for COGS.
        """
        if self._enforcement_service is None:
            return 0, 0

        from platform_api.services.draft_billing import deduct_split_draft_billing

        return await deduct_split_draft_billing(
            self._enforcement_service,
            user_id=UUID(user_id),
            channel_profile_id=channel_profile_id,
            draft_routing=draft_routing,
            include_title=not draft_request.forced_title,
            include_album=not draft_request.forced_album,
            pricing=self._pricing_service,
        )
    async def _sanitize_suno_payload(
        self,
        song: Song,
        batch: Batch,
        *,
        latest_task: SunoTask | None = None,
        is_retry: bool = False,
    ) -> SunoSanitizedPayload:
        """Sanitize lyrics/title/style using static blocklist and latest Suno failure hints."""
        from platform_api.dependencies import get_suno_blocklist_service
        from platform_api.services.suno_lyrics_sanitize import (
            SunoSanitizeReplacement,
            extract_blocked_terms_from_suno_error,
            sanitize_text_for_suno_with_changes,
        )

        if latest_task is None:
            latest_task = await self._batch_repo.get_latest_suno_task_for_song(song.id)

        runtime_config = await get_suno_blocklist_service().get_runtime_config(
            channel_profile_id=batch.ok_profile_id,
        )

        blocked_terms: list[str] = []
        if latest_task is not None and is_suno_failure_status(latest_task.status):
            blocked_terms = extract_blocked_terms_from_suno_error(latest_task.error_message)

        raw_lyrics = str(song.lyrics or "").strip()
        raw_title = str(song.title or "").strip()
        raw_style = await self._resolve_song_style(song, batch)

        lyrics, lyrics_changes = sanitize_text_for_suno_with_changes(
            raw_lyrics,
            field="lyrics",
            blocked_terms=blocked_terms,
            runtime_config=runtime_config,
        )
        title, title_changes = sanitize_text_for_suno_with_changes(
            raw_title,
            field="title",
            blocked_terms=blocked_terms,
            runtime_config=runtime_config,
        )
        style, style_changes = sanitize_text_for_suno_with_changes(
            raw_style,
            field="style",
            blocked_terms=blocked_terms,
            runtime_config=runtime_config,
        )

        replacements: list[SunoSanitizeReplacement] = [
            *lyrics_changes,
            *title_changes,
            *style_changes,
        ]
        resolved_title = title.strip() or "Untitled"
        if lyrics != raw_lyrics or resolved_title != raw_title:
            await self._batch_repo.update_song_draft(
                song.id,
                resolved_title,
                str(song.album or "").strip(),
                lyrics,
            )
            song.title = resolved_title
            song.lyrics = lyrics

        if replacements:
            await self._batch_repo.update_song_suno_sanitize_metadata(
                song.id,
                {
                    "replacements": [
                        {
                            "field": item.field,
                            "source": item.source,
                            "target": item.target,
                        }
                        for item in replacements
                    ],
                    "at": datetime.now(timezone.utc).isoformat(),
                    "blocked_terms": list(blocked_terms),
                },
            )

        return SunoSanitizedPayload(
            title=resolved_title,
            lyrics=lyrics,
            style=style,
            replacements=tuple(replacements),
            blocked_terms=tuple(blocked_terms),
            is_retry=is_retry or latest_task is not None,
        )

    def _log_suno_failure_metric(
        self,
        *,
        batch_id: UUID | None,
        song_id: UUID | None,
        status: object = "",
        error_message: object = "",
        is_retry: bool = False,
        blocked_terms: list[str] | None = None,
    ) -> None:
        draft_log.log_suno_failure_metric(
            batch_id=str(batch_id) if batch_id else None,
            song_id=str(song_id) if song_id else None,
            failure_type=classify_suno_failure_type(
                status=status,
                error_message=error_message,
            ),
            is_retry=is_retry,
            blocked_terms_extracted=blocked_terms,
        )

    async def _promote_suno_blocked_terms(self, blocked_terms: list[str]) -> None:
        """Promote parsed Suno block terms into the learned blocklist registry."""
        if not blocked_terms:
            return
        from platform_api.dependencies import get_suno_blocklist_service
        from platform_api.services.suno_lyrics_sanitize import DEFAULT_REPLACEMENTS

        service = get_suno_blocklist_service()
        for term in blocked_terms:
            normalized = str(term or "").strip().lower()
            if not normalized:
                continue
            replacement = DEFAULT_REPLACEMENTS.get(normalized)
            try:
                await service.promote_learned_term(
                    term=normalized,
                    replacement=replacement,
                    severity="block",
                    notes="Auto-promoted from Suno callback failure",
                )
            except Exception:
                logger.exception("Failed to promote learned Suno term %s", normalized)

    async def _try_auto_retry_suno_after_failure(
        self,
        *,
        song: Song,
        batch_id: UUID,
        user_id: str,
    ) -> bool:
        """Sanitize and resubmit once after a sensitive-word/producer-tag failure."""
        retry_count = await self._batch_repo.get_suno_auto_retry_count(song.id)
        if retry_count >= 1:
            return False

        batch = await self._batch_repo.get_batch_by_id(batch_id)
        if batch is None:
            return False

        await self._batch_repo.increment_suno_auto_retry_count(song.id)
        suno_model = await self._resolve_suno_model(batch.user_id)
        try:
            await self._submit_song_to_suno(
                song=song,
                batch=batch,
                user_id=user_id,
                model=suno_model,
                is_retry=True,
            )
            logger.info(
                "Auto-retried Suno for song %s in batch %s after sensitive-word failure",
                song.id,
                batch_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Auto-retry Suno failed for song %s in batch %s: %s",
                song.id,
                batch_id,
                str(exc)[:200],
            )
            return False

    async def _assert_suno_payload_has_no_block_terms(
        self,
        payload: SunoSanitizedPayload,
        *,
        batch: Batch,
    ) -> None:
        """Reject Suno submit when block-severity terms remain after sanitize."""
        from platform_api.dependencies import get_suno_blocklist_service
        from platform_api.services.suno_lyrics_sanitize import find_suno_risk_terms_in_text

        runtime_config = await get_suno_blocklist_service().get_runtime_config(
            channel_profile_id=batch.ok_profile_id,
        )
        for field_name, text in (
            ("title", payload.title),
            ("lyrics", payload.lyrics),
            ("style", payload.style),
        ):
            hits = find_suno_risk_terms_in_text(
                text,
                learned_terms=payload.blocked_terms,
                runtime_config=runtime_config,
            )
            block_hits = [hit for hit in hits if hit.severity == "block"]
            if block_hits:
                terms = ", ".join(hit.term for hit in block_hits[:5])
                raise ValidationError(
                    "Suno-safe lyrics still contain blocked terms after sanitize.",
                    details={"field": field_name, "terms": terms},
                )

    async def _submit_song_to_suno(
        self,
        song: Song,
        batch: Batch,
        user_id: str,
        model: str,
        *,
        is_retry: bool = False,
    ) -> str:
        """Submit one successful draft to Suno and link the created task back to the batch.

        One Suno API job produces Primary + Secondary channel audio; billing is per
        submission, not per downloaded track.

        Song quota / wallet is deducted before the Suno API call. On submit failure
        (or later callback failure via ``_refund_suno_billing``), the song unit and
        any wallet debit are refunded while the original plan_allowance debit remains
        for owner COGS visibility.
        """
        payload = await self._sanitize_suno_payload(
            song,
            batch,
            is_retry=is_retry,
        )
        await self._assert_suno_payload_has_no_block_terms(payload, batch=batch)

        charged = 0
        music_provider = "suno"
        music_sub_model = self._normalize_suno_pricing_model(model)
        billing_applied = False
        try:
            if self._enforcement_service is not None and self._ai_routing_service is not None:
                routing_music = await self._ai_routing_service.resolve("music")
                music_provider = str(
                    getattr(routing_music, "provider", "") or "suno"
                ).strip() or "suno"
                charged = await self._enforcement_service.deduct_for_operation(
                    UUID(user_id),
                    batch.ok_profile_id,
                    "music",
                    music_provider,
                    sub_model=music_sub_model,
                )
                billing_applied = True
            task_id = await self._generation_service.submit_suno(
                user_id,
                SunoRequest(
                    model=model,
                    title=payload.title,
                    lyrics=payload.lyrics,
                    style=payload.style,
                    instrumental=False,
                ),
                skip_pricing=self._enforcement_service is not None,
            )
            await self._batch_repo.link_suno_task(UUID(task_id), song.id, batch.id)
            ok_output_dir = self._resolve_batch_run_dir(batch, ChannelRole.OK)
            alt_output_dir = self._resolve_batch_run_dir(batch, ChannelRole.ALT)
            if ok_output_dir or alt_output_dir:
                await self._batch_repo.update_suno_download_state(
                    task_id=UUID(task_id),
                    user_id=UUID(user_id),
                    output_dir_ok=ok_output_dir or None,
                    output_dir_alt=alt_output_dir or None,
                )
            await self.update_song_to_suno_pending(song.id)
            if self._enforcement_service is not None:
                stash = getattr(self._enforcement_service, "stash_operation_charge", None)
                if stash is not None:
                    await stash(f"suno:{song.id}", int(charged or 0))
            return task_id
        except Exception as exc:
            self._log_suno_failure_metric(
                batch_id=batch.id,
                song_id=song.id,
                error_message=str(exc),
                is_retry=payload.is_retry,
                blocked_terms=list(payload.blocked_terms),
            )
            if billing_applied:
                await self._refund_suno_billing(
                    user_id=user_id,
                    channel_profile_id=batch.ok_profile_id,
                    music_provider=music_provider,
                    music_sub_model=music_sub_model,
                    charged_credit_units=int(charged or 0),
                    song_id=song.id,
                    reason="suno_generation_failed",
                )
            raise

    async def _refund_suno_billing(
        self,
        *,
        user_id: str,
        channel_profile_id: UUID | None,
        music_provider: str = "suno",
        music_sub_model: str | None = None,
        charged_credit_units: int | None = None,
        song_id: UUID,
        reason: str = "suno_generation_failed",
    ) -> None:
        """Release song quota and refund wallet after a Suno failure."""
        if self._enforcement_service is None:
            return
        charged = charged_credit_units
        if charged is None:
            pop = getattr(self._enforcement_service, "pop_operation_charge", None)
            if pop is not None:
                stored = await pop(f"suno:{song_id}")
                charged = int(stored or 0) if stored is not None else 0
            else:
                charged = 0
        try:
            await self._enforcement_service.refund_failed_operation(
                UUID(user_id),
                channel_profile_id,
                "music",
                music_provider,
                charged_credit_units=int(charged or 0),
                sub_model=music_sub_model,
                reason=reason,
                ref_id=str(song_id),
                prior_ledger_recorded=True,
            )
        except Exception:
            logger.exception(
                "Failed to refund Suno billing for song %s (reason=%s).",
                song_id,
                reason,
            )
    async def _resolve_song_style(self, song: Song, batch: Batch) -> str:
        """Resolve Suno style from the stored music description prompt."""
        from platform_api.ai.purposes.vocal_profile import resolve_suno_style_from_description

        _ = batch
        if self._prompt_service is not None and song.description_id is not None:
            description = await self._prompt_service.get_description_for_access(
                song.description_id, song.user_id
            )
            return resolve_suno_style_from_description(
                str(getattr(description, "content", "") or "")
            )
        return resolve_suno_style_from_description("")

    def _derive_batch_status(self, batch: Batch, counters: dict[str, int]) -> str:
        """Map current pipeline counters to a batch-level status."""
        total_songs = int(counters.get("total_songs", 0) or 0)
        drafts_completed = int(counters.get("drafts_completed", 0) or 0)
        drafts_failed = int(counters.get("drafts_failed", 0) or 0)
        suno_submitted = int(counters.get("suno_submitted", 0) or 0)
        suno_completed = int(counters.get("suno_completed", 0) or 0)
        suno_failed = int(counters.get("suno_failed", 0) or 0)

        if total_songs <= 0:
            return BATCH_STATUS_PENDING

        if drafts_completed == 0 and drafts_failed == 0:
            return BATCH_STATUS_PENDING

        if not batch.auto_gsuno:
            if drafts_completed == total_songs and drafts_failed == 0:
                return BATCH_STATUS_COMPLETED
            if drafts_completed == 0 and drafts_failed == total_songs:
                return BATCH_STATUS_FAILED
            if drafts_completed + drafts_failed >= total_songs:
                return BATCH_STATUS_PARTIAL
            return BATCH_STATUS_PROCESSING

        if suno_submitted == 0:
            if drafts_completed == 0 and drafts_failed == total_songs:
                return BATCH_STATUS_FAILED
            if drafts_completed + drafts_failed >= total_songs:
                if drafts_failed > 0:
                    return BATCH_STATUS_PARTIAL
                return BATCH_STATUS_PROCESSING
            return BATCH_STATUS_PROCESSING

        suno_terminal = suno_completed + suno_failed
        if suno_terminal < drafts_completed:
            return BATCH_STATUS_PROCESSING

        if drafts_failed == 0 and suno_failed == 0 and suno_completed == drafts_completed:
            return BATCH_STATUS_COMPLETED

        if suno_completed > 0 or drafts_failed > 0:
            return BATCH_STATUS_PARTIAL

        return BATCH_STATUS_FAILED

    async def _estimate_profile_image_job_count(self, profile_id: UUID | None) -> int:
        """Return how many image jobs one profile creates per album/channel."""
        if profile_id is None:
            return 0

        profile = await self._profile_repo.get_by_id(profile_id)
        if profile is None:
            return 0

        image_config = getattr(profile, "image_config", None) or {}
        mode = str(image_config.get("mode", "bg_thumb") or "bg_thumb").strip().lower()

        if mode in {"bg_only", "thumb_only"}:
            return 1
        return 2

    async def _create_jobs_for_profile(
        self,
        song: Song,
        batch: Batch,
        profile_id: UUID,
        channel_role: ChannelRole,
        settings: dict[str, Any],
        used_samples: dict[ImageKind, list[str]] | None = None,
    ) -> list[ImageJob]:
        """Create image jobs for a specific profile based on its image_config.

        Args:
            song: The song to generate images for.
            batch: The parent batch.
            profile_id: The UUID of the channel profile.
            channel_role: Primary (OK) or Secondary (ALT) role code.

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
        kinds = self._resolve_profile_image_kinds(image_config)

        if self._normalize_image_source_mode(settings) == "manual":
            return self._build_manual_jobs_for_profile(
                song=song,
                batch=batch,
                profile_id=profile_id,
                channel_role=channel_role,
                image_config=image_config,
                kinds=kinds,
                settings=settings,
            )

        sample_usage = used_samples or {
            ImageKind.BACKGROUND: [],
            ImageKind.THUMBNAIL: [],
        }
        jobs: list[ImageJob] = []
        background_job_id: UUID | None = None
        for kind in kinds:
            if kind == ImageKind.BACKGROUND:
                profile_prompt = image_config.get("background_prompt", "")
                ui_prompt = self._get_user_image_prompt(settings, kind)
                input_image_path = await self._resolve_sample_reference_path(
                    settings=settings,
                    kind=kind,
                    exclude=sample_usage.get(kind, []),
                )
                if input_image_path:
                    sample_usage.setdefault(kind, []).append(input_image_path)
                style_reference_path = None
                source_job_id = None
            else:
                profile_prompt = image_config.get("thumbnail_prompt", "")
                ui_prompt = self._get_user_image_prompt(settings, kind)
                input_image_path = None
                style_reference_path = await self._resolve_sample_reference_path(
                    settings=settings,
                    kind=kind,
                    exclude=sample_usage.get(kind, []),
                )
                if style_reference_path:
                    sample_usage.setdefault(kind, []).append(style_reference_path)
                source_job_id = background_job_id
                if source_job_id is None:
                    input_image_path = style_reference_path

            prompt = self._compose_image_prompt(
                song=song,
                batch=batch,
                channel_role=channel_role,
                profile_prompt=profile_prompt,
                user_prompt=ui_prompt,
            )
            if kind == ImageKind.BACKGROUND:
                prompt = enrich_background_prompt(prompt)
            elif normalize_thumbnail_reference_mode(
                str(settings.get("thumbnailReferenceMode", "composite") or "composite")
            ) == "composite":
                prompt = enrich_thumbnail_prompt(prompt)

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
                input_image_path=input_image_path,
                style_reference_path=style_reference_path,
                source_job_id=source_job_id,
                status=TaskStatus.PENDING,
                attempt_count=0,
            )
            jobs.append(job)
            if kind == ImageKind.BACKGROUND:
                background_job_id = job.id

        return jobs

    @staticmethod
    def _normalize_image_source_mode(settings: dict[str, Any]) -> str:
        return (
            "manual"
            if str(settings.get("imageSourceMode", "") or "").strip().lower() == "manual"
            else "ai"
        )

    @staticmethod
    def _sanitize_music_file_name(value: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            re.sub(r'[\\/:*?"<>|]', "_", str(value or "")),
        ).strip()[:120]

    @staticmethod
    def _build_suno_download_target_path(
        *,
        output_dir: str,
        title: str,
        track_no: int | None,
        variant: str,
    ) -> str | None:
        normalized_dir = str(output_dir or "").strip()
        if not normalized_dir:
            return None
        base = BatchService._sanitize_music_file_name(title) or "track"
        prefix = f"{max(1, int(track_no))}. " if isinstance(track_no, int) else ""
        suffix = "OK" if str(variant).lower() == "primary" else "Alt"
        return str(Path(normalized_dir) / f"{prefix}{base}_{suffix}.mp3")

    @staticmethod
    def _resolve_profile_image_kinds(image_config: dict[str, Any]) -> list[ImageKind]:
        mode = str(image_config.get("mode", "bg_thumb") or "bg_thumb").strip().lower()
        if mode == "thumb_only":
            return [ImageKind.THUMBNAIL]
        if mode == "bg_only":
            return [ImageKind.BACKGROUND]
        return [ImageKind.BACKGROUND, ImageKind.THUMBNAIL]

    async def _assign_batch_run_directories_if_needed(
        self,
        batch: Batch,
        *,
        ok_album: str,
        alt_album: str | None = None,
    ) -> Batch:
        if str(batch.ok_run_dir or "").strip():
            return batch
        ok_album_text = str(ok_album or batch.ok_album or "").strip()
        if not ok_album_text:
            return batch
        alt_album_text = str(alt_album or batch.alt_album or ok_album_text).strip() or ok_album_text
        if self._settings_service is None:
            return batch
        settings = await self._settings_service.get_merged_settings(
            user_id=batch.user_id,
            include_sensitive=False,
        )
        from_date = batch.planned_from_date
        if from_date is None:
            from_date = batch.created_at.date() if batch.created_at else date.today()
        ok_run_dir, alt_run_dir = await self._resolve_batch_run_directories(
            ok_profile_id=batch.ok_profile_id,
            alt_profile_id=batch.alt_profile_id,
            from_date=from_date,
            ok_run_dir=None,
            alt_run_dir=None,
            ok_album=ok_album_text,
            alt_album=alt_album_text,
            settings=settings,
        )
        if not ok_run_dir and not alt_run_dir:
            return batch
        await self._batch_repo.update_batch_run_directories(
            batch.id,
            ok_run_dir=ok_run_dir,
            alt_run_dir=alt_run_dir,
        )
        batch.ok_run_dir = ok_run_dir
        batch.alt_run_dir = alt_run_dir
        return batch

    async def _resolve_batch_run_directories(
        self,
        *,
        ok_profile_id: UUID,
        alt_profile_id: UUID,
        from_date: date,
        ok_run_dir: str | None,
        alt_run_dir: str | None,
        ok_album: str | None,
        alt_album: str | None = None,
        settings: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        resolved_ok = str(ok_run_dir or "").strip()
        resolved_alt = str(alt_run_dir or "").strip()
        if resolved_ok and resolved_alt and resolved_ok != resolved_alt:
            return resolved_ok, resolved_alt

        base_dir = str(settings.get("sunoOutputDir") or settings.get("downloadsDir") or "").strip()
        if not base_dir:
            return resolved_ok or None, resolved_alt or None

        ok_profile = await self._profile_repo.get_by_id(ok_profile_id)
        alt_profile = await self._profile_repo.get_by_id(alt_profile_id)
        if ok_profile is None or alt_profile is None:
            return resolved_ok or None, resolved_alt or None

        ok_folder = str(ok_profile.folder_name or ok_profile.name or "").strip()
        alt_folder = str(alt_profile.folder_name or alt_profile.name or "").strip()
        if not ok_folder or not alt_folder:
            return resolved_ok or None, resolved_alt or None

        planned = plan_run_directories(
            base_dir=base_dir,
            ok_profile_folder=ok_folder,
            alt_profile_folder=alt_folder,
            run_label=build_run_folder_label(run_date=from_date, album=ok_album),
            ok_run_label=build_run_folder_label(run_date=from_date, album=ok_album),
            alt_run_label=build_run_folder_label(
                run_date=from_date,
                album=alt_album or ok_album,
            ),
            existing_ok_entries=list_run_folder_entries(base_dir, ok_folder),
            existing_alt_entries=list_run_folder_entries(base_dir, alt_folder),
        )
        if not resolved_ok:
            resolved_ok = str(planned.ok_run_dir or "").strip()
        if not resolved_alt or resolved_alt == resolved_ok:
            resolved_alt = str(planned.alt_run_dir or "").strip()
        return resolved_ok or None, resolved_alt or None

    @staticmethod
    def _batch_roles_share_run_dir(batch: Batch) -> bool:
        ok_dir = str(batch.ok_run_dir or "").strip()
        alt_dir = str(batch.alt_run_dir or "").strip()
        return bool(ok_dir and alt_dir and ok_dir == alt_dir)

    @staticmethod
    def _resolve_batch_run_dir(batch: Batch, channel_role: ChannelRole) -> str:
        if channel_role == ChannelRole.OK:
            return str(batch.ok_run_dir or "").strip()
        return str(batch.alt_run_dir or "").strip()

    def _resolve_manual_asset_outputs(
        self,
        *,
        run_dir: str,
        kinds: list[ImageKind],
        channel_role: ChannelRole,
        role_disambiguate: bool,
    ) -> dict[ImageKind, str] | None:
        asset_paths = resolve_channel_asset_paths(
            run_dir,
            channel_role=channel_role,
            role_disambiguate=role_disambiguate,
        )
        outputs: dict[ImageKind, str] = {}
        if ImageKind.BACKGROUND in kinds:
            if not compute_long_ready(asset_paths) and not compute_reel_ready(asset_paths):
                return None
            outputs[ImageKind.BACKGROUND] = str(asset_paths.get("background_16x9_path") or "")
        if ImageKind.THUMBNAIL in kinds:
            if not compute_long_ready(asset_paths) and not compute_reel_ready(asset_paths):
                return None
            outputs[ImageKind.THUMBNAIL] = str(asset_paths.get("thumbnail_16x9_path") or "")
        if any(not value for value in outputs.values()):
            return None
        return outputs

    async def _sync_batch_channel_asset_manifests(
        self,
        *,
        batch: Batch,
        settings: dict[str, Any],
    ) -> None:
        source_mode = self._normalize_image_source_mode(settings)
        role_disambiguate = self._batch_roles_share_run_dir(batch)
        for profile_id, channel_role in (
            (batch.ok_profile_id, ChannelRole.OK),
            (batch.alt_profile_id, ChannelRole.ALT),
        ):
            if profile_id is None:
                continue
            run_dir = self._resolve_batch_run_dir(batch, channel_role)
            if not run_dir:
                continue
            asset = build_batch_channel_assets(
                batch_id=batch.id,
                user_id=batch.user_id,
                profile_id=profile_id,
                role=channel_role,
                run_dir=run_dir,
                source_mode=source_mode,
                role_disambiguate=role_disambiguate,
            )
            await self._batch_repo.upsert_batch_channel_assets(asset)

    def _build_manual_jobs_for_profile(
        self,
        *,
        song: Song,
        batch: Batch,
        profile_id: UUID,
        channel_role: ChannelRole,
        image_config: dict[str, Any],
        kinds: list[ImageKind],
        settings: dict[str, Any],
    ) -> list[ImageJob]:
        run_dir = self._resolve_batch_run_dir(batch, channel_role)
        outputs = self._resolve_manual_asset_outputs(
            run_dir=run_dir,
            kinds=kinds,
            channel_role=channel_role,
            role_disambiguate=self._batch_roles_share_run_dir(batch),
        )
        if not outputs:
            return []

        jobs: list[ImageJob] = []
        for kind in kinds:
            profile_prompt = image_config.get(
                "background_prompt" if kind == ImageKind.BACKGROUND else "thumbnail_prompt",
                "",
            )
            ui_prompt = self._get_user_image_prompt(settings, kind)
            prompt = self._compose_image_prompt(
                song=song,
                batch=batch,
                channel_role=channel_role,
                profile_prompt=profile_prompt,
                user_prompt=ui_prompt,
            )
            jobs.append(
                ImageJob(
                    id=uuid4(),
                    song_id=song.id,
                    user_id=batch.user_id,
                    batch_id=batch.id,
                    profile_id=profile_id,
                    kind=kind,
                    channel_role=channel_role,
                    prompt=prompt or None,
                    provider="manual",
                    resolution=image_config.get("resolution", "1920x1080"),
                    style_strength=float(image_config.get("style_strength", 0.6)),
                    status=TaskStatus.SUCCESS,
                    attempt_count=0,
                    output_image_path=outputs[kind],
                )
            )
        return jobs

    @staticmethod
    def _normalize_prompt_tokens(template: str, song: Song, *, album_label: str = "") -> str:
        value = str(template or "").strip()
        if not value:
            return ""
        album = str(album_label or song.album or "").strip()
        return value.replace("{title}", song.title or "").replace("{album}", album)

    def _compose_image_prompt(
        self,
        *,
        song: Song,
        batch: Batch | None = None,
        channel_role: ChannelRole | None = None,
        profile_prompt: Any,
        user_prompt: str,
    ) -> str:
        album_label = ""
        if batch is not None and channel_role is not None:
            album_label = self._channel_album_label(batch, channel_role)
        parts = [
            self._normalize_prompt_tokens(
                str(profile_prompt or ""),
                song,
                album_label=album_label,
            ),
            self._normalize_prompt_tokens(user_prompt, song, album_label=album_label),
        ]
        return "\n\n".join(part for part in parts if part).strip()

    @staticmethod
    def _get_user_image_prompt(settings: dict[str, Any], kind: ImageKind) -> str:
        if kind == ImageKind.BACKGROUND:
            prompt = settings.get("imageBackgroundPrompt", settings.get("imagePrompt", ""))
        else:
            prompt = settings.get("imageThumbnailPrompt", "")
        return str(prompt or "").strip()

    @staticmethod
    def _coerce_setting_paths(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item or "").strip() for item in value if str(item or "").strip()]

    @staticmethod
    def _list_directory_images(directory: str) -> list[str]:
        base = Path(str(directory or "").strip()).expanduser()
        if not base.exists() or not base.is_dir():
            return []
        supported = {".png", ".jpg", ".jpeg", ".webp"}
        return sorted(
            str(path)
            for path in base.iterdir()
            if path.is_file() and path.suffix.lower() in supported
        )

    async def _resolve_sample_reference_path(
        self,
        *,
        settings: dict[str, Any],
        kind: ImageKind,
        exclude: list[str] | None = None,
    ) -> str | None:
        if self._image_sample_rotation is not None:
            return await self._image_sample_rotation.pick_sample_path(
                settings=settings,
                kind=kind,
                exclude=exclude,
            )
        candidates = ImageSampleRotationService.build_candidates(settings, kind)
        excluded = {str(value).strip() for value in (exclude or []) if str(value).strip()}
        for candidate in candidates:
            if candidate not in excluded:
                return candidate
        return candidates[0] if candidates else None
