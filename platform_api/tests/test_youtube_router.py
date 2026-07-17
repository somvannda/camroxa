"""Tests for the user-facing YouTube connection router."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.youtube import _get_youtube_connection_service
from platform_api.services.youtube_connection_service import (
    YouTubeCallbackResult,
    YouTubeMergeUploadEnqueueResult,
    YouTubeConnectionStartResult,
    YouTubeConnectionState,
)

USER_CONTEXT = AuthContext(
    user_id=str(uuid4()), email="boss@example.com", role="user"
)


@pytest.fixture
def mock_youtube_connection_service() -> AsyncMock:
    service = AsyncMock()
    service.list_connections = AsyncMock(
        return_value=[
            YouTubeConnectionState(
                profile_id="profile-1",
                profile_name="Boss Primary",
                status="connected",
                channel_id="channel-1",
                channel_title="Boss Official",
                message="Channel connected.",
            )
        ]
    )
    service.start_connection = AsyncMock(
        return_value=YouTubeConnectionStartResult(
            session_id="session-1",
            auth_url="https://accounts.google.com/o/oauth2/auth",
            status="pending_browser",
        )
    )
    service.finalize_callback = AsyncMock(
        return_value=YouTubeCallbackResult(
            title="YouTube connected",
            message='Connected channel "Boss Official". Return to CAMXORA.',
            status="connected",
        )
    )
    service.select_channel = AsyncMock(
        return_value=YouTubeConnectionState(
            profile_id="profile-1",
            profile_name="Boss Primary",
            status="connected",
            channel_id="channel-1",
            channel_title="Boss Official",
            message="Channel connected.",
        )
    )
    service.disconnect = AsyncMock(return_value=None)
    service.enqueue_upload_for_merge = AsyncMock(
        return_value=YouTubeMergeUploadEnqueueResult(
            job_uid="yt-batch-profile-ok",
            status="pending",
            profile_id="profile-1",
            batch_id="batch-1",
            role="OK",
            file_path="D:/Runs/Batch-1/MERGED_OK.mp4",
            message="Merged upload job queued.",
            blocked_reason=None,
        )
    )
    service.run_pending_upload_jobs = AsyncMock(return_value=1)
    return service


@pytest.fixture
def app(mock_youtube_connection_service: AsyncMock):
    application = create_app()
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    application.dependency_overrides[_get_youtube_connection_service] = (
        lambda: mock_youtube_connection_service
    )
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestYouTubeRouter:
    async def test_lists_connections(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        response = await client.get("/api/v1/youtube/connections")

        assert response.status_code == 200
        data = response.json()
        assert data["connections"][0]["profile_id"] == "profile-1"
        assert data["connections"][0]["channel_title"] == "Boss Official"
        mock_youtube_connection_service.list_connections.assert_awaited_once()

    async def test_starts_connection(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        profile_id = str(uuid4())

        response = await client.post(f"/api/v1/youtube/profiles/{profile_id}/connect")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-1"
        assert data["status"] == "pending_browser"

        mock_youtube_connection_service.start_connection.assert_awaited_once()
        call = mock_youtube_connection_service.start_connection.await_args
        assert str(call.kwargs["user_id"]) == USER_CONTEXT.user_id
        assert str(call.kwargs["profile_id"]) == profile_id
        assert (
            call.kwargs["callback_url"]
            == "http://test/api/v1/youtube/oauth/callback"
        )

    async def test_renders_callback_page(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        response = await client.get("/api/v1/youtube/oauth/callback?state=abc123")

        assert response.status_code == 200
        assert "YouTube connected" in response.text
        assert "Return to CAMXORA" in response.text

        mock_youtube_connection_service.finalize_callback.assert_awaited_once()
        call = mock_youtube_connection_service.finalize_callback.await_args
        assert call.kwargs["state_token"] == "abc123"
        assert (
            call.kwargs["callback_url"]
            == "http://test/api/v1/youtube/oauth/callback"
        )

    async def test_selects_channel(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        response = await client.post(
            "/api/v1/youtube/connect-sessions/session-1/select-channel",
            json={"channel_id": "channel-1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["channel_id"] == "channel-1"

        mock_youtube_connection_service.select_channel.assert_awaited_once()
        call = mock_youtube_connection_service.select_channel.await_args
        assert str(call.kwargs["user_id"]) == USER_CONTEXT.user_id
        assert call.kwargs["session_id"] == "session-1"
        assert call.kwargs["channel_id"] == "channel-1"

    async def test_disconnects_channel(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        profile_id = str(uuid4())

        response = await client.delete(f"/api/v1/youtube/profiles/{profile_id}/connection")

        assert response.status_code == 200
        assert response.json() == {"message": "YouTube channel disconnected."}

        mock_youtube_connection_service.disconnect.assert_awaited_once()
        call = mock_youtube_connection_service.disconnect.await_args
        assert str(call.kwargs["user_id"]) == USER_CONTEXT.user_id
        assert str(call.kwargs["profile_id"]) == profile_id

    async def test_enqueues_merge_upload(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        profile_id = str(uuid4())
        batch_id = str(uuid4())

        response = await client.post(
            f"/api/v1/youtube/profiles/{profile_id}/uploads/merge",
            json={
                "batch_id": batch_id,
                "role": "primary",
                "merged_mp4_path": "D:/Runs/Boss/MERGED_PRIMARY.mp4",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_uid"] == "yt-batch-profile-ok"
        assert data["status"] == "pending"
        assert data["role"] == "OK"

        mock_youtube_connection_service.enqueue_upload_for_merge.assert_awaited_once()
        call = mock_youtube_connection_service.enqueue_upload_for_merge.await_args
        assert str(call.kwargs["user_id"]) == USER_CONTEXT.user_id
        assert str(call.kwargs["profile_id"]) == profile_id
        assert str(call.kwargs["batch_id"]) == batch_id
        assert call.kwargs["role"] == "primary"
        assert call.kwargs["merged_mp4_path"] == "D:/Runs/Boss/MERGED_PRIMARY.mp4"

    async def test_schedules_upload_runner(
        self, client: AsyncClient, mock_youtube_connection_service: AsyncMock
    ) -> None:
        batch_id = str(uuid4())

        response = await client.post(
            "/api/v1/youtube/uploads/run",
            json={"batch_id": batch_id, "limit": 3},
        )

        assert response.status_code == 202
        assert response.json() == {"scheduled": 3}
