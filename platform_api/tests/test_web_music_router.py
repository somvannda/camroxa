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
            "vocal_gender": "m",
            "style_weight": 0.7,
            "weirdness_constraint": 0.65,
            "audio_weight": 0.5,
            "clips": [
                {
                    "variant": "ok",
                    "label": "Night Drive · Version 1",
                    "audio_url": "/api/v1/web-music/generations/x/stream?variant=ok",
                    "download_url": "/api/v1/web-music/generations/x/download?variant=ok",
                    "ready": True,
                    "duration_seconds": 199.0,
                }
            ],
        }
    )
    service.download_mp3 = AsyncMock(return_value=(b"ID3fake", "Night Drive-ok.mp3", "audio/mpeg"))
    service.download_wav = AsyncMock(return_value=(b"RIFF____WAVEdata", "Night Drive-ok.wav", "audio/wav"))
    service.update_generation_title = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "title": "Renamed Drive",
            "lyrics": "[Verse]",
            "style": "synthwave",
            "model": "V5",
            "instrumental": False,
            "status": "SUCCESS",
            "error_message": None,
            "created_at": None,
            "clips": [],
        }
    )
    service.generate_draft = AsyncMock(return_value=("[Verse]\nCity lights", "Night Drive"))
    service.generate_styles = AsyncMock(return_value="synthwave, analog synth, 118 BPM")
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

    async def test_download_wav(self, client: AsyncClient) -> None:
        task_id = uuid4()
        response = await client.get(f"/api/v1/web-music/generations/{task_id}/download-wav?variant=ok")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/wav")
        assert response.content.startswith(b"RIFF")

    async def test_patch_generation_title(self, client: AsyncClient, mock_web_music_service: AsyncMock) -> None:
        task_id = uuid4()
        response = await client.patch(
            f"/api/v1/web-music/generations/{task_id}",
            json={"title": "Renamed Drive", "variant": "alt"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Renamed Drive"
        mock_web_music_service.update_generation_title.assert_awaited()
        assert mock_web_music_service.update_generation_title.await_args.kwargs["variant"] == "alt"
        assert mock_web_music_service.update_generation_title.await_args.kwargs["title"] == "Renamed Drive"

    async def test_get_generation_returns_advanced_settings(self, client: AsyncClient) -> None:
        task_id = uuid4()
        response = await client.get(f"/api/v1/web-music/generations/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["vocal_gender"] == "m"
        assert data["style_weight"] == 0.7
        assert data["weirdness_constraint"] == 0.65
        assert data["audio_weight"] == 0.5
        assert data["clips"][0]["label"] == "Night Drive · Version 1"
        assert data["clips"][0]["duration_seconds"] == 199.0

    async def test_stream_proxies_without_exposing_origin(
        self, client: AsyncClient, mock_web_music_service: AsyncMock
    ) -> None:
        from fastapi.responses import Response

        mock_web_music_service.proxy_playback = AsyncMock(
            return_value=Response(
                content=b"ID3fake",
                media_type="audio/mpeg",
                headers={
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "private, no-store",
                    "Content-Disposition": "inline",
                },
            )
        )
        task_id = uuid4()
        response = await client.get(
            f"/api/v1/web-music/generations/{task_id}/stream?variant=ok",
            headers={"Range": "bytes=0-1023"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "location" not in response.headers
        assert b"cdn1.suno.ai" not in response.content
        assert b"ID3fake" in response.content
        mock_web_music_service.proxy_playback.assert_awaited()
        assert mock_web_music_service.proxy_playback.await_args.kwargs["request_headers"] is not None
        mock_web_music_service.download_mp3.assert_not_awaited()

        path_response = await client.get(
            f"/api/v1/web-music/generations/{task_id}/stream/alt",
            headers={"Range": "bytes=0-1023"},
            follow_redirects=False,
        )
        assert path_response.status_code == 200
        assert mock_web_music_service.proxy_playback.await_args.kwargs["variant"] == "alt"

    async def test_generate_draft(self, client: AsyncClient, mock_web_music_service: AsyncMock) -> None:
        response = await client.post(
            "/api/v1/web-music/generate-draft",
            json={"prompt": "neon city night drive"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Night Drive"
        mock_web_music_service.generate_draft.assert_awaited()

    async def test_generate_styles_accepts_long_lyrics(
        self, client: AsyncClient, mock_web_music_service: AsyncMock
    ) -> None:
        response = await client.post(
            "/api/v1/web-music/generate-styles",
            json={"style": "pop", "lyrics": "x" * 5000, "title": "Night Drive"},
        )
        assert response.status_code == 200
        assert "synthwave" in response.json()["style"]
        mock_web_music_service.generate_styles.assert_awaited()

    async def test_generate_simple_prompt_follows_suno_custom_lyrics_limit(
        self, client: AsyncClient, mock_web_music_service: AsyncMock
    ) -> None:
        ok = await client.post(
            "/api/v1/web-music/generate",
            json={"mode": "simple", "prompt": "x" * 5000},
        )
        assert ok.status_code == 202
        mock_web_music_service.generate.assert_awaited()

        too_long = await client.post(
            "/api/v1/web-music/generate",
            json={"mode": "simple", "prompt": "x" * 5001},
        )
        assert too_long.status_code == 422
