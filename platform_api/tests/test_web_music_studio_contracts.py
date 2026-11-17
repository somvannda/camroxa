"""S04 Studio project list/detail contracts: deletion flag, ordering, lifecycle.

These pin the SQL/parameter shape the web client depends on: the list hides
soft-deleted rows by default, the "Recently Deleted" tab flips one flag, and a
delete can always be undone until the row is restored.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.services.web_music_service import WebMusicService


def _service() -> WebMusicService:
    return WebMusicService(AsyncMock(), AsyncMock(), redis=None)


def _row(**overrides):
    row = {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Project",
        "major_version": 2,
        "bpm": 120,
        "time_signature": "4/4",
        "data": {"tracks": [], "lanes": []},
        "created_at": None,
        "updated_at": None,
        "deleted_at": None,
        "pinned": False,
        "archived": False,
        "tags": [],
        "comment_count": 0,
        "last_comment_at": None,
    }
    row.update(overrides)
    return row


def _stub_list_pool(service: WebMusicService, rows: list[dict], total: int = 0) -> None:
    service._pool.fetch = AsyncMock(return_value=rows)
    service._pool.fetchval = AsyncMock(return_value=total)
    service._studio_batch_sync_statuses = AsyncMock(return_value={})


# --- list_studio_projects -------------------------------------------------


@pytest.mark.asyncio
async def test_list_defaults_to_hiding_soft_deleted_rows() -> None:
    service = _service()
    _stub_list_pool(service, [], total=0)
    user_id = uuid4()

    result = await service.list_studio_projects(user_id)

    sql = service._pool.fetch.await_args.args[0]
    assert "FROM studio_projects p" in sql
    assert "NOT $5::boolean AND p.deleted_at IS NULL" in sql
    count_sql = service._pool.fetchval.await_args.args[0]
    assert "NOT $3::boolean AND deleted_at IS NULL" in count_sql
    # user_id, limit, offset, include_archived, deleted
    assert service._pool.fetch.await_args.args[1:] == (user_id, 40, 0, False, False)
    assert service._pool.fetchval.await_args.args[1:] == (user_id, False, False)
    assert result == {"items": [], "total": 0, "limit": 40, "offset": 0}


@pytest.mark.asyncio
async def test_list_deleted_tab_filters_the_other_way() -> None:
    service = _service()
    _stub_list_pool(service, [], total=0)
    user_id = uuid4()

    result = await service.list_studio_projects(user_id, deleted=True)

    sql = service._pool.fetch.await_args.args[0]
    assert "p.deleted_at IS NOT NULL" in sql
    count_sql = service._pool.fetchval.await_args.args[0]
    assert "deleted_at IS NOT NULL" in count_sql
    # SQL, user_id, limit, offset, include_archived, deleted
    assert service._pool.fetch.await_args.args[5] is True
    # SQL, user_id, include_archived, deleted
    assert service._pool.fetchval.await_args.args[3] is True
    assert result["items"] == []


@pytest.mark.asyncio
async def test_list_passes_paging_and_archive_flags_in_order() -> None:
    service = _service()
    _stub_list_pool(service, [], total=3)
    user_id = uuid4()

    result = await service.list_studio_projects(
        user_id,
        limit=25,
        offset=50,
        include_archived=True,
        deleted=True,
    )

    assert service._pool.fetch.await_args.args[1:] == (user_id, 25, 50, True, True)
    assert service._pool.fetchval.await_args.args[1:] == (user_id, True, True)
    assert result["limit"] == 25
    assert result["offset"] == 50
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_list_clamps_paging_to_the_allowed_window() -> None:
    service = _service()
    _stub_list_pool(service, [], total=0)

    result = await service.list_studio_projects(uuid4(), limit=500, offset=-7)

    assert service._pool.fetch.await_args.args[2:4] == (100, 0)
    assert result["limit"] == 100
    assert result["offset"] == 0


@pytest.mark.asyncio
async def test_list_rows_are_list_items_without_the_heavy_document() -> None:
    service = _service()
    row = _row(title="Card")
    _stub_list_pool(service, [row], total=1)
    service._studio_batch_sync_statuses = AsyncMock(
        return_value={str(row["id"]): "synced"}
    )

    result = await service.list_studio_projects(row["user_id"])

    item = result["items"][0]
    assert item["id"] == str(row["id"])
    assert item["title"] == "Card"
    assert "data" not in item
    assert "thumb" in item
    assert item["sync"] == {"status": "synced"}


# --- get_studio_project ---------------------------------------------------


@pytest.mark.asyncio
async def test_get_hides_soft_deleted_projects() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)
    project_id = uuid4()
    user_id = uuid4()

    with pytest.raises(NotFoundError):
        await service.get_studio_project(user_id, project_id)

    sql = service._pool.fetchrow.await_args.args[0]
    assert "deleted_at IS NULL" in sql
    assert service._pool.fetchrow.await_args.args[1:] == (project_id, user_id)


@pytest.mark.asyncio
async def test_get_returns_the_full_document_for_a_live_project() -> None:
    service = _service()
    data = {"tracks": [{"id": "t1", "clipIds": []}], "lanes": []}
    row = _row(data=data)
    service._pool.fetchrow = AsyncMock(return_value=row)

    result = await service.get_studio_project(row["user_id"], row["id"])

    assert result["data"] == data
    assert "thumb" not in result


# --- delete -> restore lifecycle -----------------------------------------


@pytest.mark.asyncio
async def test_delete_stamps_deleted_at_and_updated_at() -> None:
    service = _service()
    row = _row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: None

    assert await service.delete_studio_project(row["user_id"], row["id"]) is None

    sql = service._pool.fetchrow.await_args.args[0]
    assert "UPDATE studio_projects" in sql
    assert "deleted_at = now()" in sql
    assert "updated_at = now()" in sql
    assert "deleted_at IS NULL" in sql
    assert "DELETE FROM" not in sql
    assert service._pool.fetchrow.await_args.args[1:] == (row["id"], row["user_id"])


@pytest.mark.asyncio
async def test_delete_archives_the_suno_copy_without_blocking() -> None:
    service = _service()
    row = _row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    service._studio_sync_endpoint = lambda: ("http://mirror", "token")
    scheduled: list[tuple] = []
    service._schedule_studio_request = lambda *args: scheduled.append(args)

    await service.delete_studio_project(row["user_id"], row["id"])

    assert scheduled == [
        (
            str(row["user_id"]),
            str(row["id"]),
            "archive",
            {"user_id": str(row["user_id"]), "archived": True},
        )
    ]


@pytest.mark.asyncio
async def test_restore_clears_deleted_at_and_returns_a_card() -> None:
    service = _service()
    row = _row()
    service._pool.fetchrow = AsyncMock(return_value=row)
    project_id = uuid4()
    user_id = uuid4()

    result = await service.restore_studio_project(user_id, project_id)

    sql = service._pool.fetchrow.await_args.args[0]
    assert "deleted_at = NULL" in sql
    assert "updated_at = now()" in sql
    assert "deleted_at IS NOT NULL" in sql
    assert service._pool.fetchrow.await_args.args[1:] == (project_id, user_id)
    assert result["id"] == str(row["id"])
    assert "data" not in result
    assert "thumb" in result


@pytest.mark.asyncio
async def test_restore_rejects_a_project_that_was_never_deleted() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.restore_studio_project(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_delete_then_restore_round_trips_the_same_row() -> None:
    service = _service()
    row = _row(title="Round trip")
    service._pool.fetchrow = AsyncMock(side_effect=[row, row])
    service._studio_sync_endpoint = lambda: None
    user_id = row["user_id"]

    await service.delete_studio_project(user_id, row["id"])
    restored = await service.restore_studio_project(user_id, row["id"])

    statements = [call.args[0] for call in service._pool.fetchrow.await_args_list]
    assert "deleted_at = now()" in statements[0]
    assert "deleted_at = NULL" in statements[1]
    assert restored["id"] == str(row["id"])
    assert restored["title"] == "Round trip"


# --- payload --------------------------------------------------------------


def test_payload_reports_a_null_deleted_at_for_live_rows() -> None:
    payload = WebMusicService._studio_project_payload(_row(), include_data=False)
    assert payload["deleted_at"] is None


def test_payload_serialises_deleted_at_for_the_deleted_tab() -> None:
    deleted_at = datetime(2026, 11, 14, 9, 30, tzinfo=timezone.utc)
    payload = WebMusicService._studio_project_payload(
        _row(deleted_at=deleted_at), include_data=False
    )
    assert payload["deleted_at"] == deleted_at.isoformat()


# --- studio_project_for_song ---------------------------------------------


@pytest.mark.asyncio
async def test_for_song_ignores_deleted_projects() -> None:
    service = _service()
    project_id = uuid4()
    service._pool.fetchrow = AsyncMock(return_value={"id": project_id})
    user_id = uuid4()

    result = await service.studio_project_for_song(user_id, " song-1 ")

    sql = service._pool.fetchrow.await_args.args[0]
    assert "deleted_at IS NULL" in sql
    assert "jsonb_array_elements(data->'lanes')" in sql
    assert "ORDER BY updated_at DESC" in sql
    assert service._pool.fetchrow.await_args.args[1:] == (user_id, "song-1")
    assert result == {"id": str(project_id)}


@pytest.mark.asyncio
async def test_for_song_returns_none_when_no_project_holds_it() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock(return_value=None)

    assert await service.studio_project_for_song(uuid4(), "song-1") == {"id": None}


@pytest.mark.asyncio
async def test_for_song_requires_an_id() -> None:
    service = _service()
    service._pool.fetchrow = AsyncMock()

    with pytest.raises(ValidationError):
        await service.studio_project_for_song(uuid4(), "   ")

    service._pool.fetchrow.assert_not_called()


# --- refresh must not re-arm the mirror on every poll ---------------------


@pytest.mark.asyncio
async def test_refresh_does_not_enqueue_an_unlinked_project() -> None:
    """QA follow-up: an editor polling refresh used to trigger a 90 s enqueue each time."""
    service = _service()
    project = _row()
    service._pool.fetchrow = AsyncMock(return_value=project)
    service._studio_sync_request = AsyncMock(
        return_value={
            "status": "pending",
            "suno_project_id": None,
            "suno_version_id": None,
            "last_error": None,
            "synced_at": None,
            "skipped_clips": [],
            "state_sync": False,
        }
    )

    view = await service.refresh_studio_project(project["user_id"], project["id"])

    assert view["status"] == "pending"
    service._studio_sync_request.assert_awaited_once()
    assert service._studio_sync_request.await_args.args[2] == "refresh"
