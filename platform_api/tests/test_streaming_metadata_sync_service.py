"""Tests for streaming metadata sync admin flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_api.services.streaming_metadata_sync_service import StreamingMetadataSyncService
from platform_api.services.suno_audio_resolver import SunoTaskDownloadUrls


@pytest.mark.asyncio
async def test_sync_track_metadata_uses_description_genres(monkeypatch) -> None:
    track_id = uuid4()
    album_id = uuid4()
    user_id = uuid4()

    pool = AsyncMock()
    service = StreamingMetadataSyncService(pool)
    service._repo.get_track_for_metadata_sync = AsyncMock(
        return_value={
            "id": track_id,
            "album_id": album_id,
            "user_id": user_id,
            "album_slug": "test-album",
            "variant": "ok",
            "external_task_id": "suno-ext-1",
            "song_lyrics": "Line one",
            "description_genres": ["Eurodance", "Hands Up"],
            "suno_style": "Eurodance and Hands Up track featuring full production prompt text",
            "genre": None,
            "cover_storage_key": None,
        }
    )
    service._repo.update_track_metadata_sync = AsyncMock()
    service._repo.update_album_genre = AsyncMock()

    refreshed = SunoTaskDownloadUrls(
        duration_ok=123.4,
        tags_ok="pop, electronic",
        image_url_ok="https://cdn.example.com/cover.jpg",
        refreshed=True,
    )
    service._upload_service._refresh_task_download_urls = AsyncMock(return_value=refreshed)
    service._upload_service._maybe_upload_suno_cover = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "platform_api.services.streaming_metadata_sync_service.resolve_streaming_storage_config",
        AsyncMock(return_value=MagicMock(configured=False)),
    )

    result = await service.sync_track_metadata(track_id)

    assert result["ok"] is True
    assert result["genre"] == "Eurodance"
    assert result["duration_seconds"] == 123.4
    assert result["has_lyrics"] is True
    kwargs = service._repo.update_track_metadata_sync.await_args.kwargs
    assert kwargs["genre"] == "Eurodance"
    assert kwargs["genres"] == ["Eurodance", "Hands Up"]
    assert kwargs["tags"] == ["pop", "electronic"]
    service._repo.update_album_genre.assert_awaited_once_with(
        album_id,
        "Eurodance",
        genres=["Eurodance", "Hands Up"],
        overwrite=True,
    )


@pytest.mark.asyncio
async def test_sync_track_metadata_updates_repo(monkeypatch) -> None:
    track_id = uuid4()
    album_id = uuid4()
    user_id = uuid4()

    pool = AsyncMock()
    service = StreamingMetadataSyncService(pool)
    service._repo.get_track_for_metadata_sync = AsyncMock(
        return_value={
            "id": track_id,
            "album_id": album_id,
            "user_id": user_id,
            "album_slug": "test-album",
            "variant": "ok",
            "external_task_id": "suno-ext-1",
            "song_lyrics": "Line one",
            "genre": None,
            "cover_storage_key": None,
        }
    )
    service._repo.update_track_metadata_sync = AsyncMock()
    service._repo.update_album_genre = AsyncMock()

    refreshed = SunoTaskDownloadUrls(
        duration_ok=123.4,
        tags_ok="pop, electronic",
        image_url_ok="https://cdn.example.com/cover.jpg",
        refreshed=True,
    )
    service._upload_service._refresh_task_download_urls = AsyncMock(return_value=refreshed)
    service._upload_service._maybe_upload_suno_cover = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "platform_api.services.streaming_metadata_sync_service.resolve_streaming_storage_config",
        AsyncMock(return_value=MagicMock(configured=False)),
    )

    result = await service.sync_track_metadata(track_id)

    assert result["ok"] is True
    assert result["genre"] == "pop"
    assert result["duration_seconds"] == 123.4
    assert result["has_lyrics"] is True
    service._repo.update_track_metadata_sync.assert_awaited_once()
    service._repo.update_album_genre.assert_awaited_once_with(
        album_id,
        "pop",
        genres=["pop", "electronic"],
        overwrite=True,
    )


@pytest.mark.asyncio
async def test_sync_track_metadata_normalizes_list_style(monkeypatch) -> None:
    track_id = uuid4()
    album_id = uuid4()
    user_id = uuid4()

    pool = AsyncMock()
    service = StreamingMetadataSyncService(pool)
    service._repo.get_track_for_metadata_sync = AsyncMock(
        return_value={
            "id": track_id,
            "album_id": album_id,
            "user_id": user_id,
            "album_slug": "test-album",
            "variant": "ok",
            "external_task_id": "suno-ext-1",
            "song_lyrics": "Line one",
            "description_genres": ["Eurodance", "Hands Up"],
            "suno_style": ["Eurodance", "Hands Up"],
            "genre": None,
            "cover_storage_key": None,
        }
    )
    service._repo.update_track_metadata_sync = AsyncMock()
    service._repo.update_album_genre = AsyncMock()

    refreshed = SunoTaskDownloadUrls(
        duration_ok=99.0,
        tags_ok="pop, electronic",
        refreshed=True,
    )
    service._upload_service._refresh_task_download_urls = AsyncMock(return_value=refreshed)
    service._upload_service._maybe_upload_suno_cover = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "platform_api.services.streaming_metadata_sync_service.resolve_streaming_storage_config",
        AsyncMock(return_value=MagicMock(configured=False)),
    )

    result = await service.sync_track_metadata(track_id)

    assert result["genre"] == "Eurodance"
    service._repo.update_track_metadata_sync.assert_awaited_once()
    kwargs = service._repo.update_track_metadata_sync.await_args.kwargs
    assert kwargs["tags"] == ["pop", "electronic"]
    assert kwargs["genres"] == ["Eurodance", "Hands Up"]
    assert kwargs["overwrite"] is True
    album_kwargs = service._repo.update_album_genre.await_args.kwargs
    assert album_kwargs["genres"] == ["Eurodance", "Hands Up"]
    assert album_kwargs["overwrite"] is True
    assert kwargs["genres"] == ["Eurodance", "Hands Up"]


@pytest.mark.asyncio
async def test_sync_all_tracks_metadata_counts_results(monkeypatch) -> None:
    track_ids = [uuid4(), uuid4()]
    pool = AsyncMock()
    service = StreamingMetadataSyncService(pool)
    service._repo.list_tracks_for_metadata_sync = AsyncMock(
        return_value=[{"id": track_ids[0]}, {"id": track_ids[1]}]
    )

    async def _sync(track_id):
        if track_id == track_ids[1]:
            raise RuntimeError("Suno unavailable")
        return {"ok": True}

    service.sync_track_metadata = AsyncMock(side_effect=_sync)

    result = await service.sync_all_tracks_metadata(limit=2)

    assert result["synced"] == 1
    assert result["total"] == 2
    assert len(result["failed"]) == 1
