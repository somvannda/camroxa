from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.responses import Response
from httpx import ASGITransport, AsyncClient

from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user
from platform_api.routers.streaming_public import _get_catalog_service
from platform_api.services.streaming_catalog_service import StreamingCatalogService
from platform_api.services.streaming_config_service import StreamingStorageConfig


def _configured_storage() -> StreamingStorageConfig:
    return StreamingStorageConfig(
        key_id="key",
        application_key="secret",
        bucket="camxora-media",
        region="us-west-004",
        endpoint="https://s3.us-west-004.backblazeb2.com",
        cdn_base_url="",
        stream_url_ttl_seconds=3600,
        secret_source="environment",
        configured=True,
    )


@pytest.mark.asyncio
async def test_get_play_url_returns_proxy_path_not_origin() -> None:
    track_id = uuid4()
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.get_published_track = AsyncMock(
        return_value={
            "storage_key": "user/album/track-ok.mp3",
            "title": "Night Drive",
            "album_id": uuid4(),
            "album_name": "Pulse",
            "user_id": uuid4(),
            "artist_name": "Camxora",
            "variant": "ok",
            "duration_seconds": 199,
            "play_count": 3,
            "genre": "edm",
            "lyrics": "[Verse]",
            "cover_storage_key": None,
            "album_cover_storage_key": None,
        }
    )
    service._repo.increment_play_count = AsyncMock()
    service._cover_url = AsyncMock(return_value=None)

    with patch(
        "platform_api.services.streaming_catalog_service.resolve_streaming_storage_config",
        AsyncMock(return_value=_configured_storage()),
    ), patch(
        "platform_api.services.streaming_catalog_service.StorageService.from_config",
    ) as from_config:
        payload = await service.get_play_url(track_id)

    assert payload is not None
    assert payload["url"] == f"/api/v1/public/streaming/tracks/{track_id}/stream"
    assert "backblaze" not in payload["url"].lower()
    assert not payload["url"].startswith("http")
    service._repo.increment_play_count.assert_not_awaited()
    from_config.assert_not_called()


@pytest.mark.asyncio
async def test_proxy_track_audio_increments_on_initial_range() -> None:
    track_id = uuid4()
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.get_published_track = AsyncMock(
        return_value={"storage_key": "user/album/track-ok.mp3"}
    )
    service._repo.increment_play_count = AsyncMock()
    storage = MagicMock()
    storage.get_signed_get_url = AsyncMock(return_value="https://b2.example/secret.mp3")
    proxied = Response(content=b"ID3fake", media_type="audio/mpeg")

    with patch(
        "platform_api.services.streaming_catalog_service.resolve_streaming_storage_config",
        AsyncMock(return_value=_configured_storage()),
    ), patch(
        "platform_api.services.streaming_catalog_service.StorageService.from_config",
        return_value=storage,
    ), patch(
        "platform_api.services.streaming_catalog_service.proxy_origin_audio",
        AsyncMock(return_value=proxied),
    ) as proxy:
        response = await service.proxy_track_audio(track_id, range_header="bytes=0-1023")

    assert response is proxied
    service._repo.increment_play_count.assert_awaited_once_with(track_id)
    proxy.assert_awaited_once()
    assert proxy.await_args.kwargs["range_header"] == "bytes=0-1023"
    assert proxy.await_args.args[0] == "https://b2.example/secret.mp3"


@pytest.mark.asyncio
async def test_proxy_track_audio_skips_increment_on_seek() -> None:
    track_id = uuid4()
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.get_published_track = AsyncMock(
        return_value={"storage_key": "user/album/track-ok.mp3"}
    )
    service._repo.increment_play_count = AsyncMock()
    storage = MagicMock()
    storage.get_signed_get_url = AsyncMock(return_value="https://b2.example/secret.mp3")

    with patch(
        "platform_api.services.streaming_catalog_service.resolve_streaming_storage_config",
        AsyncMock(return_value=_configured_storage()),
    ), patch(
        "platform_api.services.streaming_catalog_service.StorageService.from_config",
        return_value=storage,
    ), patch(
        "platform_api.services.streaming_catalog_service.proxy_origin_audio",
        AsyncMock(return_value=Response(content=b"ID3fake", media_type="audio/mpeg")),
    ):
        await service.proxy_track_audio(track_id, range_header="bytes=1024-2047")

    service._repo.increment_play_count.assert_not_awaited()


@pytest.fixture
def mock_catalog_service() -> AsyncMock:
    service = AsyncMock()
    service.get_play_url = AsyncMock(
        return_value={
            "track_id": str(uuid4()),
            "url": "/api/v1/public/streaming/tracks/x/stream",
            "expires_at": "2026-08-17T00:00:00+00:00",
            "title": "Night Drive",
        }
    )
    service.proxy_track_audio = AsyncMock(
        return_value=Response(
            content=b"ID3fake",
            media_type="audio/mpeg",
            headers={"Cache-Control": "private, no-store", "Accept-Ranges": "bytes"},
        )
    )
    return service


@pytest.fixture
def app(mock_catalog_service: AsyncMock):
    application = create_app()
    user_id = str(uuid4())

    async def current_user() -> AuthContext:
        return AuthContext(user_id=user_id, email="listener@example.com", role="user")

    application.dependency_overrides[get_current_user] = current_user
    application.dependency_overrides[_get_catalog_service] = lambda: mock_catalog_service
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_play_url_endpoint_does_not_expose_origin(client: AsyncClient) -> None:
    track_id = uuid4()
    response = await client.get(f"/api/v1/public/streaming/tracks/{track_id}/play-url")
    assert response.status_code == 200
    data = response.json()
    assert data["url"].startswith("/api/v1/public/streaming/tracks/")
    assert data["url"].endswith("/stream")
    assert "http" not in data["url"]


@pytest.mark.asyncio
async def test_catalog_stream_proxies_without_location(
    client: AsyncClient, mock_catalog_service: AsyncMock
) -> None:
    track_id = uuid4()
    response = await client.get(
        f"/api/v1/public/streaming/tracks/{track_id}/stream",
        headers={"Range": "bytes=0-1023"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "location" not in response.headers
    assert b"ID3fake" in response.content
    mock_catalog_service.proxy_track_audio.assert_awaited()
