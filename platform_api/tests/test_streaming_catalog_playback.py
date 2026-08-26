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
    assert payload["url"] == f"/api/v3/public/streaming/tracks/{track_id}/stream"
    assert payload["package_status"] == "none"
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
            "url": "/api/v3/public/streaming/tracks/x/stream",
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
    response = await client.get(f"/api/v3/public/streaming/tracks/{track_id}/play-url")
    assert response.status_code == 200
    data = response.json()
    assert data["url"].startswith("/api/v3/public/streaming/tracks/")
    assert data["url"].endswith("/stream")
    assert "http" not in data["url"]


@pytest.mark.asyncio
async def test_decorate_track_strips_origin_fields() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._cover_url = AsyncMock(return_value="https://cdn.example/cover.jpg")
    track = {
        "id": uuid4(),
        "title": "Night Drive",
        "storage_key": "user/album/track-ok.mp3",
        "suno_audio_id": "abc-123",
        "suno_image_url": "https://cdn1.suno.ai/abc.jpeg",
        "cover_storage_key": "covers/x.jpg",
        "album_cover_storage_key": "covers/album.jpg",
        "suno_task_id": uuid4(),
        "play_count": 2,
        "genre": "edm",
    }

    await service._decorate_track(track)

    assert track["title"] == "Night Drive"
    assert track["cover_url"] == "https://cdn.example/cover.jpg"
    assert "storage_key" not in track
    assert "suno_audio_id" not in track
    assert "suno_image_url" not in track
    assert "cdn1.suno.ai" not in str(track)
    assert "cover_storage_key" not in track
    assert "suno_task_id" not in track


@pytest.mark.asyncio
async def test_get_album_does_not_leak_storage_or_suno_ids() -> None:
    album_id = uuid4()
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.get_published_album = AsyncMock(
        return_value={
            "id": album_id,
            "album_name": "Pulse",
            "cover_storage_key": "covers/album.jpg",
            "genre": "edm",
            "play_count": 1,
        }
    )
    service._repo.list_published_tracks_for_album = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "title": "Night Drive",
                "storage_key": "secret.mp3",
                "suno_audio_id": "leak-me",
                "cover_storage_key": None,
                "play_count": 0,
            }
        ]
    )
    captured: list[str | None] = []

    async def cover(key: str | None) -> str | None:
        captured.append(key)
        return "https://covers/signed" if key else None

    service._cover_url = cover  # type: ignore[method-assign]
    payload = await service.get_album(album_id)

    assert payload is not None
    assert "cover_storage_key" not in payload
    track = payload["tracks"][0]
    assert "storage_key" not in track
    assert "suno_audio_id" not in track
    assert "covers/album.jpg" in captured


@pytest.mark.asyncio
async def test_get_artist_strips_album_storage_keys() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.list_artist_albums = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "album_name": "Pulse",
                "artist_name": "Camxora",
                "cover_storage_key": "covers/pulse.jpg",
                "play_count": 4,
                "genre": "edm",
            }
        ]
    )
    service._cover_url = AsyncMock(return_value="/signed-cover")

    payload = await service.get_artist(uuid4())

    assert payload is not None
    album = payload["albums"][0]
    assert "cover_storage_key" not in album
    assert album["cover_url"] == "/signed-cover"


@pytest.mark.asyncio
async def test_proxy_track_audio_refuses_packaged_ciphertext() -> None:
    from platform_api.exceptions import NotFoundError

    track_id = uuid4()
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.get_published_track = AsyncMock(
        return_value={
            "storage_key": "user/album/track-ok.mp3",
            "package_status": "ready",
        }
    )
    with pytest.raises(NotFoundError, match="encrypted player"):
        await service.proxy_track_audio(track_id, range_header="bytes=0-1023")


@pytest.mark.asyncio
async def test_decorate_track_keeps_package_status_not_origin() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._cover_url = AsyncMock(return_value=None)
    track = {
        "id": uuid4(),
        "title": "Night Drive",
        "package_status": "ready",
        "storage_key": "secret.mp3",
        "audio_url_ok": "https://cdn1.suno.ai/secret.mp3",
    }
    await service._decorate_track(track)
    assert track["package_status"] == "ready"
    assert "storage_key" not in track
    assert "audio_url_ok" not in track
    assert "cdn1.suno.ai" not in str(track)


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
    assert mock_catalog_service.proxy_track_audio.await_args.kwargs["session_user_id"]
    assert mock_catalog_service.proxy_track_audio.await_args.kwargs["request_headers"] is not None
