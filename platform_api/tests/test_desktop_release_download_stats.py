from __future__ import annotations

import json

import pytest

from platform_api.services.desktop_release_download_stats import (
    DESKTOP_DOWNLOAD_COUNTS_KEY,
    get_download_count_for_version,
    get_total_downloads,
    increment_download_for_filename,
)


class _FakePool:
    def __init__(self) -> None:
        self.settings: dict[str, str] = {}
        self.executed: list[tuple] = []

    async def fetchrow(self, query: str, key: str):
        value = self.settings.get(key)
        if value is None:
            return None
        return {"value": value}

    async def execute(self, query: str, *args):
        self.executed.append((query, args))
        if "INSERT INTO system_settings" in query and len(args) >= 2:
            self.settings[str(args[0])] = str(args[1])


@pytest.mark.asyncio
async def test_increment_download_for_filename_tracks_by_version() -> None:
    pool = _FakePool()
    version, count = await increment_download_for_filename(pool, "Camxora-0.2.4.exe")
    assert version == "0.2.4"
    assert count == 1

    version, count = await increment_download_for_filename(pool, "Camxora-0.2.4.exe")
    assert count == 2

    assert await get_download_count_for_version(pool, "0.2.4") == 2
    assert await get_total_downloads(pool) == 2


@pytest.mark.asyncio
async def test_versions_are_independent() -> None:
    pool = _FakePool()
    await increment_download_for_filename(pool, "Camxora-0.2.3.exe")
    await increment_download_for_filename(pool, "Camxora-0.2.4.exe")
    await increment_download_for_filename(pool, "Camxora-0.2.4.exe")

    assert await get_download_count_for_version(pool, "0.2.3") == 1
    assert await get_download_count_for_version(pool, "0.2.4") == 2
    assert await get_total_downloads(pool) == 3


@pytest.mark.asyncio
async def test_persists_json_blob() -> None:
    pool = _FakePool()
    await increment_download_for_filename(pool, "Camxora-1.0.0.zip")
    stored = json.loads(pool.settings[DESKTOP_DOWNLOAD_COUNTS_KEY])
    assert stored == {"1.0.0": 1}
