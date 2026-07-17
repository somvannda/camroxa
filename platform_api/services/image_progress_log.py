"""Readable image job logging for the API terminal."""

from __future__ import annotations

import logging

from platform_api.terminal_log import emit, short_id

logger = logging.getLogger("platform_api.images")


def _progress(message: str, *args: object) -> None:
    emit("images", message, *args, level=logging.INFO)


def _progress_warn(message: str, *args: object) -> None:
    emit("images", message, *args, level=logging.WARNING)


def log_run_scheduled(*, user_id: str, batch_id: str | None, limit: int) -> None:
    _progress(
        "Run scheduled for user %s batch=%s (limit=%d).",
        short_id(user_id),
        short_id(batch_id),
        limit,
    )


def log_runner_started(*, user_id: str, batch_id: str) -> None:
    _progress(
        "Runner started for user %s batch=%s.",
        short_id(user_id),
        short_id(batch_id),
    )


def log_runner_iteration(*, batch_id: str, iteration: int, ran: int) -> None:
    if ran <= 0:
        return
    _progress(
        "Runner batch=%s iteration=%d claimed %d job(s).",
        short_id(batch_id),
        iteration,
        ran,
    )


def log_runner_finished(*, batch_id: str, total_ran: int) -> None:
    _progress(
        "Runner finished for batch=%s (%d job(s) executed).",
        short_id(batch_id),
        total_ran,
    )


def log_retry_requested(
    *,
    user_id: str,
    batch_id: str | None,
    job_ids: list[str] | None,
) -> None:
    if job_ids:
        _progress(
            "Retry requested by user %s for %d job(s).",
            short_id(user_id),
            len(job_ids),
        )
    else:
        _progress(
            "Retry requested by user %s for batch=%s.",
            short_id(user_id),
            short_id(batch_id),
        )


def log_retry_reset(*, batch_id: str | None, updated: int) -> None:
    _progress(
        "Retry reset %d job(s) for batch=%s.",
        updated,
        short_id(batch_id),
    )


def log_jobs_claimed(*, batch_id: str | None, count: int, workers: int) -> None:
    _progress(
        "Claimed %d pending job(s) for batch=%s (workers=%d).",
        count,
        short_id(batch_id),
        workers,
    )


def log_job_started(
    *,
    job_id: object,
    batch_id: object | None,
    kind: str,
    channel_role: str,
    attempt: int,
) -> None:
    _progress(
        "Job %s started — kind=%s role=%s batch=%s attempt=%d.",
        short_id(job_id),
        kind,
        channel_role,
        short_id(batch_id),
        attempt,
    )


def log_job_waiting(*, job_id: object, reason: str) -> None:
    _progress(
        "Job %s waiting: %s",
        short_id(job_id),
        reason[:200],
    )


def log_slai_rate_limit_wait(wait_seconds: float) -> None:
    _progress(
        "SLAI rate limit: waiting %.1fs before next image request.",
        wait_seconds,
    )


def log_provider_attempt(
    *,
    job_id: object,
    provider: str,
    sub_model: str | None,
    attempt: int = 1,
    max_attempts: int = 1,
) -> None:
    model = str(sub_model or "").strip() or "default"
    if max_attempts > 1:
        _progress(
            "Job %s calling provider %s/%s (attempt %d/%d).",
            short_id(job_id),
            provider,
            model,
            attempt,
            max_attempts,
        )
    else:
        _progress(
            "Job %s calling provider %s/%s.",
            short_id(job_id),
            provider,
            model,
        )


def log_provider_retry(
    *,
    job_id: object | None,
    provider: str,
    sub_model: str | None,
    attempt: int,
    max_attempts: int,
    delay_seconds: float,
    error: str,
) -> None:
    model = str(sub_model or "").strip() or "default"
    _progress_warn(
        "Job %s provider %s/%s attempt %d/%d failed (%s); retrying in %.1fs.",
        short_id(job_id),
        provider,
        model,
        attempt,
        max_attempts,
        error[:200],
        delay_seconds,
    )


def log_provider_fallback(
    *,
    job_id: object | None,
    provider: str,
    sub_model: str | None,
    error: str,
    next_provider: str | None,
) -> None:
    model = str(sub_model or "").strip() or "default"
    if next_provider:
        _progress_warn(
            "Job %s provider %s/%s failed (%s); trying %s next.",
            short_id(job_id),
            provider,
            model,
            error[:200],
            next_provider,
        )
    else:
        _progress_warn(
            "Job %s provider %s/%s failed (%s); no more fallbacks.",
            short_id(job_id),
            provider,
            model,
            error[:200],
        )


def log_job_success(
    *,
    job_id: object,
    kind: str,
    provider: str,
    output_path: str,
) -> None:
    _progress(
        "Job %s succeeded — kind=%s provider=%s output=%s",
        short_id(job_id),
        kind,
        provider,
        output_path,
    )


def log_job_failed(*, job_id: object, kind: str, error: str) -> None:
    _progress_warn(
        "Job %s failed — kind=%s error=%s",
        short_id(job_id),
        kind,
        error[:300],
    )


def log_runner_crashed(*, user_id: str, batch_id: str, error: str) -> None:
    _progress_warn(
        "Runner crashed for user %s batch=%s: %s",
        short_id(user_id),
        short_id(batch_id),
        error[:300],
    )
