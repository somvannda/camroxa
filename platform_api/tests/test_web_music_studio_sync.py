"""Suno Studio mirror status/refresh proxies: ownership first, then the mirror."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError
from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    return WebMusicService(AsyncMock(), AsyncMock(), redis=None)


PENDING = {
    "status": "pending",
    "suno_project_id": None,
    "suno_version_id": None,
    "suno_remote_version_id": None,
    "last_error": None,
    "synced_at": None,
    "skipped_clips": [],
    "state_sync": False,
}


@pytest.mark.asyncio
async def test_status_returns_pending_without_a_link() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    service._studio_sync_request = AsyncMock(return_value=None)

    result = await service.studio_sync_status(uuid4(), uuid4())

    assert result == PENDING


@pytest.mark.asyncio
async def test_status_returns_the_mirror_view() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    mirrored = {**PENDING, "status": "linked", "suno_project_id": "suno-1"}
    service._studio_sync_request = AsyncMock(return_value=mirrored)

    result = await service.studio_sync_status(uuid4(), uuid4())

    assert result["status"] == "linked"
    assert result["suno_project_id"] == "suno-1"


@pytest.mark.asyncio
async def test_status_checks_ownership_before_calling_the_mirror() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)
    service._studio_sync_request = AsyncMock()

    with pytest.raises(NotFoundError):
        await service.studio_sync_status(uuid4(), uuid4())

    service._studio_sync_request.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_proxies_the_read_only_check() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": uuid4()})
    service._studio_sync_request = AsyncMock(return_value={**PENDING, "status": "conflict"})

    result = await service.refresh_studio_project(uuid4(), uuid4())

    assert result["status"] == "conflict"
    service._studio_sync_request.assert_awaited_once()
    assert service._studio_sync_request.await_args.args[2] == "refresh"


@pytest.mark.asyncio
async def test_force_sync_refuses_without_a_document() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.sync_studio_project(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_asset_enrichment_attaches_the_suno_clip_id() -> None:
    service = _service()
    song_id = uuid4()
    document = {
        "user_id": str(uuid4()),
        "title": "Asset",
        "data": {
            "lanes": [
                {"id": "clip-1", "songId": str(song_id), "songVariant": "ok"},
                {"id": "clip-2", "songId": str(song_id), "songVariant": "alt"},
                {"id": "clip-3", "songId": str(song_id)},
            ]
        },
    }
    service._pool.fetch = AsyncMock(
        return_value=[{"id": song_id, "audio_id_ok": "asset-ok", "audio_id_alt": "asset-alt"}]
    )

    enriched = await service._enrich_studio_assets(document["user_id"], document)

    lanes = enriched["data"]["lanes"]
    assert lanes[0]["sunoAssetId"] == "asset-ok"
    assert lanes[1]["sunoAssetId"] == "asset-alt"
    # No variant means the clip was not seeded from a generation variant.
    assert "sunoAssetId" not in lanes[2]


@pytest.mark.asyncio
async def test_upload_assets_reuse_a_cached_suno_clip_id() -> None:
    service = _service()
    upload_id = uuid4()
    service._pool.fetch = AsyncMock(
        return_value=[
            {
                "id": upload_id,
                "filename": "loop.wav",
                "storage_key": "studio/loop.wav",
                "suno_clip_id": "suno-asset-1",
            }
        ]
    )
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    lanes = [{"id": "clip-1", "uploadId": str(upload_id)}]

    await service._attach_upload_assets(str(uuid4()), lanes)

    assert lanes[0]["sunoAssetId"] == "suno-asset-1"
    # A cached id means no storage read and no import call.
    service._pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_upload_assets_import_once_and_cache_the_result() -> None:
    from unittest.mock import MagicMock, patch

    service = _service()
    upload_id = uuid4()
    service._pool.fetch = AsyncMock(
        return_value=[
            {
                "id": upload_id,
                "filename": "loop.wav",
                "storage_key": "studio/loop.wav",
                "suno_clip_id": None,
            }
        ]
    )
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    lanes = [{"id": "clip-1", "uploadId": str(upload_id)}]

    storage = MagicMock()
    storage.get_signed_get_url = AsyncMock(return_value="https://storage/loop.wav")
    response = MagicMock(status_code=201)
    response.json = MagicMock(return_value={"clip_id": "suno-asset-2"})
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "platform_api.services.streaming_config_service.resolve_streaming_storage_config",
            AsyncMock(return_value=MagicMock(configured=True)),
        ),
        patch(
            "platform_api.services.storage_service.StorageService.from_config",
            return_value=storage,
        ),
        patch("httpx.AsyncClient", return_value=context),
    ):
        await service._attach_upload_assets(str(uuid4()), lanes)

    assert lanes[0]["sunoAssetId"] == "suno-asset-2"
    service._pool.execute.assert_awaited_once()
    assert "UPDATE studio_uploads" in service._pool.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_asset_enrichment_skips_non_uuid_song_ids() -> None:
    service = _service()
    service._pool.fetch = AsyncMock()
    document = {
        "data": {"lanes": [{"id": "clip-1", "songId": "not-a-uuid", "songVariant": "ok"}]}
    }

    enriched = await service._enrich_studio_assets(str(uuid4()), document)

    service._pool.fetch.assert_not_called()
    assert "sunoAssetId" not in enriched["data"]["lanes"][0]


def _project_row() -> dict:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Tracked",
        "major_version": 2,
        "bpm": 120,
        "time_signature": "4/4",
        "data": {"tracks": [], "lanes": []},
        "created_at": None,
        "updated_at": None,
        "pinned": False,
        "archived": False,
        "tags": [],
        "comment_count": 0,
        "last_comment_at": None,
    }


@pytest.mark.asyncio
async def test_load_suno_version_applies_the_merged_document_and_records_it() -> None:
    service = _service()
    row = _project_row()
    merged = {
        "bpm": 90,
        "time_signature": "3/4",
        "data": {"tracks": [{"id": "t1", "clipIds": []}], "lanes": []},
        "kept_local_clips": [],
        "dropped_tracks": [],
        "suno_version_id": "v2",
    }
    service._pool.fetchrow = AsyncMock(side_effect=[row, {**row, "bpm": 90, "time_signature": "3/4"}])
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    service._studio_sync_request = AsyncMock(
        side_effect=[merged, {"status": "synced"}]
    )

    result = await service.load_studio_suno_version(row["user_id"], row["id"])

    assert result["bpm"] == 90
    assert result["time_signature"] == "3/4"
    assert service._studio_sync_request.await_args_list[0].args[2] == "merge"
    resolve_call = service._studio_sync_request.await_args_list[1]
    assert resolve_call.args[2] == "resolve"
    assert resolve_call.args[3]["resolution"] == "theirs"


@pytest.mark.asyncio
async def test_keep_mine_rebases_then_pushes() -> None:
    service = _service()
    row = _project_row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    mirrored = {**PENDING, "status": "synced", "suno_remote_version_id": "v2"}
    service._studio_sync_request = AsyncMock(
        side_effect=[
            {**PENDING, "suno_remote_version_id": "v2"},
            {**PENDING, "status": "linked"},
            mirrored,
        ]
    )

    result = await service.keep_studio_local_version(row["user_id"], row["id"])

    assert result["status"] == "synced"
    actions = [call.args[2] for call in service._studio_sync_request.await_args_list]
    assert actions == ["refresh", "resolve", "sync"]
    resolve_call = service._studio_sync_request.await_args_list[1]
    assert resolve_call.args[3]["resolution"] == "mine"
    assert resolve_call.args[3]["version"] == "v2"
