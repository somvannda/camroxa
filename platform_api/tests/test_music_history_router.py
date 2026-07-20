from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from unittest.mock import AsyncMock

import pytest

from platform_api.middleware.auth import AuthContext
from platform_api.routers import music_history


class FakeMusicHistoryPool:
    def __init__(self) -> None:
        self._batch_fetch_calls = 0
        self._song_fetch_calls = 0

    async def fetch(self, query: str, *args):
        if "FROM batches b" in query:
            self._batch_fetch_calls += 1
            if self._batch_fetch_calls == 1:
                raise RuntimeError('column "planned_from_date" does not exist')
            return [
                {
                    "id": UUID("00000000-0000-0000-0000-000000000100"),
                    "status": "pending",
                    "song_count": 2,
                    "planned_from_date": date(2026, 6, 25),
                    "planned_to_date": date(2026, 6, 25),
                    "created_at": datetime(2026, 6, 25, 10, 0, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 6, 25, 10, 5, tzinfo=timezone.utc),
                    "ok_profile_id": UUID("00000000-0000-0000-0000-000000000200"),
                    "alt_profile_id": UUID("00000000-0000-0000-0000-000000000201"),
                    "ok_profile_name": "OK Channel",
                    "alt_profile_name": "ALT Channel",
                    "ok_run_dir": r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
                    "alt_run_dir": r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
                    "ok_profile_folder": "bass-drive",
                    "alt_profile_folder": "beattok-remixes",
                }
            ]

        if "FROM songs s" in query:
            self._song_fetch_calls += 1
            if self._song_fetch_calls == 1:
                raise RuntimeError('column "output_dir_ok" does not exist')
            return [
                {
                    "song_id": UUID("00000000-0000-0000-0000-000000000300"),
                    "batch_id": UUID("00000000-0000-0000-0000-000000000100"),
                    "batch_index": 0,
                    "title": "Test Song",
                    "album": "Test Album",
                    "lyrics": "[Verse]\nTest lyric line",
                    "description_id": UUID("00000000-0000-0000-0000-000000000400"),
                    "description_name": "Cinematic Pop",
                    "structure_id": UUID("00000000-0000-0000-0000-000000000401"),
                    "structure_name": "Verse Chorus Bridge",
                    "output_dir_ok": r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
                    "output_dir_alt": r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
                    "status": "draft_ready",
                    "created_at": datetime(2026, 6, 25, 10, 1, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 6, 25, 10, 2, tzinfo=timezone.utc),
                    "suno_status": "success",
                    "downloaded_ok": True,
                    "downloaded_alt": False,
                    "youtube_status": None,
                }
            ]

        if "FROM image_jobs" in query:
            return [
                {
                    "song_id": UUID("00000000-0000-0000-0000-000000000300"),
                    "total": 2,
                    "completed": 1,
                }
            ]

        return []


@pytest.mark.asyncio
async def test_music_history_falls_back_when_date_columns_or_history_columns_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(music_history, "get_db_pool", lambda: FakeMusicHistoryPool())
    batch_service = AsyncMock()
    batch_service.reconcile_pending_suno_tasks = AsyncMock(return_value=0)

    result = await music_history.list_music_history(
        batch_service,
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        ),
        limit=8,
    )

    batch_service.reconcile_pending_suno_tasks.assert_awaited_once()

    assert len(result.batches) == 1
    assert result.batches[0].planned_days == 1
    assert result.batches[0].from_date == date(2026, 6, 25)
    assert len(result.batches[0].songs) == 1
    assert result.batches[0].songs[0].image_jobs_total == 2
    assert result.batches[0].songs[0].youtube_status is None
    assert result.batches[0].songs[0].description_name == "Cinematic Pop"
    assert result.batches[0].songs[0].structure_name == "Verse Chorus Bridge"
    assert result.batches[0].songs[0].lyrics == "[Verse]\nTest lyric line"
    assert result.batches[0].songs[0].output_dir_ok == r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02"
    assert (
        result.batches[0].songs[0].output_dir_alt
        == r"D:\MusicGenerator\downloads\suno\beattok-remixes\2026-07-12_02"
    )


def test_parse_query_date_accepts_iso_and_rejects_junk() -> None:
    assert music_history._parse_query_date("2026-07-20") == date(2026, 7, 20)
    assert music_history._parse_query_date("2026-07-20T15:00:00Z") == date(2026, 7, 20)
    assert music_history._parse_query_date("") is None
    assert music_history._parse_query_date(None) is None
    assert music_history._parse_query_date("not-a-date") is None


@pytest.mark.asyncio
async def test_music_history_accepts_string_date_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: asyncpg needs date objects, not bare yyyy-MM-dd strings."""
    pool = FakeMusicHistoryPool()
    monkeypatch.setattr(music_history, "get_db_pool", lambda: pool)
    batch_service = AsyncMock()
    batch_service.reconcile_pending_suno_tasks = AsyncMock(return_value=0)

    # Force primary query path (no schema drift) by making first fetch succeed.
    original_fetch = pool.fetch

    async def fetch_ok(query: str, *args):
        # Skip the intentional first-failure behavior for this regression.
        if "FROM batches b" in query:
            pool._batch_fetch_calls += 1
            # Validate date args are date|None for asyncpg.
            assert args[2] is None or isinstance(args[2], date)
            assert args[3] is None or isinstance(args[3], date)
            return [
                {
                    "id": UUID("00000000-0000-0000-0000-000000000100"),
                    "status": "pending",
                    "song_count": 2,
                    "planned_from_date": date(2026, 6, 25),
                    "planned_to_date": date(2026, 6, 25),
                    "created_at": datetime(2026, 6, 25, 10, 0, tzinfo=timezone.utc),
                    "updated_at": datetime(2026, 6, 25, 10, 5, tzinfo=timezone.utc),
                    "ok_profile_id": UUID("00000000-0000-0000-0000-000000000200"),
                    "alt_profile_id": UUID("00000000-0000-0000-0000-000000000201"),
                    "ok_profile_name": "OK Channel",
                    "alt_profile_name": "ALT Channel",
                    "ok_run_dir": r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
                    "alt_run_dir": r"D:\MusicGenerator\downloads\suno\bass-drive\2026-07-12_02",
                    "ok_profile_folder": "bass-drive",
                    "alt_profile_folder": "beattok-remixes",
                    "ok_album": "A1",
                    "alt_album": "A2",
                }
            ]
        return await original_fetch(query, *args)

    pool.fetch = fetch_ok  # type: ignore[method-assign]

    result = await music_history.list_music_history(
        batch_service,
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        ),
        limit=8,
        from_date="2026-06-25",
        to_date="2026-06-25",
    )
    assert len(result.batches) == 1
