"""User-facing YouTube channel connection routes."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.repositories.job_queue_repo import JobQueueRepository
from platform_api.services.job_types import JOB_RUN_YOUTUBE_UPLOADS, PRI_YOUTUBE_UPLOADS
from platform_api.services.public_url_service import (
    build_youtube_oauth_callback_url,
    resolve_public_api_base_url,
)
from platform_api.services.youtube_connection_service import (
    YouTubeConnectionService,
)

router = APIRouter(prefix="/youtube", tags=["youtube"])


class YouTubeAccessTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    channel_id: str | None = None
    channel_title: str | None = None


class RecordYouTubeUploadRequest(BaseModel):
    batch_id: UUID
    profile_id: UUID
    role: str = "OK"
    video_id: str
    video_url: str | None = None
    title: str = ""
    status: str = "success"
    error_message: str | None = None
logger = logging.getLogger(__name__)


async def _get_youtube_connection_service() -> YouTubeConnectionService:
    raise NotImplementedError(
        "YouTubeConnectionService dependency not configured. Wire via app.dependency_overrides."
    )


async def _get_job_queue_repo() -> JobQueueRepository:
    raise NotImplementedError(
        "JobQueueRepository dependency not configured. Wire via app.dependency_overrides."
    )


CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
YouTubeConnectionServiceDep = Annotated[
    YouTubeConnectionService, Depends(_get_youtube_connection_service)
]
JobQueueRepoDep = Annotated[JobQueueRepository, Depends(_get_job_queue_repo)]


class YouTubeChannelOption(BaseModel):
    id: str
    title: str


class YouTubePlaylistOption(BaseModel):
    id: str
    title: str


class YouTubeConnectionResponse(BaseModel):
    profile_id: str
    profile_name: str
    status: str
    channel_id: str | None = None
    channel_title: str | None = None
    session_id: str | None = None
    channels: list[YouTubeChannelOption] = []
    message: str | None = None


class YouTubeConnectionsResponse(BaseModel):
    connections: list[YouTubeConnectionResponse]


class YouTubePlaylistsResponse(BaseModel):
    playlists: list[YouTubePlaylistOption]


class StartYouTubeConnectionResponse(BaseModel):
    session_id: str
    auth_url: str
    status: str


class SelectYouTubeChannelRequest(BaseModel):
    channel_id: str


class EnqueueYouTubeMergeUploadRequest(BaseModel):
    batch_id: UUID
    role: str
    merged_mp4_path: str


class EnqueueYouTubeMergeUploadResponse(BaseModel):
    job_uid: str
    status: str
    profile_id: str
    batch_id: str
    role: str
    file_path: str
    message: str
    blocked_reason: str | None = None


class RunYouTubeUploadsRequest(BaseModel):
    batch_id: str | None = None
    limit: int = 4


class RunYouTubeUploadsResponse(BaseModel):
    scheduled: int


def _to_connection_response(state) -> YouTubeConnectionResponse:
    return YouTubeConnectionResponse(
        profile_id=state.profile_id,
        profile_name=state.profile_name,
        status=state.status,
        channel_id=state.channel_id,
        channel_title=state.channel_title,
        session_id=state.session_id,
        channels=[
            YouTubeChannelOption(
                id=str(channel.get("id") or ""),
                title=str(channel.get("title") or ""),
            )
            for channel in (state.channels or [])
            if str(channel.get("id") or "").strip()
        ],
        message=state.message,
    )


@router.get("/connections", response_model=YouTubeConnectionsResponse)
async def list_youtube_connections(
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubeConnectionsResponse:
    states = await service.list_connections(UUID(ctx.user_id))
    return YouTubeConnectionsResponse(
        connections=[_to_connection_response(state) for state in states]
    )


class CreatePlaylistRequest(BaseModel):
    title: str
    privacy_status: str = "private"


@router.post("/profiles/{profile_id}/playlists", response_model=YouTubePlaylistOption, status_code=201)
async def create_youtube_playlist(
    profile_id: UUID,
    request: CreatePlaylistRequest,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubePlaylistOption:
    """Create a playlist on the connected channel so it can be selected here."""
    data = await service.create_playlist(
        user_id=UUID(ctx.user_id),
        profile_id=profile_id,
        title=request.title,
        privacy_status=request.privacy_status,
    )
    return YouTubePlaylistOption(id=data["id"], title=data["title"])


@router.get("/profiles/{profile_id}/playlists", response_model=YouTubePlaylistsResponse)
async def list_youtube_playlists(
    profile_id: UUID,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubePlaylistsResponse:
    playlists = await service.list_connected_playlists(
        user_id=UUID(ctx.user_id),
        profile_id=profile_id,
    )
    return YouTubePlaylistsResponse(
        playlists=[
            YouTubePlaylistOption(
                id=str(playlist.get("id") or ""),
                title=str(playlist.get("title") or ""),
            )
            for playlist in playlists
            if str(playlist.get("id") or "").strip()
        ]
    )


async def _resolve_youtube_callback_url(pool: Any) -> str:
    """Use the public API host so Google OAuth matches api.*, not app.* proxy host."""
    api_base = await resolve_public_api_base_url(pool)
    return build_youtube_oauth_callback_url(api_base)


# ---------------------------------------------------------------------------
# Bring your own Google OAuth client
# ---------------------------------------------------------------------------


class UserOAuthAppResponse(BaseModel):
    configured: bool = False
    client_id: str | None = None
    name: str | None = None


class SaveUserOAuthAppRequest(BaseModel):
    client_id: str
    client_secret: str
    name: str = "My Google app"


async def _oauth_credentials_work(client_id: str, client_secret: str, callback_url: str) -> tuple[bool, str]:
    """Ask Google whether this client id/secret pair exists.

    A deliberately invalid authorization code produces `invalid_client` for
    bad credentials and `invalid_grant` for good ones, so this validates the
    pair without storing anything.
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": "camxora-validation-code",
                    "redirect_uri": callback_url,
                },
            )
    except Exception as exc:  # noqa: BLE001 - reported to the user
        return False, f"Could not reach Google: {exc}"

    try:
        body = response.json()
    except Exception:
        body = {}
    error = str(body.get("error") or "").strip()
    if error == "invalid_client":
        return False, "Google rejected that client id / secret pair."
    if error in {"invalid_grant", "invalid_request", "redirect_uri_mismatch"}:
        return True, ""
    if response.status_code < 400:
        return True, ""
    return False, f"Google rejected the credentials ({error or response.status_code})."


@router.get("/oauth-app", response_model=UserOAuthAppResponse)
async def get_user_youtube_oauth_app(ctx: CurrentUserDep) -> UserOAuthAppResponse:
    """Whether this account connected with its own Google client."""
    from platform_api.dependencies import get_youtube_oauth_app_repo

    app = await get_youtube_oauth_app_repo().get_for_user(ctx.user_id)
    if app is None:
        return UserOAuthAppResponse()
    return UserOAuthAppResponse(configured=True, client_id=app.client_id, name=app.name)


@router.put("/oauth-app", response_model=UserOAuthAppResponse)
async def save_user_youtube_oauth_app(
    request: SaveUserOAuthAppRequest,
    ctx: CurrentUserDep,
    pool: Any = Depends(get_db_pool),
) -> UserOAuthAppResponse:
    """Save the user's own Google client so connects use their quota.

    Bring-your-own keeps each account on its own YouTube quota (a shared
    project allows ~6 uploads/day) and avoids the platform app's verification
    being a single point of failure.
    """
    from fastapi import HTTPException

    from platform_api.dependencies import (
        get_youtube_oauth_app_repo,
        get_youtube_oauth_encryption,
    )

    client_id = str(request.client_id or "").strip()
    client_secret = str(request.client_secret or "").strip()
    if not client_id.endswith(".apps.googleusercontent.com"):
        raise HTTPException(
            status_code=400,
            detail="That does not look like a Google OAuth client id.",
        )
    if len(client_secret) < 10:
        raise HTTPException(status_code=400, detail="The client secret is too short.")

    encryption = get_youtube_oauth_encryption()
    if encryption is None:
        raise HTTPException(
            status_code=503,
            detail="Credential storage is unavailable on this server.",
        )

    callback_url = await _resolve_youtube_callback_url(pool)
    ok, reason = await _oauth_credentials_work(client_id, client_secret, callback_url)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    record = await get_youtube_oauth_app_repo().save_for_user(
        user_id=ctx.user_id,
        name=str(request.name or "My Google app").strip() or "My Google app",
        client_id=client_id,
        encrypted_client_secret=encryption.encrypt(client_secret),
    )
    if record is None:
        raise HTTPException(status_code=500, detail="Could not save the credentials.")
    logger.info("User %s saved their own YouTube OAuth app", ctx.user_id)
    return UserOAuthAppResponse(
        configured=True, client_id=record.client_id, name=record.name
    )


@router.delete("/oauth-app", status_code=200)
async def delete_user_youtube_oauth_app(ctx: CurrentUserDep) -> dict[str, Any]:
    """Forget the user's own client and fall back to the platform app."""
    from platform_api.dependencies import get_youtube_oauth_app_repo

    removed = await get_youtube_oauth_app_repo().delete_for_user(ctx.user_id)
    return {"removed": bool(removed)}


@router.post("/profiles/{profile_id}/connect", response_model=StartYouTubeConnectionResponse)
async def start_youtube_connection(
    profile_id: UUID,
    request: Request,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
    pool: Any = Depends(get_db_pool),
) -> StartYouTubeConnectionResponse:
    _ = request
    callback_url = await _resolve_youtube_callback_url(pool)
    result = await service.start_connection(
        user_id=UUID(ctx.user_id),
        profile_id=profile_id,
        callback_url=callback_url,
    )
    return StartYouTubeConnectionResponse(
        session_id=result.session_id,
        auth_url=result.auth_url,
        status=result.status,
    )


@router.get("/oauth/callback", name="youtube_oauth_callback", response_class=HTMLResponse)
async def youtube_oauth_callback(
    request: Request,
    service: YouTubeConnectionServiceDep,
    pool: Any = Depends(get_db_pool),
    state: str = Query(default=""),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    configured = await _resolve_youtube_callback_url(pool)
    incoming = str(request.url.replace(query="", fragment=""))
    callback_url = incoming if incoming.endswith("/youtube/oauth/callback") else configured
    result = await service.finalize_callback(
        callback_url=callback_url,
        callback_request_url=str(request.url),
        state_token=state,
        error_message=error,
    )
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
        box-shadow: 0 24px 60px rgba(2, 6, 23, 0.35);
      }}
      .eyebrow {{
        font-size: 11px;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #94a3b8;
      }}
      h1 {{
        margin: 12px 0 0;
        font-size: 28px;
        line-height: 1.2;
      }}
      p {{
        margin: 14px 0 0;
        color: #cbd5e1;
        line-height: 1.6;
      }}
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


class YouTubeQuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: int
    resets_at: str


@router.get("/quota", response_model=YouTubeQuotaResponse)
async def youtube_quota(
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubeQuotaResponse:
    """Uploads used today against Google's per-project daily allowance."""
    data = await service.quota_status(UUID(ctx.user_id))
    return YouTubeQuotaResponse(**data)


@router.post(
    "/profiles/{profile_id}/access-token", response_model=YouTubeAccessTokenResponse
)
async def issue_youtube_access_token(
    profile_id: UUID,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubeAccessTokenResponse:
    """Short-lived token so the desktop can upload straight to YouTube."""
    data = await service.issue_access_token(
        user_id=UUID(ctx.user_id), profile_id=profile_id
    )
    return YouTubeAccessTokenResponse(**data)


@router.post("/uploads/report")
async def report_youtube_upload(
    request: RecordYouTubeUploadRequest,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> dict[str, Any]:
    """Record a desktop-direct upload, then charge it once it is live.

    Native uploads used to bypass billing entirely while the legacy provider
    path charged, so the same action cost different amounts depending on the
    route. The charge is applied here, exactly once per job row.
    """
    job_id = await service.record_upload_result(
        user_id=UUID(ctx.user_id),
        batch_id=request.batch_id,
        profile_id=request.profile_id,
        role=request.role,
        video_id=request.video_id,
        video_url=request.video_url,
        title=request.title,
        status=request.status,
        error_message=request.error_message,
    )
    if job_id and str(request.status) == "success":
        await _charge_native_upload(UUID(ctx.user_id), job_id)

    return {"ok": True, "job_id": job_id}


async def _charge_native_upload(user_id: UUID, job_id: str) -> None:
    """Charge the publish price once, guarded by the job's charged column."""
    from platform_api.dependencies import get_v3_billing_service
    from platform_api.services.publish_pricing import POSTFORME_PUBLISH_OP

    pool = get_db_pool()
    try:
        row = await pool.fetchrow(
            "SELECT credits_charged_units, credit_ref_id FROM youtube_upload_jobs "
            "WHERE id = $1::uuid",
            job_id,
        )
        if row is None or int(row["credits_charged_units"] or 0) > 0:
            return
        charge = await get_v3_billing_service().charge(
            user_id=user_id,
            op=POSTFORME_PUBLISH_OP,
            ref_id=f"youtube-upload:{job_id}",
            product="desktop",
        )
        units = int(charge.get("amount_units") or 0)
        await pool.execute(
            "UPDATE youtube_upload_jobs SET credits_charged_units = $2, "
            "credit_ref_id = $3, updated_at = NOW() WHERE id = $1::uuid "
            "AND credits_charged_units = 0",
            job_id,
            units,
            f"youtube-upload:{job_id}",
        )
    except Exception:
        logger.warning("Could not charge native YouTube upload %s", job_id, exc_info=True)


@router.post("/connect-sessions/{session_id}/select-channel", response_model=YouTubeConnectionResponse)
async def select_youtube_channel(
    session_id: str,
    request: SelectYouTubeChannelRequest,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubeConnectionResponse:
    state = await service.select_channel(
        user_id=UUID(ctx.user_id),
        session_id=session_id,
        channel_id=request.channel_id,
    )
    from platform_api.services.workspace_notifications import notify_workspace_changed

    await notify_workspace_changed(
        ctx.user_id,
        source="youtube.select_channel",
        scope="youtube",
        extra={"profile_id": str(state.profile_id)},
    )
    return _to_connection_response(state)


@router.delete("/profiles/{profile_id}/connection", status_code=200)
async def disconnect_youtube_channel(
    profile_id: UUID,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> dict[str, str]:
    await service.disconnect(user_id=UUID(ctx.user_id), profile_id=profile_id)
    from platform_api.services.workspace_notifications import notify_workspace_changed

    await notify_workspace_changed(
        ctx.user_id,
        source="youtube.disconnect",
        scope="youtube",
        extra={"profile_id": str(profile_id)},
    )
    return {"message": "YouTube channel disconnected."}


@router.post("/profiles/{profile_id}/resync", response_model=YouTubeConnectionResponse)
async def resync_youtube_channel_profile(
    profile_id: UUID,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> YouTubeConnectionResponse:
    state = await service.resync_connected_profile(
        user_id=UUID(ctx.user_id),
        profile_id=profile_id,
    )
    from platform_api.services.workspace_notifications import notify_workspace_changed

    await notify_workspace_changed(
        ctx.user_id,
        source="youtube.resync",
        scope="youtube",
        extra={"profile_id": str(profile_id)},
    )
    return _to_connection_response(state)


@router.post(
    "/profiles/{profile_id}/uploads/merge",
    response_model=EnqueueYouTubeMergeUploadResponse,
)
async def enqueue_youtube_merge_upload(
    profile_id: UUID,
    request: EnqueueYouTubeMergeUploadRequest,
    ctx: CurrentUserDep,
    service: YouTubeConnectionServiceDep,
) -> EnqueueYouTubeMergeUploadResponse:
    result = await service.enqueue_upload_for_merge(
        user_id=UUID(ctx.user_id),
        batch_id=request.batch_id,
        profile_id=profile_id,
        role=request.role,
        merged_mp4_path=request.merged_mp4_path,
    )
    return EnqueueYouTubeMergeUploadResponse(
        job_uid=result.job_uid,
        status=result.status,
        profile_id=result.profile_id,
        batch_id=result.batch_id,
        role=result.role,
        file_path=result.file_path,
        message=result.message,
        blocked_reason=result.blocked_reason,
    )


@router.post("/uploads/run", response_model=RunYouTubeUploadsResponse, status_code=202)
async def run_youtube_uploads(
    request: RunYouTubeUploadsRequest,
    ctx: CurrentUserDep,
    job_queue: JobQueueRepoDep,
) -> RunYouTubeUploadsResponse:
    limit = max(1, min(50, int(request.limit or 4)))
    batch_uuid = UUID(str(request.batch_id)) if request.batch_id else None
    await job_queue.enqueue_if_absent(
        user_id=UUID(ctx.user_id),
        batch_id=batch_uuid,
        job_type=JOB_RUN_YOUTUBE_UPLOADS,
        payload={
            "user_id": ctx.user_id,
            "batch_id": str(request.batch_id) if request.batch_id else None,
            "limit": limit,
        },
        priority=PRI_YOUTUBE_UPLOADS,
    )
    return RunYouTubeUploadsResponse(scheduled=limit)
