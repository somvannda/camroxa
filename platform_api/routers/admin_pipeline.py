"""Admin Pipeline Ops API — multi-user live board + owner-charged retries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.models.schemas import SongRetryResponse
from platform_api.repositories.job_queue_repo import JobQueueRepository
from platform_api.services.admin_pipeline_retry_costs import build_admin_retry_cost_estimates
from platform_api.services.admin_pipeline_service import (
    get_admin_pipeline_batch_detail,
    list_admin_pipeline_board,
)
from platform_api.services.audit_service import AuditService
from platform_api.services.batch_service import BatchService
from platform_api.services.image_job_service import ImageJobService
from platform_api.services.job_types import (
    JOB_RETRY_SONG_DRAFT,
    JOB_RETRY_SONG_SUNO,
    JOB_RUN_IMAGE_JOBS,
    JOB_RUN_YOUTUBE_UPLOADS,
    PRI_RETRY,
    PRI_RUN_IMAGE_JOBS,
    PRI_YOUTUBE_UPLOADS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pipeline", tags=["admin-pipeline"])

AdminDep = Annotated[AuthContext, Depends(require_admin)]


async def _get_batch_service() -> BatchService:
    raise NotImplementedError(
        "BatchService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_image_job_service() -> ImageJobService:
    raise NotImplementedError(
        "ImageJobService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_audit_service() -> AuditService:
    raise NotImplementedError(
        "AuditService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_job_queue_repo() -> JobQueueRepository:
    raise NotImplementedError(
        "JobQueueRepository dependency not configured. Wire via app.dependency_overrides."
    )


BatchServiceDep = Annotated[BatchService, Depends(_get_batch_service)]
ImageJobServiceDep = Annotated[ImageJobService, Depends(_get_image_job_service)]
AuditServiceDep = Annotated[AuditService, Depends(_get_audit_service)]
JobQueueRepoDep = Annotated[JobQueueRepository, Depends(_get_job_queue_repo)]


class AdminPipelineCounts(BaseModel):
    active: int = 0
    failed: int = 0
    stuck: int = 0
    total: int = 0


class AdminPipelineBoardRow(BaseModel):
    user_id: str
    user_email: str
    user_display_name: str = ""
    batch_id: str
    role: str
    profile_id: str
    profile_name: str
    album: str | None = None
    run_date: str
    stage: str
    status: str
    music: str
    image: str
    converter: str
    merge: str
    youtube: str
    streaming: str = "—"
    notes: str
    error_snippet: str | None = None
    updated: str
    updated_at: datetime | None = None
    age_seconds: int | None = None
    draft_failed_count: int = 0
    suno_failed_count: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)


class AdminPipelineBoardResponse(BaseModel):
    rows: list[AdminPipelineBoardRow] = Field(default_factory=list)
    summary: str = "Ready"
    updated_at: datetime
    counts: AdminPipelineCounts = Field(default_factory=AdminPipelineCounts)


class AdminPipelineSong(BaseModel):
    id: str
    batch_index: int
    title: str | None = None
    album: str | None = None
    status: str
    updated_at: datetime | None = None
    suno_status: str | None = None
    suno_error: str | None = None
    suno_updated_at: datetime | None = None


class AdminPipelineImageJob(BaseModel):
    id: str
    profile_id: str | None = None
    channel_role: str | None = None
    kind: str
    status: str
    provider: str | None = None
    prompt_length: int | None = None
    attempt_count: int = 0
    error: str | None = None
    updated_at: datetime | None = None


class AdminPipelineYoutubeJob(BaseModel):
    id: str
    profile_id: str | None = None
    role: str | None = None
    status: str
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    error_message: str | None = None
    updated_at: datetime | None = None


class AdminPipelineStreamingJob(BaseModel):
    id: str
    song_id: str | None = None
    batch_id: str | None = None
    album_id: str | None = None
    kind: str
    status: str
    attempt_count: int = 0
    error: str | None = None
    source_url: str | None = None
    storage_key: str | None = None
    song_title: str | None = None
    song_album: str | None = None
    song_batch_index: int | None = None
    stream_album_name: str | None = None
    stream_channel_role: str | None = None
    stream_album_publish_status: str | None = None
    stream_track_publish_status: str | None = None
    stream_track_variant: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminPipelineBatchDetailResponse(BaseModel):
    batch_id: str
    user_id: str
    user_email: str
    user_display_name: str = ""
    status: str
    song_count: int = 0
    ok_profile_id: str | None = None
    alt_profile_id: str | None = None
    ok_album: str | None = None
    alt_album: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    songs: list[AdminPipelineSong] = Field(default_factory=list)
    image_jobs: list[AdminPipelineImageJob] = Field(default_factory=list)
    youtube_jobs: list[AdminPipelineYoutubeJob] = Field(default_factory=list)
    streaming_jobs: list[AdminPipelineStreamingJob] = Field(default_factory=list)


class AdminPipelineRetryCostsResponse(BaseModel):
    updated_at: str | None = None
    draft_credits_min: float | None = None
    draft_credits_max: float | None = None
    suno_credits: float | None = None
    background_image_credits: float | None = None
    thumbnail_image_credits: float | None = None
    operations: dict[str, float | None] = Field(default_factory=dict)
    disclaimer: str = ""


@router.get(
    "/retry-costs",
    response_model=AdminPipelineRetryCostsResponse,
    summary="Estimated credit costs for owner-charged pipeline retries",
)
async def get_pipeline_retry_costs(ctx: AdminDep) -> AdminPipelineRetryCostsResponse:
    """Return current list prices for draft / Suno / image retry confirms (P4.3)."""
    del ctx
    from platform_api.dependencies import get_ai_routing_service, get_credit_pricing_service

    payload = await build_admin_retry_cost_estimates(
        routing_service=get_ai_routing_service(),
        pricing_service=get_credit_pricing_service(),
    )
    return AdminPipelineRetryCostsResponse.model_validate(payload)


@router.get(
    "/board",
    response_model=AdminPipelineBoardResponse,
    summary="Multi-user pipeline board for admin ops",
)
async def get_pipeline_board(
    ctx: AdminDep,
    limit: int = Query(default=50, ge=1, le=100),
    active_only: bool = Query(default=True),
    stage: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> AdminPipelineBoardResponse:
    del ctx
    parsed_user_id: UUID | None = None
    if user_id:
        try:
            parsed_user_id = UUID(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid user_id.") from exc

    payload = await list_admin_pipeline_board(
        limit=limit,
        active_only=active_only,
        stage=stage,
        user_id=parsed_user_id,
        q=q,
    )
    return AdminPipelineBoardResponse.model_validate(payload)


@router.get(
    "/batches/{batch_id}",
    response_model=AdminPipelineBatchDetailResponse,
    summary="Pipeline drawer detail for one batch",
)
async def get_pipeline_batch_detail(
    batch_id: str,
    ctx: AdminDep,
) -> AdminPipelineBatchDetailResponse:
    del ctx
    try:
        parsed = UUID(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid batch ID.") from exc

    payload = await get_admin_pipeline_batch_detail(parsed)
    if payload is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return AdminPipelineBatchDetailResponse.model_validate(payload)


class AdminRetryBillingBody(BaseModel):
    waive_billing: bool = False
    reason: str | None = Field(default=None, max_length=500)


class AdminRetryImageRequest(AdminRetryBillingBody):
    job_ids: list[str] | None = None
    channel_role: str | None = Field(
        default=None,
        description="When set without job_ids, retry failed jobs for this OK/ALT role.",
    )


class AdminRetryImageResponse(BaseModel):
    batch_id: str
    owner_user_id: str
    updated: int
    status: str = "retrying"
    charge_path: str = "owner_quota_or_wallet"
    requires_approval: bool = False
    pending_id: str | None = None
    message: str | None = None


class AdminSongRetryResponse(SongRetryResponse):
    owner_user_id: str
    charge_path: str = "owner_quota_or_wallet"
    requires_approval: bool = False
    pending_id: str | None = None
    message: str | None = None


def _resolve_charge_path(waive_billing: bool) -> str:
    return "platform_paid" if waive_billing else "owner_quota_or_wallet"


def _require_waive_reason(waive_billing: bool, reason: str | None) -> str | None:
    if not waive_billing:
        return None
    text = str(reason or "").strip()
    if len(text) < 8:
        raise HTTPException(
            status_code=422,
            detail="waive_billing requires a reason (at least 8 characters).",
        )
    return text


async def _estimate_waive_credits(
    *,
    retry_kind: str,
    job_kinds: list[str] | None = None,
) -> float:
    from platform_api.dependencies import get_ai_routing_service, get_credit_pricing_service

    costs = await build_admin_retry_cost_estimates(
        routing_service=get_ai_routing_service(),
        pricing_service=get_credit_pricing_service(),
    )
    if retry_kind == "draft":
        value = costs.get("draft_credits_max")
        if value is None:
            value = costs.get("draft_credits_min")
        return float(value or 0)
    if retry_kind == "suno":
        return float(costs.get("suno_credits") or 0)
    total = 0.0
    for kind in job_kinds or ["background"]:
        key = "thumbnail_image_credits" if "thumb" in kind.lower() else "background_image_credits"
        rate = costs.get(key)
        if rate is not None:
            total += float(rate)
    return total


async def _maybe_queue_waive_retry(
    *,
    admin_id: str,
    owner_user_id: str,
    waive_reason: str,
    estimated_credits: float,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Return pending dual-control result when queued; None if may proceed immediately.

    Platform-paid dual-control for pipeline retries is not wired in the current
    DualControlService. Reject waive requests until that lands again.
    """
    _ = (admin_id, owner_user_id, waive_reason, estimated_credits, payload)
    raise HTTPException(
        status_code=501,
        detail=(
            "Platform-paid (waive_billing) pipeline retries are temporarily unavailable. "
            "Retry without waive to charge the batch owner, or re-enable dual-control waive."
        ),
    )


async def _require_batch_owner(batch_id: UUID) -> dict[str, Any]:
    payload = await get_admin_pipeline_batch_detail(batch_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Batch not found.")
    return payload


async def _log_admin_retry(
    *,
    audit: AuditService,
    http_request: Request,
    admin_id: str,
    action_type: str,
    target_resource: str,
    owner_user_id: str,
    batch_id: str,
    metadata: dict[str, Any],
    charge_path: str = "owner_quota_or_wallet",
) -> None:
    try:
        await audit.log_event(
            actor_id=admin_id,
            action_type=action_type,
            target_resource=target_resource,
            outcome="success",
            source_ip=http_request.client.host if http_request.client else None,
            endpoint_path=http_request.url.path,
            metadata={
                "owner_user_id": owner_user_id,
                "batch_id": batch_id,
                "charge_path": charge_path,
                **metadata,
            },
        )
    except Exception:
        logger.exception("Failed to write admin pipeline retry audit (%s)", action_type)


@router.post(
    "/batches/{batch_id}/songs/{song_id}/retry-draft",
    response_model=AdminSongRetryResponse,
    status_code=202,
    summary="Admin retry draft (charges owner unless waive_billing)",
)
async def admin_retry_song_draft(
    batch_id: str,
    song_id: str,
    http_request: Request,
    ctx: AdminDep,
    batch_service: BatchServiceDep,
    audit: AuditServiceDep,
    job_queue: JobQueueRepoDep,
    request: AdminRetryBillingBody | None = None,
) -> AdminSongRetryResponse:
    """Queue draft retry using the batch owner's quota/wallet (same as user retry)."""
    try:
        parsed_batch = UUID(batch_id)
        parsed_song = UUID(song_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid batch or song ID.") from exc

    body = request or AdminRetryBillingBody()
    waive_reason = _require_waive_reason(body.waive_billing, body.reason)
    charge_path = _resolve_charge_path(body.waive_billing)

    detail = await _require_batch_owner(parsed_batch)
    owner_user_id = str(detail["user_id"])

    await batch_service.validate_song_draft_retry(
        batch_id=parsed_batch,
        song_id=parsed_song,
        user_id=owner_user_id,
    )
    if body.waive_billing and waive_reason:
        estimate = await _estimate_waive_credits(retry_kind="draft")
        queued = await _maybe_queue_waive_retry(
            admin_id=ctx.user_id,
            owner_user_id=owner_user_id,
            waive_reason=waive_reason,
            estimated_credits=estimate,
            payload={
                "retry_kind": "draft",
                "batch_id": batch_id,
                "song_id": song_id,
            },
        )
        if queued is not None:
            await _log_admin_retry(
                audit=audit,
                http_request=http_request,
                admin_id=ctx.user_id,
                action_type="admin.retry.draft",
                target_resource=f"song:{song_id}",
                owner_user_id=owner_user_id,
                batch_id=batch_id,
                charge_path=charge_path,
                metadata={
                    "song_id": song_id,
                    "waive_billing": True,
                    "reason": waive_reason,
                    "requires_approval": True,
                    "pending_id": queued.get("pending_id"),
                    "estimated_credits": estimate,
                },
            )
            return AdminSongRetryResponse(
                batch_id=batch_id,
                song_id=song_id,
                status="pending",
                owner_user_id=owner_user_id,
                charge_path=charge_path,
                requires_approval=True,
                pending_id=queued.get("pending_id"),
                message=queued.get("message"),
            )

    await job_queue.enqueue(
        user_id=UUID(owner_user_id),
        batch_id=parsed_batch,
        song_id=parsed_song,
        job_type=JOB_RETRY_SONG_DRAFT,
        payload={
            "batch_id": batch_id,
            "song_id": song_id,
            "user_id": owner_user_id,
        },
        priority=PRI_RETRY,
    )
    await _log_admin_retry(
        audit=audit,
        http_request=http_request,
        admin_id=ctx.user_id,
        action_type="admin.retry.draft",
        target_resource=f"song:{song_id}",
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        charge_path=charge_path,
        metadata={
            "song_id": song_id,
            "waive_billing": body.waive_billing,
            "reason": waive_reason,
        },
    )
    return AdminSongRetryResponse(
        batch_id=batch_id,
        song_id=song_id,
        status="retrying",
        owner_user_id=owner_user_id,
        charge_path=charge_path,
    )


@router.post(
    "/batches/{batch_id}/songs/{song_id}/retry-suno",
    response_model=AdminSongRetryResponse,
    status_code=202,
    summary="Admin retry Suno (charges owner unless waive_billing)",
)
async def admin_retry_song_suno(
    batch_id: str,
    song_id: str,
    http_request: Request,
    ctx: AdminDep,
    batch_service: BatchServiceDep,
    audit: AuditServiceDep,
    job_queue: JobQueueRepoDep,
    request: AdminRetryBillingBody | None = None,
) -> AdminSongRetryResponse:
    """Queue Suno retry using the batch owner's music quota/wallet."""
    try:
        parsed_batch = UUID(batch_id)
        parsed_song = UUID(song_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid batch or song ID.") from exc

    body = request or AdminRetryBillingBody()
    waive_reason = _require_waive_reason(body.waive_billing, body.reason)
    charge_path = _resolve_charge_path(body.waive_billing)

    detail = await _require_batch_owner(parsed_batch)
    owner_user_id = str(detail["user_id"])

    await batch_service.validate_song_suno_retry(
        batch_id=parsed_batch,
        song_id=parsed_song,
        user_id=owner_user_id,
    )
    if body.waive_billing and waive_reason:
        estimate = await _estimate_waive_credits(retry_kind="suno")
        queued = await _maybe_queue_waive_retry(
            admin_id=ctx.user_id,
            owner_user_id=owner_user_id,
            waive_reason=waive_reason,
            estimated_credits=estimate,
            payload={
                "retry_kind": "suno",
                "batch_id": batch_id,
                "song_id": song_id,
            },
        )
        if queued is not None:
            await _log_admin_retry(
                audit=audit,
                http_request=http_request,
                admin_id=ctx.user_id,
                action_type="admin.retry.suno",
                target_resource=f"song:{song_id}",
                owner_user_id=owner_user_id,
                batch_id=batch_id,
                charge_path=charge_path,
                metadata={
                    "song_id": song_id,
                    "waive_billing": True,
                    "reason": waive_reason,
                    "requires_approval": True,
                    "pending_id": queued.get("pending_id"),
                    "estimated_credits": estimate,
                },
            )
            return AdminSongRetryResponse(
                batch_id=batch_id,
                song_id=song_id,
                status="pending",
                owner_user_id=owner_user_id,
                charge_path=charge_path,
                requires_approval=True,
                pending_id=queued.get("pending_id"),
                message=queued.get("message"),
            )

    await job_queue.enqueue(
        user_id=UUID(owner_user_id),
        batch_id=parsed_batch,
        song_id=parsed_song,
        job_type=JOB_RETRY_SONG_SUNO,
        payload={
            "batch_id": batch_id,
            "song_id": song_id,
            "user_id": owner_user_id,
        },
        priority=PRI_RETRY,
    )
    await _log_admin_retry(
        audit=audit,
        http_request=http_request,
        admin_id=ctx.user_id,
        action_type="admin.retry.suno",
        target_resource=f"song:{song_id}",
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        charge_path=charge_path,
        metadata={
            "song_id": song_id,
            "waive_billing": body.waive_billing,
            "reason": waive_reason,
        },
    )
    return AdminSongRetryResponse(
        batch_id=batch_id,
        song_id=song_id,
        status="retrying",
        owner_user_id=owner_user_id,
        charge_path=charge_path,
    )


@router.post(
    "/batches/{batch_id}/retry-images",
    response_model=AdminRetryImageResponse,
    status_code=200,
    summary="Admin retry image jobs (charges owner unless waive_billing)",
)
async def admin_retry_image_jobs(
    batch_id: str,
    http_request: Request,
    ctx: AdminDep,
    batch_service: BatchServiceDep,
    image_service: ImageJobServiceDep,
    audit: AuditServiceDep,
    job_queue: JobQueueRepoDep,
    request: AdminRetryImageRequest | None = None,
) -> AdminRetryImageResponse:
    """Reset failed image jobs and re-run them under the owner's billing path."""
    try:
        parsed_batch = UUID(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid batch ID.") from exc

    detail = await _require_batch_owner(parsed_batch)
    owner_user_id = str(detail["user_id"])
    payload = request or AdminRetryImageRequest()
    waive_reason = _require_waive_reason(payload.waive_billing, payload.reason)
    charge_path = _resolve_charge_path(payload.waive_billing)

    job_ids = [jid.strip() for jid in (payload.job_ids or []) if str(jid).strip()]
    role = (payload.channel_role or "").strip().upper() or None

    if not job_ids and role:
        job_ids = [
            str(job["id"])
            for job in detail.get("image_jobs", [])
            if str(job.get("status") or "").lower() == "failed"
            and str(job.get("channel_role") or "").upper() == role
        ]
    elif not job_ids:
        job_ids = [
            str(job["id"])
            for job in detail.get("image_jobs", [])
            if str(job.get("status") or "").lower() == "failed"
        ]

    if not job_ids:
        raise HTTPException(status_code=400, detail="No failed image jobs to retry.")

    if payload.waive_billing and waive_reason:
        job_kinds = [
            str(job.get("kind") or "background")
            for job in detail.get("image_jobs", [])
            if str(job.get("id")) in set(job_ids)
        ] or ["background"]
        estimate = await _estimate_waive_credits(retry_kind="images", job_kinds=job_kinds)
        queued = await _maybe_queue_waive_retry(
            admin_id=ctx.user_id,
            owner_user_id=owner_user_id,
            waive_reason=waive_reason,
            estimated_credits=estimate,
            payload={
                "retry_kind": "images",
                "batch_id": batch_id,
                "job_ids": job_ids,
                "channel_role": role,
            },
        )
        if queued is not None:
            await _log_admin_retry(
                audit=audit,
                http_request=http_request,
                admin_id=ctx.user_id,
                action_type="admin.retry.image",
                target_resource=f"batch:{batch_id}",
                owner_user_id=owner_user_id,
                batch_id=batch_id,
                charge_path=charge_path,
                metadata={
                    "job_ids": job_ids,
                    "updated": 0,
                    "channel_role": role,
                    "reason": waive_reason,
                    "waive_billing": True,
                    "requires_approval": True,
                    "pending_id": queued.get("pending_id"),
                    "estimated_credits": estimate,
                },
            )
            return AdminRetryImageResponse(
                batch_id=batch_id,
                owner_user_id=owner_user_id,
                updated=0,
                status="pending",
                charge_path=charge_path,
                requires_approval=True,
                pending_id=queued.get("pending_id"),
                message=queued.get("message"),
            )

    await batch_service.refresh_image_job_prompts_for_retry(
        user_id=owner_user_id,
        job_ids=job_ids,
        batch_id=batch_id,
    )
    updated = await image_service.retry_jobs(
        owner_user_id,
        job_ids=job_ids,
        batch_id=batch_id,
    )
    if updated > 0:
        await job_queue.enqueue_if_absent(
            user_id=UUID(owner_user_id),
            batch_id=parsed_batch,
            job_type=JOB_RUN_IMAGE_JOBS,
            payload={
                "user_id": owner_user_id,
                "batch_id": batch_id,
                "limit": 50,
            },
            priority=PRI_RUN_IMAGE_JOBS,
        )

    await _log_admin_retry(
        audit=audit,
        http_request=http_request,
        admin_id=ctx.user_id,
        action_type="admin.retry.image",
        target_resource=f"batch:{batch_id}",
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        charge_path=charge_path,
        metadata={
            "job_ids": job_ids,
            "updated": updated,
            "channel_role": role,
            "reason": waive_reason or payload.reason,
            "waive_billing": payload.waive_billing,
        },
    )
    return AdminRetryImageResponse(
        batch_id=batch_id,
        owner_user_id=owner_user_id,
        updated=updated,
        status="retrying" if updated > 0 else "noop",
        charge_path=charge_path,
    )


class AdminRetryYoutubeResponse(BaseModel):
    batch_id: str
    job_id: str
    owner_user_id: str
    status: str = "requeued"


async def _run_youtube_retry_with_logging(
    owner_user_id: str,
    batch_id: str,
) -> None:
    """Legacy helper retained for scripts; prefer job_queue enqueue."""
    try:
        from platform_api.dependencies import get_youtube_connection_service

        service = get_youtube_connection_service()
        await service.run_pending_upload_jobs(
            user_id=owner_user_id,
            batch_id=batch_id,
            limit=4,
        )
    except Exception:
        logger.exception(
            "Admin YouTube retry runner crashed for user %s batch=%s",
            owner_user_id,
            batch_id,
        )


@router.post(
    "/batches/{batch_id}/youtube-jobs/{job_id}/retry",
    response_model=AdminRetryYoutubeResponse,
    status_code=202,
    summary="Admin requeue YouTube upload job",
)
async def admin_retry_youtube_job(
    batch_id: str,
    job_id: str,
    http_request: Request,
    ctx: AdminDep,
    audit: AuditServiceDep,
    job_queue: JobQueueRepoDep,
) -> AdminRetryYoutubeResponse:
    """Requeue a failed/blocked YouTube job for the batch owner.

    Does not charge credits. Upload still needs the merged MP4 reachable by the
    upload worker (usually via the owner's desktop run).
    """
    try:
        parsed_batch = UUID(batch_id)
        parsed_job = UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid batch or job ID.") from exc

    detail = await _require_batch_owner(parsed_batch)
    owner_user_id = str(detail["user_id"])

    from platform_api.dependencies import get_db_pool

    pool = get_db_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, batch_id, status, role
        FROM youtube_upload_jobs
        WHERE id = $1
          AND batch_id = $2
          AND user_id = $3::uuid
        """,
        parsed_job,
        parsed_batch,
        owner_user_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="YouTube upload job not found for this batch.")

    status = str(row["status"] or "").lower()
    if status not in {"failed", "blocked", "cancelled"}:
        raise HTTPException(
            status_code=400,
            detail=f"Only failed/blocked/cancelled YouTube jobs can be retried (got '{status}').",
        )

    await pool.execute(
        """
        UPDATE youtube_upload_jobs
        SET status = 'pending',
            error_message = NULL,
            updated_at = NOW()
        WHERE id = $1
          AND user_id = $2::uuid
        """,
        parsed_job,
        owner_user_id,
    )
    await job_queue.enqueue_if_absent(
        user_id=UUID(owner_user_id),
        batch_id=parsed_batch,
        job_type=JOB_RUN_YOUTUBE_UPLOADS,
        payload={
            "user_id": owner_user_id,
            "batch_id": batch_id,
            "limit": 4,
        },
        priority=PRI_YOUTUBE_UPLOADS,
    )
    await _log_admin_retry(
        audit=audit,
        http_request=http_request,
        admin_id=ctx.user_id,
        action_type="admin.retry.youtube",
        target_resource=f"youtube_job:{job_id}",
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        metadata={
            "job_id": job_id,
            "role": row["role"],
            "charge_path": "none_youtube_upload",
            "previous_status": status,
        },
    )
    return AdminRetryYoutubeResponse(
        batch_id=batch_id,
        job_id=job_id,
        owner_user_id=owner_user_id,
        status="requeued",
    )
