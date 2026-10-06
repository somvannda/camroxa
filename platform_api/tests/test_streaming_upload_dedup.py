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
