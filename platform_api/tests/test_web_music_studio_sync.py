"""Suno Studio mirror status/refresh proxies: ownership first, then the mirror."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
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
    row = _project_row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_request = AsyncMock(
        return_value={**PENDING, "status": "conflict", "suno_project_id": "suno-1"}
    )

    result = await service.refresh_studio_project(row["user_id"], row["id"])

    assert result["status"] == "conflict"
    service._studio_sync_request.assert_awaited_once()
    assert service._studio_sync_request.await_args.args[2] == "refresh"


@pytest.mark.asyncio
async def test_refresh_rearms_a_mirror_that_never_reached_musicapi() -> None:
    service = _service()
    row = _project_row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    service._studio_sync_request = AsyncMock(
        side_effect=[
            {**PENDING, "status": "pending", "suno_project_id": None},
            {"status": "queued"},
            {**PENDING, "status": "synced", "suno_project_id": "suno-2"},
        ]
    )

    result = await service.refresh_studio_project(row["user_id"], row["id"])

    assert result["status"] == "synced"
    actions = [call.args[2] for call in service._studio_sync_request.await_args_list]
    assert actions == ["refresh", "enqueue", "refresh"]


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
async def test_list_attaches_the_mirror_status_to_each_project() -> None:
    service = _service()
    row = _project_row()
    service._pool.fetch = AsyncMock(return_value=[row])
    service._pool.fetchval = AsyncMock(return_value=1)
    service._studio_batch_sync_statuses = AsyncMock(
        return_value={str(row["id"]): "synced"}
    )

    result = await service.list_studio_projects(row["user_id"])

    assert result["items"][0]["sync"] == {"status": "synced"}


@pytest.mark.asyncio
async def test_list_renders_when_the_mirror_is_unreachable() -> None:
    service = _service()
    row = _project_row()
    service._pool.fetch = AsyncMock(return_value=[row])
    service._pool.fetchval = AsyncMock(return_value=1)
    service._studio_batch_sync_statuses = AsyncMock(return_value={})

    result = await service.list_studio_projects(row["user_id"])

    assert "sync" not in result["items"][0]


@pytest.mark.asyncio
async def test_backfill_queues_only_projects_without_a_link() -> None:
    service = _service()
    first = _project_row()
    second = _project_row()
    second["user_id"] = first["user_id"]
    service._pool.fetch = AsyncMock(return_value=[first, second])
    service._studio_batch_sync_statuses = AsyncMock(
        return_value={str(first["id"]): "synced"}
    )
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    service.queue_studio_mirror = MagicMock()

    result = await service.backfill_studio_mirror(20)

    assert result == {"scanned": 2, "queued": 1}
    service.queue_studio_mirror.assert_called_once_with(second)


@pytest.mark.asyncio
async def test_backfill_is_a_noop_without_a_configured_mirror() -> None:
    service = _service()
    service._studio_sync_endpoint = lambda: None
    service._pool.fetch = AsyncMock()

    result = await service.backfill_studio_mirror(20)

    assert result == {"scanned": 0, "queued": 0}
    service._pool.fetch.assert_not_called()


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


@pytest.mark.asyncio
async def test_author_studio_plugin_forwards_the_instruction_and_job() -> None:
    service = _service()
    row = _project_row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    service._studio_sync_request = AsyncMock(
        return_value={"job_id": "job-1", "status": "pending"}
    )

    result = await service.author_studio_plugin(
        row["user_id"],
        row["id"],
        instruction="  warm tape saturation with a low cut  ",
        required_controls=["Drive", "Low Cut"],
    )

    assert result["job_id"] == "job-1"
    call = service._studio_sync_request.await_args
    assert call.args[2] == "plugins/author"
    assert call.args[3]["instruction"] == "warm tape saturation with a low cut"
    assert call.args[3]["required_controls"] == ["Drive", "Low Cut"]


@pytest.mark.asyncio
async def test_author_studio_plugin_fails_when_the_agent_returns_no_job() -> None:
    from platform_api.exceptions import ExternalServiceError

    service = _service()
    row = _project_row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    service._studio_sync_request = AsyncMock(return_value=None)

    with pytest.raises(ExternalServiceError):
        await service.author_studio_plugin(row["user_id"], row["id"], instruction="build it")


@pytest.mark.asyncio
async def test_studio_project_for_song_returns_the_existing_project() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value={"id": "project-1"})

    result = await service.studio_project_for_song(uuid4(), "song-1")

    assert result == {"id": "project-1"}
    sql = service._pool.fetchrow.await_args.args[0]
    assert "jsonb_array_elements" in sql
    assert service._pool.fetchrow.await_args.args[2] == "song-1"


@pytest.mark.asyncio
async def test_studio_project_for_song_returns_null_when_none_exists() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    assert await service.studio_project_for_song(uuid4(), "song-1") == {"id": None}


@pytest.mark.asyncio
async def test_plugin_authoring_job_reads_the_mirror() -> None:
    service = _service()
    project_id = uuid4()
    service._pool.fetchrow = AsyncMock(return_value={"id": project_id})
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    view = {"job_id": "job-1", "status": "ready", "plugin_id": "p1"}
    service._studio_sync_request = AsyncMock(return_value=view)

    result = await service.studio_plugin_authoring_job(uuid4(), project_id, "job-1")

    assert result == view
    call = service._studio_sync_request.await_args
    assert call.args[2] == "plugins/author/job"
    assert call.args[3]["job_id"] == "job-1"
