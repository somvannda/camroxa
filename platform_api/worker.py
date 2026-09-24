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
    JOB_WEB_MUSIC_GENERATE,
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


# A hung handler (or a dead worker whose lock was never released) leaves a job
# stuck in `running` forever. The sweep requeues any `running` job whose lock is
# older than this. Must stay well above the longest legitimate job (drafts can
# take ~30 min), so default is 1 hour.
_DEFAULT_STALE_RUNNING_SECONDS = 3600
# How often each live worker process runs the sweep. Dead workers cannot sweep,
# so a surviving process recovers their orphaned jobs.
_DEFAULT_STALE_SWEEP_INTERVAL_SECONDS = 300


def _stale_running_seconds() -> int:
    try:
        return max(60, int(os.environ.get("CAMXORA_WORKER_STALE_RUNNING_SECONDS", _DEFAULT_STALE_RUNNING_SECONDS)))
    except (TypeError, ValueError):
        return _DEFAULT_STALE_RUNNING_SECONDS


def _stale_sweep_interval_seconds() -> int:
    try:
        return max(30, int(os.environ.get("CAMXORA_WORKER_STALE_SWEEP_INTERVAL_SECONDS", _DEFAULT_STALE_SWEEP_INTERVAL_SECONDS)))
    except (TypeError, ValueError):
        return _DEFAULT_STALE_SWEEP_INTERVAL_SECONDS


def _job_timeout_seconds() -> float:
    """Optional hard timeout per job. 0 (default) disables it."""
    try:
        value = int(os.environ.get("CAMXORA_WORKER_JOB_TIMEOUT_SECONDS", "0"))
    except (TypeError, ValueError):
        return 0.0
    return float(value) if value > 0 else 0.0


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

    try:
        from platform_api.services.telegram_ops_alert_service import (
            install_telegram_ops_hooks,
        )

        install_telegram_ops_hooks()
        logger.info("Worker Telegram ops hooks installed.")
    except Exception as exc:
        logger.warning("Worker Telegram ops hooks skipped: %s", exc)


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


WEB_SUNO_LOCK_KEY = "web_music:suno_submit"
WEB_SUNO_LOCK_TTL_SECONDS = 180
WEB_SUNO_LOCK_WAIT_SECONDS = 90


async def _acquire_web_suno_lock(redis: Any) -> str | None:
    if redis is None:
        return None
    token = f"{_worker_id()}:{id(object())}"
    deadline = asyncio.get_running_loop().time() + WEB_SUNO_LOCK_WAIT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        acquired = await redis.set(WEB_SUNO_LOCK_KEY, token, nx=True, ex=WEB_SUNO_LOCK_TTL_SECONDS)
        if acquired:
            return token
        await asyncio.sleep(0.5)
    raise TimeoutError("Timed out waiting for the web Suno submit lock.")


async def _release_web_suno_lock(redis: Any, token: str | None) -> None:
    if redis is None or not token:
        return
    current = await redis.get(WEB_SUNO_LOCK_KEY)
    if current in {token, token.encode() if isinstance(token, str) else token}:
        await redis.delete(WEB_SUNO_LOCK_KEY)


async def _handle_web_music_generate(job: Any, payload: dict[str, Any]) -> None:
    from platform_api.dependencies import get_db_pool, get_generation_service, get_redis, get_v2_credit_service
    from platform_api.services.web_music_service import WebMusicService

    user_id = UUID(str(payload.get("user_id") or job.user_id))
    task_id = UUID(str(payload.get("task_id") or job.song_id or ""))
    reservation_id = str(payload.get("reservation_id") or task_id)
    redis = None
    try:
        redis = get_redis()
    except Exception:
        redis = None
    lock_token = await _acquire_web_suno_lock(redis)
    try:
        service = WebMusicService(
            get_db_pool(),
            get_generation_service(),
            credit_service=get_v2_credit_service(),
            redis=redis,
        )
        await service.fulfill_queued_generate(
            user_id,
            task_id,
            reservation_id=reservation_id,
        )
    finally:
        await _release_web_suno_lock(redis, lock_token)


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

    if job.job_type == JOB_WEB_MUSIC_GENERATE:
        await _handle_web_music_generate(job, payload)
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
    stale_seconds = _stale_running_seconds()
    sweep_interval = _stale_sweep_interval_seconds()
    job_timeout = _job_timeout_seconds()
    recovered = await queue.requeue_stale_running(older_than_seconds=stale_seconds)
    if recovered:
        logger.warning("Requeued %s stale running job(s).", recovered)
    logger.info(
        "Worker %s draining job_queue (types=%s, stale=%ss, sweep=%ss, job_timeout=%ss).",
        worker_id,
        claim_types,
        stale_seconds,
        sweep_interval,
        job_timeout,
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

    next_sweep = loop.time() + sweep_interval

    while not stop.is_set():
        # Periodic recovery: a hung handler or a dead worker would otherwise
        # leave its job `running` forever (the startup-only sweep never sees it).
        if loop.time() >= next_sweep:
            next_sweep = loop.time() + sweep_interval
            try:
                swept = await queue.requeue_stale_running(older_than_seconds=stale_seconds)
                if swept:
                    logger.warning("Periodic sweep requeued %s stale running job(s).", swept)
            except Exception:
                logger.exception("Periodic stale-job sweep failed; continuing.")

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
            if job_timeout > 0:
                await asyncio.wait_for(_handle_job(job), timeout=job_timeout)
            else:
                await _handle_job(job)
            await queue.mark_done(job.id)
            logger.info("Job %s done.", job.id)
        except asyncio.TimeoutError:
            status = await queue.mark_failed_or_retry(
                job,
                error=f"job exceeded {job_timeout:.0f}s timeout",
                delay_seconds=min(300, 15 * max(1, job.attempts)),
            )
            logger.error("Job %s timed out → %s", job.id, status)
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
