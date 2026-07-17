"""Tests for streaming genre catalog service helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.services.streaming_catalog_service import StreamingCatalogService


@pytest.mark.asyncio
async def test_list_genres_adds_slug() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.list_genres = AsyncMock(
        return_value=[
            {"genre": "Tech House", "album_count": 2, "track_count": 5},
            {"genre": "Lo-Fi Study", "album_count": 1, "track_count": 2},
        ]
    )

    items = await service.list_genres()

    assert items[0]["slug"] == "tech-house"
    assert items[1]["slug"] == "lo-fi-study"


@pytest.mark.asyncio
async def test_get_genre_resolves_slug_and_decorates() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.list_genres = AsyncMock(
        return_value=[{"genre": "Tech House", "album_count": 1, "track_count": 2}]
    )
    service._repo.list_published_albums_by_genre = AsyncMock(
        return_value=[{"id": "album-1", "album_name": "Pulse", "cover_storage_key": None}]
    )
    service._repo.list_published_tracks_by_genre = AsyncMock(
        return_value=[{"id": "track-1", "title": "Night Drive", "album_cover_storage_key": None}]
    )
    service._decorate_album = AsyncMock()
    service._decorate_track = AsyncMock()

    payload = await service.get_genre("tech-house")

    assert payload is not None
    assert payload["genre"] == "Tech House"
    assert payload["slug"] == "tech-house"
    service._repo.list_published_albums_by_genre.assert_awaited_once_with("Tech House", limit=24, offset=0)
    service._repo.list_published_tracks_by_genre.assert_awaited_once_with("Tech House", limit=24, offset=0)


@pytest.mark.asyncio
async def test_get_genre_returns_none_for_unknown_slug() -> None:
    service = StreamingCatalogService(pool=AsyncMock())
    service._repo.list_genres = AsyncMock(return_value=[])

    assert await service.get_genre("missing-genre") is None
