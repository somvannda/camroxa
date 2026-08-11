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

    async def fetch(self, sql: str, *args):
        return []

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


class _ListPool:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.last_sql = ""
        self.last_args: tuple = ()

    async def fetch(self, sql: str, *args):
        self.last_sql = sql
        self.last_args = args
        return self.rows


@pytest.mark.asyncio
async def test_list_admin_jobs_filters_and_maps_stage() -> None:
    from platform_api.services.job_types import stage_for_job_type

    now = datetime.now(timezone.utc)
    uid = uuid4()
    bid = uuid4()
    jid = uuid4()
    pool = _ListPool(
        [
            {
                "id": jid,
                "user_id": uid,
                "user_email": "ops@camxora.com",
                "batch_id": bid,
                "song_id": None,
                "job_type": "run_image_jobs",
                "provider": "slai",
                "status": "failed",
                "priority": 12,
                "attempts": 3,
                "max_attempts": 5,
                "last_error": "SLAI error 500: generate_image",
                "locked_by": None,
                "locked_at": None,
                "run_after": now,
                "created_at": now,
                "updated_at": now,
                "age_seconds": 42.0,
            }
        ]
    )
    repo = JobQueueRepository(pool)  # type: ignore[arg-type]
    rows = await repo.list_admin_jobs(status="failed", user="ops", limit=10)
    assert len(rows) == 1
    assert rows[0]["user_email"] == "ops@camxora.com"
    assert rows[0]["stage"] == "images"
    assert rows[0]["stage"] == stage_for_job_type("run_image_jobs")
    assert "j.status = $1" in pool.last_sql
    assert pool.last_args[0] == "failed"
    assert "%ops%" in pool.last_args


@pytest.mark.asyncio
async def test_list_admin_jobs_rejects_bad_status() -> None:
    repo = JobQueueRepository(_ListPool([]))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Unsupported status"):
        await repo.list_admin_jobs(status="done")


@pytest.mark.asyncio
async def test_get_metrics_enriches_busy_workers() -> None:
    now = datetime.now(timezone.utc)

    class _MetricsPool:
        async def fetch(self, sql: str, *args):
            if "GROUP BY status" in sql and "job_type" not in sql:
                return [{"status": "running", "count": 1}, {"status": "failed", "count": 2}]
            if "GROUP BY job_type, status" in sql:
                return [{"job_type": "draft", "status": "running", "count": 1}]
            if "j.status = 'running'" in sql:
                return [
                    {
                        "locked_by": "host:images@1:99",
                        "job_type": "run_image_jobs",
                        "user_email": "a@x.com",
                    }
                ]
            return []

        async def fetchrow(self, sql: str, *args):
            return {
                "id": uuid4(),
                "job_type": "draft",
                "created_at": now,
                "run_after": now,
                "age_seconds": 10.0,
            }

    repo = JobQueueRepository(_MetricsPool())  # type: ignore[arg-type]
    metrics = await repo.get_metrics()
    assert metrics["failed"] == 2
    assert metrics["running"] == 1
    assert metrics["workers_busy"][0]["worker_id"] == "host:images@1:99"
    assert metrics["workers_busy"][0]["job_types"] == ["run_image_jobs"]
    assert metrics["workers_busy"][0]["user_emails"] == ["a@x.com"]
    assert metrics["workers_busy"][0]["stages"] == ["images"]
