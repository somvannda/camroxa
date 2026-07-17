"""User-facing YouTube channel connection routes."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from platform_api.dependencies import get_db_pool
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.services.public_url_service import (
    build_youtube_oauth_callback_url,
    resolve_public_api_base_url,
)
from platform_api.services.youtube_connection_service import (
    YouTubeConnectionService,
)

router = APIRouter(prefix="/youtube", tags=["youtube"])
logger = logging.getLogger(__name__)


async def _get_youtube_connection_service() -> YouTubeConnectionService:
    raise NotImplementedError(
        "YouTubeConnectionService dependency not configured. Wire via app.dependency_overrides."
    )


CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
YouTubeConnectionServiceDep = Annotated[
    YouTubeConnectionService, Depends(_get_youtube_connection_service)
]


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
    callback_url = await _resolve_youtube_callback_url(pool)
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
    service: YouTubeConnectionServiceDep,
    background_tasks: BackgroundTasks,
) -> RunYouTubeUploadsResponse:
    background_tasks.add_task(
        _run_youtube_uploads_with_logging,
        service,
        ctx.user_id,
        request.batch_id,
        max(1, min(50, int(request.limit or 4))),
    )
    return RunYouTubeUploadsResponse(scheduled=max(1, min(50, int(request.limit or 4))))


async def _run_youtube_uploads_with_logging(
    service: YouTubeConnectionService,
    user_id: str,
    batch_id: str | None,
    limit: int,
) -> None:
    try:
        await service.run_pending_upload_jobs(
            user_id=user_id,
            batch_id=batch_id,
            limit=limit,
        )
    except Exception:
        logger.exception(
            "YouTube upload runner crashed for user %s batch=%s",
            user_id,
            batch_id,
        )
