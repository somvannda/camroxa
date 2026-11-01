"""Desktop publishing routes backed by Post for Me."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
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
    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{result.title}</title>
    <style>
      body {{
        margin: 0;
        font-family: Inter, system-ui, sans-serif;
        background: #020817;
        color: #e2e8f0;
        display: grid;
        place-items: center;
        min-height: 100vh;
        padding: 24px;
      }}
      .card {{
        width: min(100%, 560px);
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(2, 6, 23, 0.96));
        border-radius: 18px;
        padding: 28px;
      }}
      .eyebrow {{
        font-size: 11px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #94a3b8;
      }}
      h1 {{ margin: 12px 0 0; font-size: 28px; line-height: 1.2; }}
      p {{ margin: 14px 0 0; color: #cbd5e1; line-height: 1.6; }}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="eyebrow">CAMXORA</div>
      <h1>{result.title}</h1>
      <p>{result.message}</p>
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
