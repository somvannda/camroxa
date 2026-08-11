"""Platform background worker — drains durable job_queue off uvicorn HTTP workers.

Run (production):
  PYTHONPATH=/opt/camxora/repo \\
  /opt/camxora/repo/platform_api/.venv/bin/python -m platform_api.worker

Stage shards (optional):
  CAMXORA_WORKER_JOB_TYPES=draft|suno|images|all
  or comma list: execute_batch,draft,retry_song_draft
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from typing import Any
from uuid import UUID

from platform_api.services.job_types import (
    JOB_DRAFT,
    JOB_EXECUTE_BATCH,
    JOB_RETRY_SONG_DRAFT,
    JOB_RETRY_SONG_SUNO,
    JOB_RUN_IMAGE_JOBS,
    JOB_RUN_YOUTUBE_UPLOADS,
    JOB_SUNO_SUBMIT,
    PRI_SUNO_SUBMIT,
    resolve_worker_job_types,
)

logger = logging.getLogger("platform_api.worker")


def _worker_label() -> str:
    """Prefer CAMXORA_WORKER_NAME (e.g. images@1); else stage preset from job types."""
    named = (os.environ.get("CAMXORA_WORKER_NAME") or "").strip()
    if named:
        return named
    raw = (os.environ.get("CAMXORA_WORKER_JOB_TYPES") or "").strip().lower()
    if raw in {"draft", "suno", "images", "all"}:
        return raw
    return ""


def _worker_id() -> str:
    host = socket.gethostname()
    pid = os.getpid()
    label = _worker_label()
    if label:
        return f"{host}:{label}:{pid}"
    return f"{host}:{pid}"


async def _bootstrap_connections() -> None:
    """Mirror API lifespan wiring (pool + redis) without FastAPI / migrations."""
    from platform_api.config import get_settings, validate_production_settings
    from platform_api.dependencies import set_db_pool, set_redis

    settings = get_settings()
    validate_production_settings(settings)

    import asyncpg

    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    # Keep per-process pools small — multi-stage deploy runs several workers.
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    set_db_pool(pool)
    logger.info("Worker database pool ready.")

    try:
        import redis.asyncio as redis_async

        redis_client = redis_async.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        set_redis(redis_client)
        logger.info("Worker Redis ready.")
    except Exception:
        logger.exception("Worker Redis unavailable — continuing without cache/rate gates.")


async def _shutdown_connections() -> None:
    from platform_api.dependencies import clear_connections, get_db_pool, get_redis

    try:
        pool = get_db_pool()
        await pool.close()
    except Exception:
        pass
    try:
        redis = get_redis()
        await redis.aclose()
    except Exception:
        pass
    clear_connections()


async def _handle_execute_batch(job: Any, payload: dict[str, Any]) -> None:
    from platform_api.dependencies import get_batch_service, get_job_queue_repo

    batch_id = str(payload.get("batch_id") or job.batch_id or "")
    user_id = str(payload.get("user_id") or job.user_id)
    if not batch_id:
        raise ValueError("execute_batch job missing batch_id")
    await get_batch_service().fanout_draft_jobs(
        job_queue=get_job_queue_repo(),
        batch_id=UUID(batch_id),
        user_id=user_id,
    )


async def _handle_draft(job: Any, payload: dict[str, Any], *, submit_suno_inline: bool) -> None:
    from platform_api.dependencies import get_batch_service, get_job_queue_repo
    from platform_api.services.batch_service import SONG_STATUS_DRAFT_READY

    batch_id = UUID(str(payload.get("batch_id") or job.batch_id))
    song_id = UUID(str(payload.get("song_id") or job.song_id))
    user_id = str(payload.get("user_id") or job.user_id)
    batch_service = get_batch_service()
    song = await batch_service.retry_song_draft(
        batch_id=batch_id,
        song_id=song_id,
        user_id=user_id,
        submit_suno=submit_suno_inline,
    )
    if submit_suno_inline:
        return
    if song is None or str(song.status or "") != SONG_STATUS_DRAFT_READY:
        return
    batch = await batch_service.get_batch_for_user(batch_id=batch_id, user_id=UUID(user_id))
    if batch is None or not bool(getattr(batch, "auto_gsuno", False)):
        return
    await get_job_queue_repo().enqueue(
        user_id=UUID(user_id),
        batch_id=batch_id,
        song_id=song_id,
        job_type=JOB_SUNO_SUBMIT,
        payload={
            "batch_id": str(batch_id),
            "song_id": str(song_id),
            "user_id": user_id,
        },
        priority=PRI_SUNO_SUBMIT,
    )


async def _handle_suno(job: Any, payload: dict[str, Any]) -> None:
    from platform_api.dependencies import get_batch_service

    batch_id = UUID(str(payload.get("batch_id") or job.batch_id))
    song_id = UUID(str(payload.get("song_id") or job.song_id))
    user_id = str(payload.get("user_id") or job.user_id)
    await get_batch_service().retry_song_suno(
        batch_id=batch_id,
        song_id=song_id,
        user_id=user_id,
        title=payload.get("title"),
        album=payload.get("album"),
        lyrics=payload.get("lyrics"),
    )


async def _handle_run_image_jobs(job: Any, payload: dict[str, Any]) -> None:
    from platform_api.dependencies import get_image_job_service
    from platform_api.services.image_job_runner import run_image_jobs_until_empty

    user_id = str(payload.get("user_id") or job.user_id)
    batch_id = str(payload.get("batch_id") or job.batch_id or "").strip()
    if not batch_id:
        raise ValueError("run_image_jobs missing batch_id")
    raw_job_ids = payload.get("job_ids")
    job_ids: list[str] | None = None
    if isinstance(raw_job_ids, list):
        job_ids = [str(value).strip() for value in raw_job_ids if str(value).strip()] or None
    await run_image_jobs_until_empty(
        get_image_job_service(),
        user_id=user_id,
        batch_id=batch_id,
        job_ids=job_ids,
    )


async def _handle_run_youtube_uploads(job: Any, payload: dict[str, Any]) -> None:
    from platform_api.dependencies import get_youtube_connection_service

    user_id = str(payload.get("user_id") or job.user_id)
    batch_id = payload.get("batch_id") or (str(job.batch_id) if job.batch_id else None)
    limit = max(1, min(50, int(payload.get("limit") or 4)))
    await get_youtube_connection_service().run_pending_upload_jobs(
        user_id=user_id,
        batch_id=str(batch_id) if batch_id else None,
        limit=limit,
    )


async def _handle_job(job: Any) -> None:
    payload = job.payload or {}

    if job.job_type == JOB_EXECUTE_BATCH:
        await _handle_execute_batch(job, payload)
        return

    if job.job_type == JOB_DRAFT:
        await _handle_draft(job, payload, submit_suno_inline=False)
        return

    if job.job_type == JOB_RETRY_SONG_DRAFT:
        await _handle_draft(job, payload, submit_suno_inline=True)
        return

    if job.job_type in {JOB_SUNO_SUBMIT, JOB_RETRY_SONG_SUNO}:
        await _handle_suno(job, payload)
        return

    if job.job_type == JOB_RUN_IMAGE_JOBS:
        await _handle_run_image_jobs(job, payload)
        return

    if job.job_type == JOB_RUN_YOUTUBE_UPLOADS:
        await _handle_run_youtube_uploads(job, payload)
        return

    raise ValueError(f"Unsupported job_type: {job.job_type}")


async def run_worker_loop(*, poll_idle_seconds: float = 1.0) -> None:
    from platform_api.dependencies import get_job_queue_repo

    worker_id = _worker_id()
    allowed_types = resolve_worker_job_types()
    claim_types = sorted(allowed_types)
    queue = get_job_queue_repo()
    recovered = await queue.requeue_stale_running(older_than_seconds=1800)
    if recovered:
        logger.warning("Requeued %s stale running job(s).", recovered)
    logger.info(
        "Worker %s draining job_queue (types=%s).",
        worker_id,
        claim_types,
    )

    stop = asyncio.Event()

    def _ask_stop(*_args: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _ask_stop)
        except NotImplementedError:
            # Windows
            signal.signal(sig, lambda *_: _ask_stop())

    while not stop.is_set():
        try:
            job = await queue.claim_next(worker_id=worker_id, job_types=claim_types)
        except Exception:
            logger.exception("Failed to claim job; sleeping.")
            await asyncio.sleep(2.0)
            continue

        if job is None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_idle_seconds)
            except asyncio.TimeoutError:
                pass
            continue

        if job.job_type not in allowed_types:
            # Should not happen when claim filters; requeue safely.
            await queue.mark_failed_or_retry(
                job,
                error=f"unsupported job_type for this worker: {job.job_type}",
                delay_seconds=60,
            )
            continue

        logger.info(
            "Running job %s type=%s attempt=%s/%s batch=%s",
            job.id,
            job.job_type,
            job.attempts,
            job.max_attempts,
            job.batch_id,
        )
        try:
            await _handle_job(job)
            await queue.mark_done(job.id)
            logger.info("Job %s done.", job.id)
        except Exception as exc:
            status = await queue.mark_failed_or_retry(
                job,
                error=str(exc),
                delay_seconds=min(300, 15 * max(1, job.attempts)),
            )
            logger.exception("Job %s failed → %s", job.id, status)

    logger.info("Worker %s stopping.", worker_id)


async def _amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    await _bootstrap_connections()
    try:
        await run_worker_loop()
    finally:
        await _shutdown_connections()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
