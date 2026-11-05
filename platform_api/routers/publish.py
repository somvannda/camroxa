"""Desktop publishing routes backed by Post for Me."""

from __future__ import annotations

import logging
import math
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.job_queue_repo import JobQueueRepository
from platform_api.repositories.publish_repo import PublishRepository
from platform_api.services.job_types import JOB_SYNC_PUBLISH_RESULTS, PRI_PUBLISH_SYNC
from platform_api.services.publish_service import PublishService

router = APIRouter(prefix="/publish", tags=["publish"])
logger = logging.getLogger(__name__)


async def _get_publish_service() -> PublishService:
    raise NotImplementedError(
        "PublishService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_publish_repo() -> PublishRepository:
    raise NotImplementedError(
        "PublishRepository dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_job_queue_repo() -> JobQueueRepository:
    raise NotImplementedError(
        "JobQueueRepository dependency not configured. Wire via app.dependency_overrides."
    )


CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
PublishServiceDep = Annotated[PublishService, Depends(_get_publish_service)]
PublishRepoDep = Annotated[PublishRepository, Depends(_get_publish_repo)]
JobQueueRepoDep = Annotated[JobQueueRepository, Depends(_get_job_queue_repo)]


class PublishAccountResponse(BaseModel):
    id: str
    profile_id: str
    platform: str
    provider: str
    postforme_account_id: str
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    status: str


class PublishAccountsResponse(BaseModel):
    accounts: list[PublishAccountResponse] = Field(default_factory=list)


class StartPublishConnectionRequest(BaseModel):
    profile_id: UUID
    platform: str = "youtube"


class SyncPublishConnectionRequest(BaseModel):
    profile_id: UUID
    platform: str = "youtube"


class StartPublishConnectionResponse(BaseModel):
    session_id: str
    auth_url: str
    status: str


class PublishQuoteResponse(BaseModel):
    op: str
    credits_per_upload: float
    amount_units: int
    balance: float
    available: bool
    platforms: list[str] = Field(default_factory=list)


class CreatePublishJobRequest(BaseModel):
    profile_id: UUID
    platform: str = "youtube"
    batch_id: UUID | None = None
    role: str = "OK"
    title: str
    description: str | None = None
    tags: list[str] | str | None = None
    privacy_status: str = "private"
    publish_at: str | None = None
    made_for_kids: bool = False
    contains_synthetic_media: bool = True
    file_name: str = ""
    file_size_bytes: int | None = None
    file_checksum: str | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None
    # Media already hosted by us (B2). When set, the provider fetches this URL
    # instead of receiving a direct upload, so large originals need no PUT.
    media_url: str | None = None


class CreatePublishJobResponse(BaseModel):
    job_uid: str
    status: str
    upload_url: str | None = None
    upload_expires_at: str | None = None
    media_url: str | None = None
    thumbnail_upload_url: str | None = None
    thumbnail_media_url: str | None = None
    file_name: str = ""
    credits_per_upload: float = 0
    platforms: list[str] = Field(default_factory=list)


class CompletePublishJobRequest(BaseModel):
    checksum: str | None = None


class RetryPublishJobResponse(BaseModel):
    job_uid: str
    status: str
    upload_url: str | None = None
    media_url: str | None = None


class PublishJobResponse(BaseModel):
    job_uid: str
    status: str
    platform: str
    provider: str
    batch_id: str | None = None
    profile_id: str | None = None
    role: str
    title: str
    description: str | None = None
    privacy_status: str
    scheduled_at: str | None = None
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    postforme_post_id: str | None = None
    credits_charged: float = 0
    error_code: str | None = None
    error_message: str | None = None
    attempt_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class PublishJobsResponse(BaseModel):
    jobs: list[PublishJobResponse] = Field(default_factory=list)


class LatestConnectionResponse(BaseModel):
    session_id: str
    status: str
    account_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None


def _account_response(account) -> PublishAccountResponse:
    return PublishAccountResponse(
        id=account.id,
        profile_id=account.profile_id,
        platform=account.platform,
        provider=account.provider,
        postforme_account_id=account.postforme_account_id,
        username=account.username,
        display_name=account.display_name,
        avatar_url=account.avatar_url,
        status=account.status,
    )


@router.get("/accounts", response_model=PublishAccountsResponse)
async def list_publish_accounts(
    ctx: CurrentUserDep,
    service: PublishServiceDep,
    profile_id: UUID | None = Query(default=None),
) -> PublishAccountsResponse:
    accounts = await service.list_accounts(
        ctx.user_id, profile_id=str(profile_id) if profile_id else None
    )
    return PublishAccountsResponse(
        accounts=[_account_response(account) for account in accounts]
    )


@router.get(
    "/accounts/latest-session",
    response_model=LatestConnectionResponse | None,
)
async def latest_publish_connection(
    ctx: CurrentUserDep,
    service: PublishServiceDep,
    profile_id: UUID = Query(...),
) -> LatestConnectionResponse | None:
    session = await service.latest_connect_session(ctx.user_id, str(profile_id))
    if session is None:
        return None
    return LatestConnectionResponse(
        session_id=session.id,
        status=session.status,
        account_ids=session.account_ids,
        error_message=session.error_message,
    )


@router.post(
    "/accounts/connect",
    response_model=StartPublishConnectionResponse,
    status_code=201,
)
async def start_publish_connection(
    request: StartPublishConnectionRequest,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> StartPublishConnectionResponse:
    # NOTE: Post for Me "Quickstart" projects reject `redirect_url_override`
    # (400: "Redirect URL Override is not allowed for Quickstart Projects").
    # The redirect must be configured as the Project Redirect URL in the
    # Post for Me dashboard; point it at
    #   https://<api-host>/api/v3/publish/accounts/callback
    # so consent finishes on our branded page and the account is linked.
    result = await service.start_connection(
        user_id=ctx.user_id,
        profile_id=str(request.profile_id),
        platform=request.platform,
    )
    return StartPublishConnectionResponse(
        session_id=result.session_id,
        auth_url=result.auth_url,
        status=result.status,
    )


@router.post(
    "/accounts/sync",
    response_model=PublishAccountsResponse,
    status_code=200,
)
async def sync_publish_connection(
    request: SyncPublishConnectionRequest,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> PublishAccountsResponse:
    accounts = await service.sync_accounts(
        user_id=ctx.user_id,
        profile_id=str(request.profile_id),
        platform=request.platform,
    )
    return PublishAccountsResponse(
        accounts=[_account_response(account) for account in accounts]
    )


@router.get("/accounts/callback", response_class=HTMLResponse, include_in_schema=False)
async def publish_account_callback(
    request: Request,
    service: PublishServiceDep,
) -> HTMLResponse:
    params = dict(request.query_params)
    result = await service.finalize_connection(params)
    tone = "#34d399" if result.status == "connected" else "#f87171"
    glyph = "✓" if result.status == "connected" else "!"
    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{result.title} · CAMXORA</title>
    <style>
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: Inter, "Segoe UI", system-ui, sans-serif;
        background:
          radial-gradient(1200px 600px at 50% -10%, rgba(116, 102, 241, 0.28), transparent 60%),
          #05070f;
        color: #e2e8f0;
        display: grid;
        place-items: center;
        min-height: 100vh;
        padding: 24px;
      }}
      .card {{
        width: min(100%, 520px);
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.96));
        border-radius: 20px;
        padding: 32px;
        text-align: center;
        box-shadow: 0 24px 60px rgba(2, 6, 23, 0.65);
      }}
      .brand {{ display: flex; align-items: center; justify-content: center; gap: 10px; }}
      .brand img {{ width: 32px; height: 32px; }}
      .brand span {{
        font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: #cbd5e1;
      }}
      .badge {{
        width: 64px; height: 64px; margin: 26px auto 0; border-radius: 50%;
        display: grid; place-items: center; font-size: 30px; font-weight: 700;
        color: {tone}; background: color-mix(in srgb, {tone} 16%, transparent);
        border: 1px solid color-mix(in srgb, {tone} 35%, transparent);
      }}
      h1 {{ margin: 18px 0 0; font-size: 26px; line-height: 1.25; }}
      p {{ margin: 12px 0 0; color: #cbd5e1; line-height: 1.65; font-size: 15px; }}
      .hint {{
        margin-top: 24px; padding: 14px 16px; border-radius: 12px;
        background: rgba(148, 163, 184, 0.08); color: #94a3b8; font-size: 13px;
      }}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="brand">
        <svg width="32" height="32" viewBox="0 0 64 64" aria-hidden="true">
          <defs>
            <linearGradient id="cx" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#7c3aed"/>
              <stop offset="1" stop-color="#a855f7"/>
            </linearGradient>
          </defs>
          <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#cx)"/>
          <g fill="#ffffff">
            <rect x="17" y="27" width="5" height="10" rx="2.5"/>
            <rect x="25.5" y="20" width="5" height="24" rx="2.5"/>
            <rect x="34" y="16" width="5" height="32" rx="2.5"/>
            <rect x="42.5" y="24" width="5" height="16" rx="2.5"/>
          </g>
        </svg>
        <span>Camxora</span>
      </div>
      <div class="badge">{glyph}</div>
      <h1>{result.title}</h1>
      <p>{result.message}</p>
      <div class="hint">You can close this tab and return to the CAMXORA studio.</div>
    </div>
  </body>
</html>
        """.strip()
    )


@router.delete("/accounts/{account_id}", status_code=200)
async def disconnect_publish_account(
    account_id: UUID,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> dict[str, str]:
    await service.disconnect_account(ctx.user_id, str(account_id))
    return {"message": "Publishing account disconnected."}


@router.get("/quote", response_model=PublishQuoteResponse)
async def publish_quote(
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> PublishQuoteResponse:
    data = await service.quote(ctx.user_id)
    return PublishQuoteResponse(**data)


@router.post("/jobs", response_model=CreatePublishJobResponse, status_code=201)
async def create_publish_job(
    request: CreatePublishJobRequest,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> CreatePublishJobResponse:
    data = await service.create_job(
        user_id=ctx.user_id,
        profile_id=str(request.profile_id),
        platform=request.platform,
        batch_id=str(request.batch_id) if request.batch_id else None,
        role=request.role,
        title=request.title,
        description=request.description,
        tags=request.tags,
        privacy_status=request.privacy_status,
        publish_at=request.publish_at,
        made_for_kids=request.made_for_kids,
        contains_synthetic_media=request.contains_synthetic_media,
        file_name=request.file_name,
        file_size_bytes=request.file_size_bytes,
        file_checksum=request.file_checksum,
        file_path=request.file_path,
        thumbnail_path=request.thumbnail_path,
        media_url=request.media_url,
    )
    return CreatePublishJobResponse(**data)


@router.post("/jobs/{job_uid}/complete", response_model=PublishJobResponse)
async def complete_publish_job(
    job_uid: str,
    request: CompletePublishJobRequest,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> PublishJobResponse:
    data = await service.complete_job(
        user_id=ctx.user_id,
        job_uid=job_uid,
        checksum=request.checksum,
    )
    return PublishJobResponse(**data)


@router.get("/jobs/{job_uid}", response_model=PublishJobResponse)
async def get_publish_job(
    job_uid: str,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> PublishJobResponse:
    data = await service.get_job(ctx.user_id, job_uid)
    return PublishJobResponse(**data)


@router.get("/jobs", response_model=PublishJobsResponse)
async def list_publish_jobs(
    ctx: CurrentUserDep,
    service: PublishServiceDep,
    batch_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> PublishJobsResponse:
    jobs = await service.list_jobs(
        ctx.user_id,
        batch_id=str(batch_id) if batch_id else None,
        status=status,
        limit=limit,
    )
    return PublishJobsResponse(jobs=[PublishJobResponse(**job) for job in jobs])


@router.post("/jobs/{job_uid}/retry", response_model=RetryPublishJobResponse)
async def retry_publish_job(
    job_uid: str,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> RetryPublishJobResponse:
    data = await service.retry_job(user_id=ctx.user_id, job_uid=job_uid)
    return RetryPublishJobResponse(**data)


@router.post("/jobs/{job_uid}/cancel", response_model=PublishJobResponse)
async def cancel_publish_job(
    job_uid: str,
    ctx: CurrentUserDep,
    service: PublishServiceDep,
) -> PublishJobResponse:
    data = await service.cancel_job(user_id=ctx.user_id, job_uid=job_uid)
    return PublishJobResponse(**data)


@router.post("/webhooks/postforme", include_in_schema=False)
async def postforme_webhook(
    request: Request,
    service: PublishServiceDep,
    repo: PublishRepoDep,
    job_queue: JobQueueRepoDep,
) -> dict[str, Any]:
    secret = request.headers.get("Post-For-Me-Webhook-Secret")
    if not service.verify_webhook_secret(secret):
        logger.warning("Rejected Post for Me webhook with an invalid secret.")
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    payload = await request.json()
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    event_type = str(payload.get("event") or payload.get("type") or "").strip()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    post_container = data.get("post") if isinstance(data.get("post"), dict) else {}
    post_id = (
        str(
            data.get("post_id")
            or data.get("social_post_id")
            or post_container.get("id")
            or data.get("id")
            or ""
        ).strip()
        or None
    )
    event_id = await repo.insert_webhook_event(
        event_type=event_type or "unknown",
        postforme_post_id=post_id,
        payload=payload,
    )
    if post_id and event_type.startswith("social.post"):
        job = await repo.get_job_by_post_id(post_id)
        if job is not None:
            await job_queue.enqueue_if_absent(
                user_id=UUID(job.user_id),
                job_type=JOB_SYNC_PUBLISH_RESULTS,
                payload={"post_id": post_id, "event_id": event_id},
                priority=PRI_PUBLISH_SYNC,
            )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Large-media uploads: B2 multipart -> public URL the provider fetches
# ---------------------------------------------------------------------------

PUBLISH_PART_SIZE = 16 * 1024 * 1024
PUBLISH_MEDIA_URL_TTL = 7 * 24 * 3600


class CreateUploadRequest(BaseModel):
    file_name: str = "video.mp4"
    content_type: str = "video/mp4"
    size_bytes: int = Field(gt=0)
    first_part_count: int = Field(default=10, ge=1, le=100)


class UploadPartUrl(BaseModel):
    part_number: int
    url: str


class CreateUploadResponse(BaseModel):
    key: str
    upload_id: str
    part_size: int
    part_count: int
    parts: list[UploadPartUrl] = Field(default_factory=list)


class SignPartsRequest(BaseModel):
    key: str
    upload_id: str
    part_numbers: list[int] = Field(min_length=1, max_length=100)


class SignPartsResponse(BaseModel):
    parts: list[UploadPartUrl] = Field(default_factory=list)


class CompleteUploadPart(BaseModel):
    part_number: int = Field(ge=1)
    etag: str


class CompleteUploadRequest(BaseModel):
    key: str
    upload_id: str
    parts: list[CompleteUploadPart] = Field(min_length=1)


class CompleteUploadResponse(BaseModel):
    key: str
    media_url: str
    expires_in_seconds: int


class AbortUploadRequest(BaseModel):
    key: str
    upload_id: str


async def _media_storage():
    from platform_api.dependencies import get_db_pool
    from platform_api.services.storage_service import StorageService
    from platform_api.services.streaming_config_service import (
        resolve_streaming_storage_config,
    )

    config = await resolve_streaming_storage_config(get_db_pool())
    if not config.configured:
        raise HTTPException(status_code=503, detail="Media storage is not configured.")
    return StorageService.from_config(config)


def _owned_media_key(user_id: str, key: str) -> str:
    candidate = str(key or "").strip()
    if not candidate.startswith(f"publish/{user_id}/"):
        raise HTTPException(
            status_code=403, detail="Upload key does not belong to this account."
        )
    return candidate


@router.post("/uploads", response_model=CreateUploadResponse, status_code=201)
async def create_publish_upload(
    request: CreateUploadRequest,
    ctx: CurrentUserDep,
) -> CreateUploadResponse:
    storage = await _media_storage()
    suffix = ".mov" if "quicktime" in request.content_type.lower() else ".mp4"
    key = f"publish/{ctx.user_id}/{uuid4().hex}{suffix}"
    upload_id = await storage.create_multipart(key=key, content_type=request.content_type)
    part_count = max(1, math.ceil(int(request.size_bytes) / PUBLISH_PART_SIZE))
    numbers = list(range(1, min(part_count, request.first_part_count) + 1))
    parts = await storage.sign_parts(key=key, upload_id=upload_id, part_numbers=numbers)
    return CreateUploadResponse(
        key=key,
        upload_id=upload_id,
        part_size=PUBLISH_PART_SIZE,
        part_count=part_count,
        parts=[UploadPartUrl(**part) for part in parts],
    )


@router.post("/uploads/parts", response_model=SignPartsResponse)
async def sign_publish_upload_parts(
    request: SignPartsRequest,
    ctx: CurrentUserDep,
) -> SignPartsResponse:
    key = _owned_media_key(ctx.user_id, request.key)
    storage = await _media_storage()
    parts = await storage.sign_parts(
        key=key,
        upload_id=request.upload_id,
        part_numbers=request.part_numbers,
    )
    return SignPartsResponse(parts=[UploadPartUrl(**part) for part in parts])


@router.post("/uploads/complete", response_model=CompleteUploadResponse)
async def complete_publish_upload(
    request: CompleteUploadRequest,
    ctx: CurrentUserDep,
) -> CompleteUploadResponse:
    key = _owned_media_key(ctx.user_id, request.key)
    storage = await _media_storage()
    await storage.complete_multipart(
        key=key,
        upload_id=request.upload_id,
        parts=[part.model_dump() for part in request.parts],
    )
    media_url = await storage.get_signed_get_url(
        key, expires_seconds=PUBLISH_MEDIA_URL_TTL
    )
    return CompleteUploadResponse(
        key=key,
        media_url=media_url,
        expires_in_seconds=PUBLISH_MEDIA_URL_TTL,
    )


@router.post("/uploads/abort")
async def abort_publish_upload(
    request: AbortUploadRequest,
    ctx: CurrentUserDep,
) -> dict[str, bool]:
    key = _owned_media_key(ctx.user_id, request.key)
    storage = await _media_storage()
    await storage.abort_multipart(key=key, upload_id=request.upload_id)
    return {"ok": True}
