"""Postgres-backed durable job queue (claim via FOR UPDATE SKIP LOCKED)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg


@dataclass(frozen=True, slots=True)
class JobQueueItem:
    id: UUID
    user_id: UUID
    batch_id: UUID | None
    song_id: UUID | None
    job_type: str
    provider: str | None
    status: str
    priority: int
    run_after: datetime
    attempts: int
    max_attempts: int
    payload: dict[str, Any]
    last_error: str | None
    locked_by: str | None
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _row_to_job(row: asyncpg.Record) -> JobQueueItem:
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    elif payload is None:
        payload = {}
    return JobQueueItem(
        id=row["id"],
        user_id=row["user_id"],
        batch_id=row["batch_id"],
        song_id=row["song_id"],
        job_type=str(row["job_type"]),
        provider=row["provider"],
        status=str(row["status"]),
        priority=int(row["priority"] or 0),
        run_after=row["run_after"],
        attempts=int(row["attempts"] or 0),
        max_attempts=int(row["max_attempts"] or 5),
        payload=dict(payload),
        last_error=row["last_error"],
        locked_by=row["locked_by"],
        locked_at=row["locked_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class JobQueueRepository:
    """Enqueue and claim durable background jobs."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def enqueue(
        self,
        *,
        user_id: UUID,
        job_type: str,
        payload: dict[str, Any],
        batch_id: UUID | None = None,
        song_id: UUID | None = None,
        provider: str | None = None,
        priority: int = 0,
        max_attempts: int = 5,
        run_after: datetime | None = None,
    ) -> JobQueueItem:
        row = await self._pool.fetchrow(
            """
            INSERT INTO job_queue (
                user_id, batch_id, song_id, job_type, provider,
                status, priority, run_after, max_attempts, payload
            )
            VALUES (
                $1, $2, $3, $4, $5,
                'queued', $6, COALESCE($7, NOW()), $8, $9::jsonb
            )
            RETURNING *
            """,
            user_id,
            batch_id,
            song_id,
            job_type,
            provider,
            int(priority),
            run_after,
            int(max_attempts),
            json.dumps(payload),
        )
        return _row_to_job(row)

    async def claim_next(
        self,
        *,
        worker_id: str,
        job_types: Sequence[str] | None = None,
    ) -> JobQueueItem | None:
        """Claim highest-priority ready job. Optional job_types filters at claim time."""
        types = [str(t) for t in job_types] if job_types else None
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    WITH candidates AS (
                        SELECT id
                        FROM job_queue
                        WHERE status IN ('queued', 'delayed')
                          AND run_after <= NOW()
                          AND ($2::text[] IS NULL OR job_type = ANY($2::text[]))
                        ORDER BY priority DESC, created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE job_queue AS j
                    SET status = 'running',
                        locked_by = $1,
                        locked_at = NOW(),
                        attempts = j.attempts + 1,
                        updated_at = NOW()
                    FROM candidates
                    WHERE j.id = candidates.id
                    RETURNING j.*
                    """,
                    worker_id,
                    types,
                )
        if row is None:
            return None
        return _row_to_job(row)

    async def mark_done(self, job_id: UUID) -> None:
        await self._pool.execute(
            """
            UPDATE job_queue
            SET status = 'done',
                last_error = NULL,
                locked_by = NULL,
                locked_at = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            job_id,
        )

    async def mark_failed_or_retry(
        self,
        job: JobQueueItem,
        *,
        error: str,
        delay_seconds: int = 30,
    ) -> str:
        """Return final status: 'delayed' or 'failed'."""
        message = (error or "unknown error")[:4000]
        if job.attempts >= job.max_attempts:
            await self._pool.execute(
                """
                UPDATE job_queue
                SET status = 'failed',
                    last_error = $2,
                    locked_by = NULL,
                    locked_at = NULL,
                    updated_at = NOW()
                WHERE id = $1
                """,
                job.id,
                message,
            )
            return "failed"

        run_after = datetime.now(timezone.utc) + timedelta(seconds=max(1, int(delay_seconds)))
        await self._pool.execute(
            """
            UPDATE job_queue
            SET status = 'delayed',
                last_error = $2,
                run_after = $3,
                locked_by = NULL,
                locked_at = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            job.id,
            message,
            run_after,
        )
        return "delayed"

    async def requeue_stale_running(self, *, older_than_seconds: int = 1800) -> int:
        """Recover jobs stuck in running after a worker crash."""
        result = await self._pool.execute(
            """
            UPDATE job_queue
            SET status = 'queued',
                locked_by = NULL,
                locked_at = NULL,
                run_after = NOW(),
                updated_at = NOW(),
                last_error = COALESCE(last_error, 'requeued after stale running lock')
            WHERE status = 'running'
              AND locked_at IS NOT NULL
              AND locked_at < NOW() - ($1 * INTERVAL '1 second')
            """,
            int(older_than_seconds),
        )
        # asyncpg returns e.g. "UPDATE 2"
        try:
            return int(str(result).split()[-1])
        except (TypeError, ValueError, IndexError):
            return 0

    async def find_active(
        self,
        *,
        job_type: str,
        user_id: UUID,
        batch_id: UUID | None = None,
        song_id: UUID | None = None,
    ) -> JobQueueItem | None:
        """Return an existing queued/delayed/running job matching the key, if any."""
        row = await self._pool.fetchrow(
            """
            SELECT *
            FROM job_queue
            WHERE job_type = $1
              AND user_id = $2
              AND (($3::uuid IS NULL AND batch_id IS NULL) OR batch_id = $3)
              AND (($4::uuid IS NULL AND song_id IS NULL) OR song_id = $4)
              AND status IN ('queued', 'delayed', 'running')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            job_type,
            user_id,
            batch_id,
            song_id,
        )
        if row is None:
            return None
        return _row_to_job(row)

    async def enqueue_if_absent(
        self,
        *,
        user_id: UUID,
        job_type: str,
        payload: dict[str, Any],
        batch_id: UUID | None = None,
        song_id: UUID | None = None,
        provider: str | None = None,
        priority: int = 0,
        max_attempts: int = 5,
        run_after: datetime | None = None,
    ) -> tuple[JobQueueItem, bool]:
        """Enqueue unless an active twin already exists. Returns (job, created)."""
        existing = await self.find_active(
            job_type=job_type,
            user_id=user_id,
            batch_id=batch_id,
            song_id=song_id,
        )
        if existing is not None:
            return existing, False
        job = await self.enqueue(
            user_id=user_id,
            job_type=job_type,
            payload=payload,
            batch_id=batch_id,
            song_id=song_id,
            provider=provider,
            priority=priority,
            max_attempts=max_attempts,
            run_after=run_after,
        )
        return job, True

    async def list_admin_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        user: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Admin ops board rows: join users for email; optional filters."""
        from platform_api.services.job_types import stage_for_job_type

        limit = max(1, min(int(limit), 200))
        allowed_status = {"queued", "delayed", "running", "failed"}
        clauses: list[str] = ["j.status = ANY($1::text[])"]
        args: list[Any] = [sorted(allowed_status)]
        arg_i = 2

        if status:
            status_norm = status.strip().lower()
            if status_norm not in allowed_status:
                raise ValueError(f"Unsupported status filter: {status}")
            clauses = ["j.status = $1"]
            args = [status_norm]
            arg_i = 2

        if job_type:
            clauses.append(f"j.job_type = ${arg_i}")
            args.append(job_type.strip())
            arg_i += 1

        user_q = (user or "").strip()
        if user_q:
            clauses.append(f"u.email ILIKE ${arg_i}")
            args.append(f"%{user_q}%")
            arg_i += 1

        where_sql = " AND ".join(clauses)
        # Prefer failed/running freshness; otherwise oldest claimable first for backlog.
        order_sql = (
            "j.updated_at DESC"
            if status and status.strip().lower() in {"failed", "running"}
            else "j.created_at ASC"
        )
        args.append(limit)
        limit_ph = f"${arg_i}"

        rows = await self._pool.fetch(
            f"""
            SELECT j.id, j.user_id, u.email AS user_email,
                   j.batch_id, j.song_id, j.job_type, j.provider, j.status,
                   j.priority, j.attempts, j.max_attempts, j.last_error,
                   j.locked_by, j.locked_at, j.run_after, j.created_at, j.updated_at,
                   EXTRACT(EPOCH FROM (NOW() - j.created_at))::float AS age_seconds
            FROM job_queue j
            JOIN users u ON u.id = j.user_id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT {limit_ph}
            """,
            *args,
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            err = row["last_error"]
            err_s = str(err) if err else ""
            if len(err_s) > 300:
                err_s = err_s[:297] + "..."
            out.append(
                {
                    "id": str(row["id"]),
                    "user_id": str(row["user_id"]),
                    "user_email": str(row["user_email"] or ""),
                    "batch_id": str(row["batch_id"]) if row["batch_id"] else None,
                    "song_id": str(row["song_id"]) if row["song_id"] else None,
                    "job_type": str(row["job_type"]),
                    "stage": stage_for_job_type(str(row["job_type"])),
                    "provider": row["provider"],
                    "status": str(row["status"]),
                    "priority": int(row["priority"] or 0),
                    "attempts": int(row["attempts"] or 0),
                    "max_attempts": int(row["max_attempts"] or 5),
                    "last_error": err_s or None,
                    "locked_by": row["locked_by"],
                    "locked_at": row["locked_at"].isoformat() if row["locked_at"] else None,
                    "run_after": row["run_after"].isoformat() if row["run_after"] else None,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    "age_seconds": round(float(row["age_seconds"] or 0.0), 1),
                }
            )
        return out

    async def get_metrics(self) -> dict[str, Any]:
        """Queue depth / busy worker snapshot for admin metrics."""
        from platform_api.services.job_types import stage_for_job_type

        status_rows = await self._pool.fetch(
            """
            SELECT status, COUNT(*)::int AS count
            FROM job_queue
            WHERE status IN ('queued', 'delayed', 'running', 'failed')
            GROUP BY status
            """
        )
        by_status = {str(row["status"]): int(row["count"]) for row in status_rows}

        type_rows = await self._pool.fetch(
            """
            SELECT job_type, status, COUNT(*)::int AS count
            FROM job_queue
            WHERE status IN ('queued', 'delayed', 'running')
            GROUP BY job_type, status
            ORDER BY job_type, status
            """
        )
        by_type: dict[str, dict[str, int]] = {}
        for row in type_rows:
            job_type = str(row["job_type"])
            bucket = by_type.setdefault(job_type, {})
            bucket[str(row["status"])] = int(row["count"])

        oldest = await self._pool.fetchrow(
            """
            SELECT id, job_type, created_at, run_after,
                   EXTRACT(EPOCH FROM (NOW() - created_at))::float AS age_seconds
            FROM job_queue
            WHERE status IN ('queued', 'delayed')
              AND run_after <= NOW()
            ORDER BY created_at ASC
            LIMIT 1
            """
        )
        running_detail = await self._pool.fetch(
            """
            SELECT j.locked_by, j.job_type, u.email AS user_email
            FROM job_queue j
            JOIN users u ON u.id = j.user_id
            WHERE j.status = 'running'
              AND j.locked_by IS NOT NULL
            ORDER BY j.locked_by, j.job_type
            """
        )
        busy: dict[str, dict[str, Any]] = {}
        for row in running_detail:
            wid = str(row["locked_by"])
            entry = busy.setdefault(
                wid,
                {
                    "worker_id": wid,
                    "running_jobs": 0,
                    "job_types": [],
                    "user_emails": [],
                    "stages": [],
                },
            )
            entry["running_jobs"] = int(entry["running_jobs"]) + 1
            jt = str(row["job_type"])
            stage = stage_for_job_type(jt)
            email = str(row["user_email"] or "")
            if jt not in entry["job_types"]:
                entry["job_types"].append(jt)
            if stage not in entry["stages"]:
                entry["stages"].append(stage)
            if email and email not in entry["user_emails"]:
                entry["user_emails"].append(email)

        workers_busy = sorted(
            busy.values(),
            key=lambda item: int(item["running_jobs"]),
            reverse=True,
        )

        queued = int(by_status.get("queued", 0)) + int(by_status.get("delayed", 0))
        return {
            "by_status": by_status,
            "queued_depth": queued,
            "running": int(by_status.get("running", 0)),
            "failed": int(by_status.get("failed", 0)),
            "by_type": by_type,
            "oldest_claimable": (
                None
                if oldest is None
                else {
                    "id": str(oldest["id"]),
                    "job_type": str(oldest["job_type"]),
                    "age_seconds": round(float(oldest["age_seconds"] or 0.0), 1),
                    "created_at": oldest["created_at"].isoformat()
                    if oldest["created_at"] is not None
                    else None,
                }
            ),
            "workers_busy": workers_busy,
        }
