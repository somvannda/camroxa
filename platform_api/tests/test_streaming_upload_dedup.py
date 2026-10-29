"""Tests for streaming upload-job dedup and missing-B2 health filtering."""

from __future__ import annotations

from uuid import uuid4

from platform_api.repositories.streaming_repo import StreamingRepository


class _FakePool:
    def __init__(self, row):
        self._row = row
        self.calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self._row

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return []


async def test_has_active_upload_job_true_when_pending_row() -> None:
    pool = _FakePool({"1": 1})
    repo = StreamingRepository(pool)
    task_id = uuid4()

    assert await repo.has_active_upload_job(suno_task_id=task_id, kind="mp3_ok") is True

    query, args = pool.calls[0]
    assert "stream_upload_jobs" in query
    assert "status = 'pending'" in query
    assert args == (task_id, "mp3_ok", 30)


async def test_has_active_upload_job_false_when_no_row() -> None:
    pool = _FakePool(None)
    repo = StreamingRepository(pool)

    assert await repo.has_active_upload_job(suno_task_id=uuid4(), kind="mp3_alt") is False


async def test_count_failed_mp3_jobs_missing_b2_excludes_archived() -> None:
    pool = _FakePool({"n": 2})
    repo = StreamingRepository(pool)

    assert await repo.count_failed_mp3_jobs(missing_b2_only=True) == 2

    query, _ = pool.calls[0]
    assert "NOT EXISTS" in query
    assert "stream_tracks" in query


async def test_count_failed_mp3_jobs_without_filter_counts_all() -> None:
    pool = _FakePool({"n": 5})
    repo = StreamingRepository(pool)

    assert await repo.count_failed_mp3_jobs() == 5

    query, _ = pool.calls[0]
    assert "NOT EXISTS" not in query


async def test_count_failed_mp3_jobs_missing_b2_excludes_permanent_failed() -> None:
    pool = _FakePool({"n": 0})
    repo = StreamingRepository(pool)

    assert await repo.count_failed_mp3_jobs(missing_b2_only=True) == 0

    query, _ = pool.calls[0]
    assert "NOT EXISTS" in query
    assert "permanent_failed" in query


async def test_count_failed_mp3_jobs_without_filter_keeps_permanent_failed() -> None:
    pool = _FakePool({"n": 5})
    repo = StreamingRepository(pool)

    assert await repo.count_failed_mp3_jobs() == 5

    query, _ = pool.calls[0]
    assert "permanent_failed" not in query


async def test_count_failed_mp3_jobs_since_missing_b2_excludes_permanent_failed() -> None:
    pool = _FakePool({"n": 0})
    repo = StreamingRepository(pool)

    assert await repo.count_failed_mp3_jobs_since(hours=24, missing_b2_only=True) == 0

    query, _ = pool.calls[0]
    assert "NOT EXISTS" in query
    assert "permanent_failed" in query


async def test_list_recent_failed_mp3_errors_missing_b2_excludes_permanent_failed() -> None:
    pool = _FakePool({"n": 0})
    repo = StreamingRepository(pool)

    assert await repo.list_recent_failed_mp3_errors(limit=5, missing_b2_only=True) == []

    query, _ = pool.calls[0]
    assert "NOT EXISTS" in query
    assert "permanent_failed" in query


async def test_count_web_music_missing_assets_ignores_lazy_wav() -> None:
    """WAV is built on demand since 2026-10-28 and never written back to B2.

    A missing `b2_wav_storage_key_*` is therefore the normal state for every
    new web-music track, not a capture failure: counting it paged ops with a
    "missing assets" number that only tracked generation volume (production
    2026-10-29: 122). Only package and LRC gaps are actionable.
    """
    pool = _FakePool({"n": 0})
    repo = StreamingRepository(pool)

    assert await repo.count_web_music_missing_assets(max_age_hours=24) == 0

    query, args = pool.calls[0]
    assert "package_status_ok, 'none') <> 'ready'" in query
    assert "b2_lrc_storage_key_ok" in query
    assert "b2_wav_storage_key" not in query
    assert "wav_status" not in query
    assert args == (24,)


async def test_list_web_music_asset_tasks_skips_wav_only_backlog() -> None:
    """The recovery pass no longer recovers WAV, so it must not select it.

    Otherwise WAV-only tasks consume the per-pass task budget forever and
    starve the LRC/package gaps that can actually be fixed.
    """
    pool = _FakePool({"n": 0})
    repo = StreamingRepository(pool)

    await repo.list_web_music_asset_tasks(limit=8)

    query, _ = pool.calls[0]
    assert "package_status_ok, 'none') <> 'ready'" in query
    assert "b2_lrc_storage_key_ok, '') = ''" in query
    # The WHERE predicate must not test a WAV column (the SELECT list may still
    # carry them for the worker's row shape).
    where_clause = query.split("WHERE", 1)[1]
    assert "b2_wav_storage_key" not in where_clause
    assert "wav_status" not in where_clause


class _InsertPool:
    """Minimal pool double for create_upload_job."""

    def __init__(self, *, raise_on_insert: bool, existing_id=None) -> None:
        self._raise = raise_on_insert
        self._existing = {"id": existing_id} if existing_id is not None else None
        self.inserted_id = None

    async def execute(self, query, *args):
        self.inserted_id = args[0]
        if self._raise:
            raise RuntimeError("duplicate key value violates unique constraint")

    async def fetchrow(self, query, *args):
        return self._existing


async def test_create_upload_job_returns_new_id_on_success() -> None:
    pool = _InsertPool(raise_on_insert=False)
    repo = StreamingRepository(pool)
    task_id = uuid4()

    job_id = await repo.create_upload_job(
        user_id=uuid4(), kind="mp3_ok", suno_task_id=task_id
    )

    assert job_id == pool.inserted_id


async def test_create_upload_job_reuses_pending_on_unique_violation() -> None:
    existing = uuid4()
    pool = _InsertPool(raise_on_insert=True, existing_id=existing)
    repo = StreamingRepository(pool)

    job_id = await repo.create_upload_job(
        user_id=uuid4(), kind="mp3_ok", suno_task_id=uuid4()
    )

    assert job_id == existing


async def test_create_upload_job_reraises_when_no_pending_winner() -> None:
    pool = _InsertPool(raise_on_insert=True, existing_id=None)
    repo = StreamingRepository(pool)

    try:
        await repo.create_upload_job(
            user_id=uuid4(), kind="mp3_ok", suno_task_id=uuid4()
        )
    except RuntimeError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("expected the insert failure to propagate")

