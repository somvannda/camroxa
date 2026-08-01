from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import InsufficientCreditsError, QuotaExceededError, ValidationError
from platform_api.models.domain import Batch, ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.ports.generation_port import ImageRequest
from platform_api.services.thumbnail_composite import (
    build_thumbnail_overlay_input_png,
    compose_thumbnail_onto_background,
    enrich_thumbnail_prompt,
    normalize_thumbnail_reference_mode,
    to_cover_png_bytes,
)
from platform_api.services.image_sample_rotation import ImageSampleRotationService
from platform_api.services import image_progress_log as image_log
from platform_api.services.slai_image_config_service import (
    get_cached_slai_image_provider_config,
    load_slai_image_provider_config,
)

logger = logging.getLogger(__name__)

_NON_RETRYABLE_ERROR_MARKERS = (
    "daily fail/retry budget exceeded",
    "fail_budget_exceeded",
    "insufficient credits",
    "generation quota exceeded",
    "quota exceeded",
)


def _image_job_max_attempts() -> int:
    try:
        from platform_api.config import get_settings

        return max(1, min(8, int(get_settings().image_job_max_attempts)))
    except Exception:
        return 3


def _is_non_retryable_image_error(exc: BaseException) -> bool:
    if isinstance(exc, (QuotaExceededError, InsufficientCreditsError, ValidationError)):
        return True
    details = getattr(exc, "details", None)
    if isinstance(details, dict) and str(details.get("error_code") or "").upper() == "FAIL_BUDGET_EXCEEDED":
        return True
    message = str(exc or "").strip().lower()
    return any(marker in message for marker in _NON_RETRYABLE_ERROR_MARKERS)


def _parse_optional_uuid(value: str | None, *, field: str) -> UUID | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return UUID(normalized)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid {field}.",
            details={"field": field, "value": value},
        ) from exc


def _parse_uuid_list(values: list[str] | None, *, field: str) -> list[UUID] | None:
    if not values:
        return None
    parsed: list[UUID] = []
    for index, raw in enumerate(values):
        normalized = str(raw or "").strip()
        if not normalized:
            raise ValidationError(
                f"Invalid {field}.",
                details={"field": field, "index": index, "value": raw},
            )
        try:
            parsed.append(UUID(normalized))
        except ValueError as exc:
            raise ValidationError(
                f"Invalid {field}.",
                details={"field": field, "index": index, "value": raw},
            ) from exc
    return parsed


class DependencyPendingError(Exception):
    """Raised when a chained image job is waiting on an upstream artifact."""


class ImageJobRepositoryProtocol(Protocol):
    async def get_batch_for_user(self, batch_id: UUID, user_id: UUID) -> Batch | None: ...
    async def claim_image_jobs_for_run(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None,
        statuses: list[str],
        limit: int,
    ) -> list[ImageJob]: ...
    async def get_image_jobs_for_user(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None = None,
        statuses: list[str] | None = None,
        limit: int = 200,
    ) -> list[ImageJob]: ...
    async def get_image_job_by_id(self, job_id: UUID, user_id: UUID) -> ImageJob | None: ...
    async def update_image_job_storage_key(self, job_id: UUID, user_id: UUID, *, storage_key: str) -> None: ...
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
    async def reset_image_jobs(
        self,
        user_id: UUID,
        *,
        job_ids: list[UUID] | None = None,
        batch_id: UUID | None = None,
    ) -> int: ...
    async def requeue_auto_retry_failed_jobs(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None = None,
        max_attempts: int = 3,
        limit: int = 200,
    ) -> int: ...
    async def clear_image_jobs(
        self,
        user_id: UUID,
        *,
        batch_id: UUID | None = None,
        statuses: list[str] | None = None,
    ) -> int: ...


class SettingsServiceProtocol(Protocol):
    async def get_merged_settings(
        self, user_id: UUID, *, include_sensitive: bool = False
    ) -> dict[str, Any]: ...


class AIRoutingServiceProtocol(Protocol):
    async def resolve(self, operation_type: str) -> Any: ...
    async def resolve_image_chain(self, operation_type: str) -> list[Any]: ...


class UsageEnforcementProtocol(Protocol):
    async def check_and_deduct(
        self,
        *,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
    ) -> None: ...
    async def resolve_max_credits(
        self, operation_type: str, provider_models: list[tuple[str, str | None]]
    ) -> int: ...
    async def preflight_quotas_and_balance(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        *,
        min_credits: int,
    ) -> None: ...
    async def deduct_for_operation(
        self,
        user_id: UUID,
        channel_profile_id: UUID | None,
        operation_type: str,
        ai_service: str,
        *,
        sub_model: str | None = None,
    ) -> int: ...


class GenerationServiceProtocol(Protocol):
    async def submit_image(
        self,
        user_id: str,
        request: ImageRequest,
        *,
        skip_pricing: bool = True,
    ) -> bytes: ...
    async def submit_image_outcome(
        self,
        user_id: str,
        request: ImageRequest,
        *,
        operation: str | None = None,
        skip_pricing: bool = True,
        job_id: str | None = None,
        slai_retry_attempts: int | None = None,
    ) -> Any: ...


class ImageSampleRotationProtocol(Protocol):
    async def pick_sample_path(
        self,
        *,
        settings: dict[str, Any],
        kind: ImageKind,
    ) -> str | None: ...


class SettingsRepoProtocol(Protocol):
    async def get_system_setting(self, key: str) -> Any | None: ...
    async def upsert_system_settings(self, settings: dict[str, Any]) -> None: ...


class ImageJobService:
    def __init__(
        self,
        repo: ImageJobRepositoryProtocol,
        settings_service: SettingsServiceProtocol,
        routing_service: AIRoutingServiceProtocol,
        enforcement_service: UsageEnforcementProtocol,
        generation_service: GenerationServiceProtocol,
        image_sample_rotation: ImageSampleRotationProtocol | None = None,
        settings_repo: SettingsRepoProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._settings_service = settings_service
        self._settings_repo = settings_repo
        self._routing_service = routing_service
        self._enforcement_service = enforcement_service
        self._generation_service = generation_service
        self._image_sample_rotation = image_sample_rotation

    async def list_jobs(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 200,
    ) -> list[ImageJob]:
        resolved_batch_id = UUID(batch_id) if batch_id else None
        return await self._repo.get_image_jobs_for_user(
            UUID(user_id),
            batch_id=resolved_batch_id,
            statuses=statuses,
            limit=limit,
        )

    async def retry_jobs(
        self,
        user_id: str,
        *,
        job_ids: list[str] | None = None,
        batch_id: str | None = None,
    ) -> int:
        parsed_job_ids = _parse_uuid_list(job_ids, field="job_ids")
        parsed_batch_id = _parse_optional_uuid(batch_id, field="batch_id")
        if not parsed_job_ids and parsed_batch_id is None:
            raise ValidationError(
                "Provide at least one image job id or a batch id to retry.",
                details={"fields": ["job_ids", "batch_id"]},
            )
        return await self._repo.reset_image_jobs(
            UUID(user_id),
            job_ids=parsed_job_ids,
            batch_id=parsed_batch_id,
        )

    async def clear_jobs(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        statuses: list[str] | None = None,
    ) -> int:
        parsed_batch_id = UUID(batch_id) if batch_id else None
        return await self._repo.clear_image_jobs(
            UUID(user_id),
            batch_id=parsed_batch_id,
            statuses=statuses,
        )

    async def run_pending_jobs(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        limit: int = 8,
    ) -> int:
        if limit <= 0:
            return 0

        user_uuid = UUID(user_id)
        resolved_batch_id = UUID(batch_id) if batch_id else None
        settings = await self._settings_service.get_merged_settings(
            user_id=user_uuid,
            include_sensitive=False,
        )

        if self._settings_repo is not None:
            await load_slai_image_provider_config(self._settings_repo)
        slai_config = get_cached_slai_image_provider_config()
        slai_retry_attempts = slai_config.provider_retries

        max_workers = int(settings.get("perfImageWorkers", 4) or 4)
        max_workers = max(1, min(8, max_workers))

        # Pick up failed jobs that still have auto-retry attempts (e.g. after API restart).
        requeue = getattr(self._repo, "requeue_auto_retry_failed_jobs", None)
        if requeue is not None:
            requeued = await requeue(
                user_uuid,
                batch_id=resolved_batch_id,
                max_attempts=_image_job_max_attempts(),
                limit=min(200, max(limit, 1)),
            )
            if requeued:
                image_log.log_retry_reset(batch_id=batch_id, updated=requeued)

        claimed_jobs = await self._repo.claim_image_jobs_for_run(
            user_uuid,
            batch_id=resolved_batch_id,
            statuses=[TaskStatus.PENDING.value],
            limit=min(200, max(limit, 1)),
        )
        if not claimed_jobs:
            return 0

        image_log.log_jobs_claimed(
            batch_id=batch_id,
            count=len(claimed_jobs),
            workers=max_workers,
        )

        semaphore = asyncio.Semaphore(max_workers)
        results = await asyncio.gather(
            *[
                self._run_one_job(
                    user_id=user_uuid,
                    job=job,
                    settings=settings,
                    semaphore=semaphore,
                    slai_retry_attempts=slai_retry_attempts,
                )
                for job in claimed_jobs
            ],
            return_exceptions=True,
        )
        return sum(1 for result in results if result is True)

    async def _run_one_job(
        self,
        *,
        user_id: UUID,
        job: ImageJob,
        settings: dict[str, Any],
        semaphore: asyncio.Semaphore,
        slai_retry_attempts: int = 5,
    ) -> bool:
        async with semaphore:
            attempt_count = max(0, int(job.attempt_count or 0))

            try:
                quota_reserved = False
                provider_invoked = False
                billing_finalized = False
                charged_credit_units = 0
                operation_hold = None
                resolved_provider = "fal"
                resolved_sub_model: str | None = None
                operation_type = "background_image"
                batch = await self._resolve_job_batch(job, user_id)
                operation_type = (
                    "thumbnail_image"
                    if getattr(job, "kind", None) == ImageKind.THUMBNAIL
                    else "background_image"
                )
                image_log.log_job_started(
                    job_id=job.id,
                    batch_id=job.batch_id,
                    kind=str(getattr(job.kind, "value", job.kind)),
                    channel_role=str(getattr(job.channel_role, "value", job.channel_role)),
                    attempt=max(1, attempt_count + 1),
                )
                routing_chain = await self._routing_service.resolve_image_chain(
                    operation_type
                )
                primary_routing = routing_chain[0]
                resolved_provider = str(
                    getattr(primary_routing, "provider", "") or ""
                ).strip() or "fal"
                model_id = str(getattr(primary_routing, "sub_model", "") or "").strip() or None

                if self._enforcement_service is not None:
                    # Always bill like credit ops / plan_allowance — never skip
                    # wallet or ledger because batch.auto_gen_image was set
                    # (C2 / H3: prepaid must not mean free soft overage).
                    # H1: hold wallet before provider on soft overage.
                    provider_models = [
                        (
                            str(getattr(item, "provider", "") or "").strip(),
                            getattr(item, "sub_model", None),
                        )
                        for item in routing_chain
                        if str(getattr(item, "provider", "") or "").strip()
                    ]
                    max_credits = await self._enforcement_service.resolve_max_credits(
                        operation_type, provider_models
                    )
                    await self._enforcement_service.preflight_quotas_and_balance(
                        user_id=user_id,
                        channel_profile_id=job.profile_id,
                        operation_type=operation_type,
                        min_credits=max_credits,
                    )
                    hold = await self._enforcement_service.reserve_and_hold_before_provider(
                        user_id=user_id,
                        channel_profile_id=job.profile_id,
                        operation_type=operation_type,
                        hold_credit_units=max_credits,
                        ai_service=resolved_provider,
                        sub_model=model_id,
                    )
                    operation_hold = hold
                    quota_reserved = True
                    charged_credit_units = int(hold.held_units or 0)
                    billing_finalized = bool(hold.held_units > 0)

                prompt = str(job.prompt or "").strip()
                if not prompt:
                    raise ValidationError(
                        "Image job prompt is missing.",
                        details={"job_id": str(job.id)},
                    )

                reference_mode = normalize_thumbnail_reference_mode(
                    str(settings.get("thumbnailReferenceMode", "composite") or "composite")
                )
                if (
                    getattr(job, "kind", None) == ImageKind.THUMBNAIL
                    and reference_mode == "dual_reference"
                ):
                    logger.warning(
                        "Thumbnail dual_reference mode is not enabled yet; using composite pipeline."
                    )
                    reference_mode = "composite"

                resolved_sub_model: str | None = model_id
                provider_invoked = True
                if (
                    getattr(job, "kind", None) == ImageKind.THUMBNAIL
                    and reference_mode == "composite"
                ):
                    image_bytes, resolved_provider, resolved_sub_model = (
                        await self._generate_thumbnail_composite(
                            user_id=user_id,
                            job=job,
                            settings=settings,
                            prompt=enrich_thumbnail_prompt(prompt),
                            resolved_provider=resolved_provider,
                            model_id=model_id,
                            operation_type=operation_type,
                            slai_retry_attempts=slai_retry_attempts,
                        )
                    )
                else:
                    base_image = await self._resolve_base_image_bytes(
                        user_id=user_id,
                        job=job,
                        settings=settings,
                    )
                    outcome = await self._generation_service.submit_image_outcome(
                        str(user_id),
                        ImageRequest(
                            prompt=prompt,
                            provider=resolved_provider,
                            model_id=model_id,
                            resolution=str(job.resolution or "1920x1080"),
                            style_strength=float(job.style_strength or 0.6),
                            base_image=base_image,
                        ),
                        operation=operation_type,
                        skip_pricing=True,
                        job_id=str(job.id),
                        slai_retry_attempts=slai_retry_attempts,
                    )
                    image_bytes = outcome.image_bytes
                    resolved_provider = outcome.provider
                    resolved_sub_model = outcome.sub_model
                    if getattr(job, "kind", None) == ImageKind.BACKGROUND:
                        image_bytes = to_cover_png_bytes(
                            image_bytes,
                            str(job.resolution or "1920x1080"),
                        )

                if self._enforcement_service is not None and operation_hold is not None:
                    charged_credit_units = int(
                        await self._enforcement_service.finalize_held_operation(
                            user_id=user_id,
                            operation_type=operation_type,
                            ai_service=resolved_provider,
                            sub_model=resolved_sub_model,
                            hold=operation_hold,
                        )
                        or 0
                    )
                    billing_finalized = True

                output_path = self._write_image_output(
                    image_bytes=image_bytes,
                    user_id=user_id,
                    job=job,
                    settings=settings,
                    batch=batch,
                )
                await self._repo.update_image_job_status(
                    job.id,
                    user_id,
                    status=TaskStatus.SUCCESS,
                    output_image_path=output_path,
                    error=None,
                    provider=resolved_provider,
                    attempt_count=attempt_count,
                )
                image_log.log_job_success(
                    job_id=job.id,
                    kind=str(getattr(job.kind, "value", job.kind)),
                    provider=resolved_provider,
                    output_path=output_path,
                )
                try:
                    from platform_api.dependencies import get_db_pool
                    from platform_api.services.streaming_upload_service import StreamingUploadService

                    upload_service = StreamingUploadService(get_db_pool())
                    asyncio.create_task(
                        upload_service.maybe_upload_cover_after_image_job(
                            user_id=user_id,
                            batch_id=job.batch_id,
                            channel_role=str(getattr(job.channel_role, "value", job.channel_role) or "ok"),
                            kind=getattr(job, "kind", ImageKind.BACKGROUND),
                            image_bytes=image_bytes,
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to schedule streaming cover upload for job %s: %s", job.id, exc)
                try:
                    asyncio.create_task(
                        self._archive_image_output_to_storage(
                            job=job,
                            user_id=user_id,
                            image_bytes=image_bytes,
                        )
                    )
                except Exception as exc:
                    logger.warning("Failed to schedule image archive upload for job %s: %s", job.id, exc)
                return True
            except DependencyPendingError as exc:
                if quota_reserved and self._enforcement_service is not None:
                    if operation_hold is not None and operation_hold.held_units > 0:
                        refund = getattr(
                            self._enforcement_service, "refund_failed_operation", None
                        )
                        if refund is not None:
                            await refund(
                                user_id,
                                job.profile_id,
                                operation_type,
                                resolved_provider,
                                charged_credit_units=int(operation_hold.held_units),
                                sub_model=resolved_sub_model,
                                reason="image_generation_deferred",
                                ref_id=str(job.id),
                                prior_ledger_recorded=True,
                            )
                        else:
                            await self._enforcement_service.release_operation_quota(
                                user_id=user_id,
                                channel_profile_id=job.profile_id,
                                operation_type=operation_type,
                            )
                    else:
                        await self._enforcement_service.release_operation_quota(
                            user_id=user_id,
                            channel_profile_id=job.profile_id,
                            operation_type=operation_type,
                        )
                await self._repo.update_image_job_status(
                    job.id,
                    user_id,
                    status=TaskStatus.PENDING,
                    error=str(exc)[:500],
                    attempt_count=attempt_count,
                )
                logger.info(
                    "Image job waiting on dependency: job_id=%s reason=%s",
                    job.id,
                    str(exc)[:200],
                )
                image_log.log_job_waiting(job_id=job.id, reason=str(exc))
                return False
            except Exception as exc:
                if quota_reserved and self._enforcement_service is not None:
                    # Release reserved image quota; refund wallet if charged;
                    # record platform-absorbed COGS when provider was invoked.
                    refund = getattr(
                        self._enforcement_service, "refund_failed_operation", None
                    )
                    if refund is not None and provider_invoked:
                        await refund(
                            user_id,
                            job.profile_id,
                            operation_type,
                            resolved_provider,
                            charged_credit_units=(
                                int(charged_credit_units or 0)
                                if billing_finalized
                                else 0
                            ),
                            sub_model=resolved_sub_model,
                            reason="image_generation_failed",
                            ref_id=str(job.id),
                            prior_ledger_recorded=billing_finalized,
                        )
                    else:
                        await self._enforcement_service.release_operation_quota(
                            user_id=user_id,
                            channel_profile_id=job.profile_id,
                            operation_type=operation_type,
                        )
                message = str(exc) or exc.__class__.__name__
                next_attempt = max(1, attempt_count + 1)
                max_attempts = _image_job_max_attempts()
                auto_retry = next_attempt < max_attempts and not _is_non_retryable_image_error(exc)
                next_status = TaskStatus.PENDING if auto_retry else TaskStatus.FAILED
                await self._repo.update_image_job_status(
                    job.id,
                    user_id,
                    status=next_status,
                    error=message[:500],
                    attempt_count=next_attempt,
                )
                if auto_retry:
                    logger.warning(
                        "Image job failed; auto-retry queued: job_id=%s attempt=%s/%s error=%s",
                        job.id,
                        next_attempt,
                        max_attempts,
                        message[:200],
                    )
                    image_log.log_job_auto_retry(
                        job_id=job.id,
                        kind=str(getattr(job.kind, "value", job.kind)),
                        attempt=next_attempt,
                        max_attempts=max_attempts,
                        error=message,
                    )
                else:
                    logger.warning(
                        "Image job failed: job_id=%s status=%s error=%s",
                        job.id,
                        next_status.value,
                        message[:200],
                    )
                    image_log.log_job_failed(
                        job_id=job.id,
                        kind=str(getattr(job.kind, "value", job.kind)),
                        error=message,
                    )
                return False

    async def _resolve_job_batch(self, job: ImageJob, user_id: UUID) -> Batch | None:
        if job.batch_id is None:
            return None
        return await self._repo.get_batch_for_user(job.batch_id, user_id)

    async def _resolve_base_image_bytes(
        self,
        *,
        user_id: UUID,
        job: ImageJob,
        settings: dict[str, Any],
    ) -> bytes | None:
        if job.source_job_id is not None:
            source_job = await self._wait_for_source_job_output(
                user_id=user_id,
                source_job_id=job.source_job_id,
            )
            try:
                return await self._read_source_job_image_bytes(user_id, source_job)
            except Exception:
                return None

        sample_path = await self._resolve_runtime_sample_path(
            job=job,
            settings=settings,
            user_id=user_id,
        )
        if sample_path:
            return self._read_image_file(sample_path)

        if job.input_image_path:
            return self._read_image_file(job.input_image_path)

        return None

    async def _resolve_runtime_sample_path(
        self,
        *,
        job: ImageJob,
        settings: dict[str, Any],
        user_id: UUID | None = None,
    ) -> str | None:
        stored_path = str(
            job.input_image_path if job.kind == ImageKind.BACKGROUND else job.style_reference_path
            or ""
        ).strip()
        if stored_path:
            return stored_path

        if self._image_sample_rotation is None:
            return str(job.input_image_path or job.style_reference_path or "").strip() or None
        kind = getattr(job, "kind", None)
        if kind not in {ImageKind.BACKGROUND, ImageKind.THUMBNAIL}:
            return None

        exclude: list[str] = []
        if user_id is not None and job.batch_id is not None:
            siblings = await self._repo.get_image_jobs_for_user(
                user_id,
                batch_id=job.batch_id,
                limit=500,
            )
            for sibling in siblings:
                if sibling.id == job.id or sibling.kind != job.kind:
                    continue
                sibling_path = str(
                    sibling.input_image_path
                    if sibling.kind == ImageKind.BACKGROUND
                    else sibling.style_reference_path
                    or ""
                ).strip()
                if sibling_path:
                    exclude.append(sibling_path)

        return await self._image_sample_rotation.pick_sample_path(
            settings=settings,
            kind=kind,
            exclude=exclude,
        )

    async def _generate_thumbnail_composite(
        self,
        *,
        user_id: UUID,
        job: ImageJob,
        settings: dict[str, Any],
        prompt: str,
        resolved_provider: str,
        model_id: str | None,
        operation_type: str,
        slai_retry_attempts: int = 5,
    ) -> tuple[bytes, str, str | None]:
        source_job = await self._wait_for_source_job_output(
            user_id=user_id,
            source_job_id=job.source_job_id,
        )
        background_path = await self._resolve_source_background_path(user_id, source_job)

        style_path = await self._resolve_runtime_sample_path(
            job=job,
            settings=settings,
            user_id=user_id,
        )
        if not style_path:
            style_path = str(job.style_reference_path or "").strip() or None
        if not style_path:
            raise ValidationError(
                "Thumbnail style sample is missing.",
                details={"job_id": str(job.id)},
            )

        resolution = str(job.resolution or "1920x1080")
        style_strength = float(job.style_strength or 0.6)
        overlay_input = build_thumbnail_overlay_input_png(
            style_path,
            resolution,
            style_strength,
        )
        outcome = await self._generation_service.submit_image_outcome(
            str(user_id),
            ImageRequest(
                prompt=prompt,
                provider=resolved_provider,
                model_id=model_id,
                resolution=resolution,
                style_strength=style_strength,
                base_image=overlay_input,
            ),
            operation=operation_type,
            skip_pricing=True,
            job_id=str(job.id),
            slai_retry_attempts=slai_retry_attempts,
        )
        final_bytes = compose_thumbnail_onto_background(
            background_path=background_path,
            overlay_png_bytes=outcome.image_bytes,
            resolution=resolution,
            style_strength=style_strength,
        )
        return final_bytes, outcome.provider, outcome.sub_model

    async def _read_source_job_image_bytes(self, user_id: UUID, source_job: ImageJob) -> bytes:
        cache_path = self._server_image_cache_path(source_job.id)
        if cache_path.is_file():
            return cache_path.read_bytes()

        output_path = str(source_job.output_image_path or "").strip()
        if output_path and not self._looks_like_foreign_client_path(output_path):
            return self._read_image_file(output_path)

        image_bytes, _ = await self.read_job_output_bytes(source_job.id, user_id)
        return image_bytes

    async def _resolve_source_background_path(self, user_id: UUID, source_job: ImageJob) -> str:
        cache_path = self._server_image_cache_path(source_job.id)
        if cache_path.is_file():
            return str(cache_path)

        output_path = str(source_job.output_image_path or "").strip()
        if output_path and not self._looks_like_foreign_client_path(output_path):
            candidate = Path(output_path).expanduser()
            if candidate.is_file():
                return str(candidate.resolve())

        image_bytes, _ = await self.read_job_output_bytes(source_job.id, user_id)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(image_bytes)
        return str(cache_path)

    async def _wait_for_source_job_output(
        self,
        *,
        user_id: UUID,
        source_job_id: UUID,
        max_attempts: int = 20,
        delay_seconds: float = 0.5,
    ) -> ImageJob:
        last_job: ImageJob | None = None
        for _ in range(max_attempts):
            source_job = await self._repo.get_image_job_by_id(source_job_id, user_id)
            if source_job is None:
                raise ValidationError(
                    "Thumbnail image job source background job was not found.",
                    details={"source_job_id": str(source_job_id)},
                )
            last_job = source_job
            if source_job.status == TaskStatus.SUCCESS and (
                source_job.output_image_path
                or self._server_image_cache_path(source_job.id).is_file()
            ):
                return source_job
            if source_job.status == TaskStatus.FAILED:
                raise ValidationError(
                    "Thumbnail image job source background job failed.",
                    details={"source_job_id": str(source_job_id)},
                )
            await asyncio.sleep(delay_seconds)

        raise DependencyPendingError(
            f"Waiting for background image output from job {source_job_id}."
        )

    @staticmethod
    def _read_image_file(path: str) -> bytes:
        file_path = Path(str(path or "").strip()).expanduser().resolve()
        if not file_path.exists() or not file_path.is_file():
            raise ValidationError(
                "Image reference file does not exist.",
                details={"path": str(file_path)},
            )
        return file_path.read_bytes()

    @staticmethod
    def _batch_roles_share_run_dir(batch: Batch | None) -> bool:
        if batch is None:
            return False
        ok_dir = str(batch.ok_run_dir or "").strip()
        alt_dir = str(batch.alt_run_dir or "").strip()
        return bool(ok_dir and alt_dir and ok_dir == alt_dir)

    @staticmethod
    def _canonical_asset_stem(
        kind: ImageKind,
        resolution: str,
        *,
        channel_role: ChannelRole | str | None = None,
        role_disambiguate: bool = False,
    ) -> str:
        normalized = str(resolution or "").strip().lower().replace(" ", "")
        is_portrait = normalized in {"1080x1920", "9x16", "720x1280"} or (
            "x" in normalized
            and normalized.split("x", 1)[0].isdigit()
            and normalized.split("x", 1)[1].isdigit()
            and int(normalized.split("x", 1)[0]) < int(normalized.split("x", 1)[1])
        )
        if kind == ImageKind.BACKGROUND:
            stem = "background-9x16" if is_portrait else "background-16x9"
        else:
            stem = "thumbnail-9x16" if is_portrait else "thumbnail-16x9"
        if role_disambiguate:
            role_key = (
                "ok"
                if str(getattr(channel_role, "value", channel_role) or "").strip().lower() == "ok"
                else "alt"
            )
            return f"{stem}-{role_key}"
        return stem

    @staticmethod
    def _resolve_run_dir_for_job(job: ImageJob, batch: Batch | None) -> str | None:
        if batch is None:
            return None
        role = str(getattr(job.channel_role, "value", job.channel_role) or "").strip().lower()
        if role == "ok":
            return str(batch.ok_run_dir or "").strip() or None
        return str(batch.alt_run_dir or batch.ok_run_dir or "").strip() or None

    @staticmethod
    def _looks_like_foreign_client_path(path: str) -> bool:
        from platform_api.services.client_path_utils import is_windows_absolute_path

        text = str(path or "").strip()
        if not text:
            return False
        if is_windows_absolute_path(text):
            import sys

            return sys.platform != "win32"
        return False

    def _server_image_cache_path(self, job_id: UUID) -> Path:
        from platform_api.config import get_settings

        base = Path(get_settings().image_output_cache_dir).expanduser().resolve()
        return base / f"{job_id}.png"

    def _build_client_output_path(
        self,
        *,
        job: ImageJob,
        settings: dict[str, Any],
        batch: Batch | None,
    ) -> str | None:
        run_dir = self._resolve_run_dir_for_job(job, batch)
        if run_dir:
            stem = self._canonical_asset_stem(
                job.kind,
                str(job.resolution or "1920x1080"),
                channel_role=job.channel_role,
                role_disambiguate=self._batch_roles_share_run_dir(batch),
            )
            from platform_api.services.client_path_utils import join_client_output_path

            return join_client_output_path(run_dir, f"{stem}.png")

        output_dir = str(settings.get("imageOutputDir", "") or "").strip()
        if not output_dir:
            return None
        base_path = Path(output_dir).expanduser().resolve()
        if job.batch_id is not None:
            base_path = base_path / str(job.batch_id)
        base_path = base_path / ("ok" if str(job.channel_role.value).lower() == "ok" else "alt")
        stem = f"{job.kind.value}-{job.song_id or job.id}"
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return str((base_path / f"{stem}-{ts}.png").resolve())

    async def read_job_output_bytes(self, job_id: UUID, user_id: UUID) -> tuple[bytes, str]:
        from platform_api.exceptions import NotFoundError
        from platform_api.models.enums import TaskStatus

        job = await self._repo.get_image_job_by_id(job_id, user_id)
        if job is None or job.status != TaskStatus.SUCCESS:
            raise NotFoundError("Image job output is not available.")

        cache_path = self._server_image_cache_path(job.id)
        if cache_path.is_file():
            return cache_path.read_bytes(), "image/png"

        output_path = str(job.output_image_path or "").strip()
        if output_path:
            candidate = Path(output_path).expanduser()
            if candidate.is_file():
                return candidate.read_bytes(), "image/png"

        # Local cache and any server-reachable client path are both gone (disk
        # wipe, VPS migration, redeploy to a fresh disk, etc.) — fall back to the
        # durable Backblaze archive rather than forcing an expensive AI regeneration.
        storage_key = str(job.storage_key or "").strip()
        if storage_key:
            image_bytes = await self._read_archived_image_bytes(storage_key)
            if image_bytes is not None:
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(image_bytes)
                except OSError as exc:
                    logger.warning("Could not repopulate image cache for job %s: %s", job.id, exc)
                return image_bytes, "image/png"

        raise NotFoundError("Image file was not found on the server.")

    async def _archive_image_output_to_storage(
        self,
        *,
        job: ImageJob,
        user_id: UUID,
        image_bytes: bytes,
    ) -> None:
        """Best-effort: archive a successful image job's output to Backblaze.

        Never raises — mirrors the MP3 streaming-archive pattern so a storage
        hiccup never affects the primary (local-cache) success path. Skips
        silently if streaming storage isn't configured for this environment.
        """
        try:
            from platform_api.services.storage_service import StorageService
            from platform_api.services.streaming_config_service import resolve_streaming_storage_config

            config = await resolve_streaming_storage_config(self._pool_for_storage())
            if not config.configured:
                return
            batch_segment = str(job.batch_id) if job.batch_id else "adhoc"
            role_segment = str(getattr(job.channel_role, "value", job.channel_role) or "ok").lower()
            kind_segment = str(getattr(job.kind, "value", job.kind) or "image").lower()
            storage_key = f"images/{user_id}/{batch_segment}/{kind_segment}-{role_segment}-{job.id}.png"
            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=image_bytes, content_type="image/png")
            await self._repo.update_image_job_storage_key(job.id, user_id, storage_key=storage_key)
        except Exception as exc:
            logger.warning("Failed to archive image output for job %s to Backblaze: %s", job.id, exc)

    async def _read_archived_image_bytes(self, storage_key: str) -> bytes | None:
        """Best-effort: fetch archived image bytes from Backblaze, or None on any failure."""
        try:
            from platform_api.services.storage_service import StorageService
            from platform_api.services.streaming_config_service import resolve_streaming_storage_config

            config = await resolve_streaming_storage_config(self._pool_for_storage())
            if not config.configured:
                return None
            storage = StorageService.from_config(config)
            return await storage.download_bytes(storage_key)
        except Exception as exc:
            logger.warning("Failed to read archived image bytes for key %s: %s", storage_key, exc)
            return None

    @staticmethod
    def _pool_for_storage() -> Any:
        from platform_api.dependencies import get_db_pool

        return get_db_pool()

    def _write_image_output(
        self,
        *,
        image_bytes: bytes,
        user_id: UUID,
        job: ImageJob,
        settings: dict[str, Any],
        batch: Batch | None = None,
    ) -> str:
        client_path = self._build_client_output_path(job=job, settings=settings, batch=batch)
        cache_path = self._server_image_cache_path(job.id)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(image_bytes)

        if client_path and not self._looks_like_foreign_client_path(client_path):
            try:
                local_path = Path(client_path).expanduser().resolve()
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(image_bytes)
            except OSError as exc:
                logger.warning("Could not write image output to local path %s: %s", client_path, exc)

        if client_path:
            from platform_api.services.channel_asset_service import normalize_client_path

            return normalize_client_path(client_path)

        output_dir = str(settings.get("imageOutputDir", "") or "").strip()
        if not output_dir:
            raise ValidationError(
                "Image output directory is not configured. Set it in Settings → Preferences → Image output.",
                details={"setting": "imageOutputDir"},
            )

        base_path = Path(output_dir).expanduser().resolve()
        if job.batch_id is not None:
            base_path = base_path / str(job.batch_id)
        base_path = base_path / ("ok" if str(job.channel_role.value).lower() == "ok" else "alt")
        base_path.mkdir(parents=True, exist_ok=True)

        stem = f"{job.kind.value}-{job.song_id or job.id}"
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_path = base_path / f"{stem}-{ts}.png"
        file_path.write_bytes(image_bytes)

        return str(file_path)

    @staticmethod
    def encode_preview_base64(path: str) -> str | None:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        raw = p.read_bytes()
        return base64.b64encode(raw).decode("ascii")
