"""Unit tests for JobQueueRepository claim / complete / retry semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from platform_api.repositories.job_queue_repo import JobQueueItem, JobQueueRepository


class _FakeConn:
    def __init__(self, row=None) -> None:
        self.row = row
        self.execute_sql: list[str] = []

    async def fetchrow(self, sql: str, *args):
        self.execute_sql.append(sql)
        return self.row

    async def execute(self, sql: str, *args):
        self.execute_sql.append(sql)
        return "UPDATE 1"

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)

    async def fetchrow(self, sql: str, *args):
        return await self._conn.fetchrow(sql, *args)

    async def execute(self, sql: str, *args):
        return await self._conn.execute(sql, *args)


def _job(*, attempts: int = 1, max_attempts: int = 5) -> JobQueueItem:
    now = datetime.now(timezone.utc)
    return JobQueueItem(
        id=uuid4(),
        user_id=uuid4(),
        batch_id=uuid4(),
        song_id=None,
        job_type="execute_batch",
        provider=None,
        status="running",
        priority=10,
        run_after=now,
        attempts=attempts,
        max_attempts=max_attempts,
        payload={"batch_id": "x"},
        last_error=None,
        locked_by="worker-1",
        locked_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_claim_next_returns_none_when_empty() -> None:
    conn = _FakeConn(row=None)
    repo = JobQueueRepository(_FakePool(conn))  # type: ignore[arg-type]
    assert await repo.claim_next(worker_id="w1") is None


@pytest.mark.asyncio
async def test_claim_next_passes_job_type_filter() -> None:
    conn = _FakeConn(row=None)
    repo = JobQueueRepository(_FakePool(conn))  # type: ignore[arg-type]
    await repo.claim_next(worker_id="w1", job_types=["draft", "execute_batch"])
    sql = conn.execute_sql[0]
    assert "job_type = ANY" in sql
    assert "$2::text[]" in sql


@pytest.mark.asyncio
async def test_mark_failed_retries_until_max() -> None:
    conn = _FakeConn()
    repo = JobQueueRepository(_FakePool(conn))  # type: ignore[arg-type]
    status = await repo.mark_failed_or_retry(_job(attempts=2, max_attempts=5), error="boom")
    assert status == "delayed"
    status = await repo.mark_failed_or_retry(_job(attempts=5, max_attempts=5), error="boom")
    assert status == "failed"
