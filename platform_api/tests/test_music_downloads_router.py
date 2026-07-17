from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.music_downloads import _get_batch_service

USER_CONTEXT = AuthContext(user_id=str(uuid4()), email="user@example.com", role="user")


@pytest.fixture
def mock_batch_service() -> AsyncMock:
    service = AsyncMock()
    service.list_pending_suno_downloads = AsyncMock(
        return_value=[
            {
                "task_id": str(uuid4()),
                "song_id": str(uuid4()),
                "batch_id": str(uuid4()),
                "title": "Dark Trap",
                "track_number": 1,
                "primary": {
                    "download_url": "https://cdn.example.com/primary.mp3",
                    "downloaded": False,
                    "output_dir": "D:/Music/Primary",
                    "target_path": "D:/Music/Primary/1. Dark Trap_OK.mp3",
                },
                "secondary": {
                    "download_url": "https://cdn.example.com/secondary.mp3",
                    "downloaded": False,
                    "output_dir": "D:/Music/Secondary",
                    "target_path": "D:/Music/Secondary/1. Dark Trap_Secondary.mp3",
                },
            }
        ]
    )
    service.sync_suno_downloads = AsyncMock(return_value=1)
    return service


@pytest.fixture
def app(mock_batch_service: AsyncMock):
    application = create_app()
    application.dependency_overrides[_get_batch_service] = lambda: mock_batch_service
    application.dependency_overrides[get_current_user] = lambda: USER_CONTEXT
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_pending_music_downloads(client: AsyncClient, mock_batch_service: AsyncMock) -> None:
    response = await client.get("/api/v1/music/downloads/pending?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["primary"]["download_url"] == "https://cdn.example.com/primary.mp3"
    assert payload["items"][0]["secondary"]["target_path"].endswith("_Secondary.mp3")
    mock_batch_service.list_pending_suno_downloads.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_music_downloads(client: AsyncClient, mock_batch_service: AsyncMock) -> None:
    response = await client.post(
        "/api/v1/music/downloads/sync",
        json={
            "items": [
                {
                    "task_id": str(uuid4()),
                    "downloaded_primary": True,
                    "output_dir_primary": "D:/Music/Primary",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 1
    mock_batch_service.sync_suno_downloads.assert_awaited_once()
