"""Automatic Studio project versions (§25): throttled snapshots, bounded history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from platform_api.services.web_music_service import AUTO_VERSION_MIN_SECONDS, WebMusicService

USER_ID = uuid4()
PROJECT_ID = uuid4()
VERSION_ID = uuid4()
NOW = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)


def _project_row() -> dict:
    return {
        "id": PROJECT_ID,
        "user_id": USER_ID,
        "title": "Demo",
        "bpm": 120,
        "time_signature": "4/4",
        "data": {"lanes": []},
    }


def _version_row(created_at: datetime, version_id: UUID = VERSION_ID) -> dict:
    return {
        "id": version_id,
        "project_id": PROJECT_ID,
        "label": None,
        "title": "Demo",
        "bpm": 120,
        "time_signature": "4/4",
        "created_at": created_at,
        "data": {"lanes": []},
    }


class RecordingPool:
    """Routes the three queries the version writer makes; records everything."""

    def __init__(self, *, newest: dict | None, inserted: dict | None = None) -> None:
        self.newest = newest
        self.inserted = inserted or _version_row(datetime.now(timezone.utc))
        self.queries: list[str] = []

    @staticmethod
    def _sql(query: str) -> str:
        return " ".join(query.split())

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        sql = self._sql(query)
        self.queries.append(sql)
        if sql.startswith("SELECT * FROM studio_projects"):
            return _project_row()
        if sql.startswith("SELECT * FROM studio_project_versions"):
            return self.newest
        if sql.startswith("INSERT INTO studio_project_versions"):
            return self.inserted
        raise AssertionError(f"unexpected fetchrow: {sql}")

    async def execute(self, query: str, *args: object) -> str:
        self.queries.append(self._sql(query))
        return "OK"


def _service(pool: RecordingPool) -> WebMusicService:
    service = WebMusicService(pool, AsyncMock())  # type: ignore[arg-type]
    return service


def _wrote_version(pool: RecordingPool) -> bool:
    return any(query.startswith("INSERT INTO studio_project_versions") for query in pool.queries)


@pytest.mark.asyncio
async def test_auto_snapshot_is_skipped_inside_the_throttle_window() -> None:
    recent = _version_row(datetime.now(timezone.utc) - timedelta(seconds=AUTO_VERSION_MIN_SECONDS / 2))
    pool = RecordingPool(newest=recent)

    payload = await _service(pool).create_studio_project_version(
        USER_ID, PROJECT_ID, auto=True
    )

    assert payload["id"] == str(VERSION_ID)
    assert not _wrote_version(pool), "a second snapshot inside the window must not be written"


@pytest.mark.asyncio
async def test_auto_snapshot_writes_once_the_window_has_passed() -> None:
    old = _version_row(datetime.now(timezone.utc) - timedelta(seconds=AUTO_VERSION_MIN_SECONDS + 5))
    pool = RecordingPool(newest=old)

    await _service(pool).create_studio_project_version(USER_ID, PROJECT_ID, auto=True)

    assert _wrote_version(pool)
    # The history is bounded: the insert is followed by the prune to the newest 50.
    assert any(query.startswith("DELETE FROM studio_project_versions") for query in pool.queries)


@pytest.mark.asyncio
async def test_auto_snapshot_writes_when_no_version_exists_yet() -> None:
    pool = RecordingPool(newest=None)

    await _service(pool).create_studio_project_version(USER_ID, PROJECT_ID, auto=True)

    assert _wrote_version(pool)


@pytest.mark.asyncio
async def test_manual_versions_are_never_throttled() -> None:
    recent = _version_row(datetime.now(timezone.utc))
    pool = RecordingPool(newest=recent)

    await _service(pool).create_studio_project_version(USER_ID, PROJECT_ID, label="Before the drop")

    assert _wrote_version(pool), "an explicit save must not be swallowed by the throttle"
