"""Tests for music-web generation API (no desktop license)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.web_music import _get_web_music_service


@pytest.fixture
def mock_web_music_service() -> AsyncMock:
    service = AsyncMock()
    service.usage_today = AsyncMock(
        return_value={
            "limit": 5,
            "used": 1,
            "remaining": 4,
            "is_pro": False,
            "requires_upgrade": False,
        }
    )
    service.generate = AsyncMock(
        return_value={
            "task_id": str(uuid4()),
            "status": "PENDING",
            "title": "Night Drive",
            "style": "synthwave",
            "quota": {
                "limit": 5,
                "used": 2,
                "remaining": 3,
                "is_pro": False,
                "requires_upgrade": False,
            },
        }
    )
    service.list_generations = AsyncMock(
        return_value={"items": [], "total": 0, "limit": 40, "offset": 0}
    )
    service.get_generation = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "title": "Night Drive",
            "lyrics": "[Verse]",
            "style": "synthwave",
            "model": "V5",
            "instrumental": False,
            "status": "SUCCESS",
            "error_message": None,
            "created_at": None,
            "clips": [
                {
                    "variant": "ok",
                    "label": "Version 1",
                    "audio_url": "/api/v1/web-music/generations/x/stream?variant=ok",
                    "download_url": "/api/v1/web-music/generations/x/download?variant=ok",
                    "ready": True,
                }
            ],
        }
    )
    service.download_mp3 = AsyncMock(return_value=(b"ID3fake", "Night Drive-ok.mp3", "audio/mpeg"))
    return service


@pytest.fixture
def app(mock_web_music_service: AsyncMock):
    application = create_app()
    user_id = str(uuid4())

    async def current_user() -> AuthContext:
        return AuthContext(user_id=user_id, email="listener@example.com", role="user")

    application.dependency_overrides[get_current_user] = current_user
    application.dependency_overrides[_get_web_music_service] = lambda: mock_web_music_service
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestWebMusicRouter:
    async def test_quota(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/web-music/quota")
        assert response.status_code == 200
        assert response.json()["remaining"] == 4

    async def test_generate_advanced(self, client: AsyncClient, mock_web_music_service: AsyncMock) -> None:
        response = await client.post(
            "/api/v1/web-music/generate",
            json={
                "mode": "advanced",
                "lyrics": "[Verse]\nCity lights",
                "style": "synthwave",
                "title": "Night Drive",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["title"] == "Night Drive"
        assert data["quota"]["remaining"] == 3
        mock_web_music_service.generate.assert_awaited()

    async def test_list_generations(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/web-music/generations")
        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_download(self, client: AsyncClient) -> None:
        task_id = uuid4()
        response = await client.get(f"/api/v1/web-music/generations/{task_id}/download?variant=ok")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/mpeg")
        assert b"ID3fake" in response.content
