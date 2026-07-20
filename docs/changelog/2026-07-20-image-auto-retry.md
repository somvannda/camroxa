# Image auto-retry + fail-budget unblock for sandbox testing

**Date:** 2026-07-20  
**Status:** implemented (API deploy + sandbox budget reset)

## Summary

Image jobs that fail for transient provider errors are now automatically re-queued as `pending` in the background runner (up to `image_job_max_attempts`, default 3). Fail-budget / quota / insufficient-credits errors are not auto-retried. Sandbox user `somvannda@gmail.com` had fail-absorb counter cleared and 56 failed jobs requeued.

## Product impact

**Before**
- Failed images stayed `failed` until the user clicked Retry.
- Hitting the daily fail-absorb budget (default 25) blocked all further image work with “Try again tomorrow,” even with a high daily image quota.

**After**
- Background runner auto-retries transient failures up to 3 attempts.
- Budget / credits / quota hard stops stay terminal (no spin loop).
- somvannda can generate images again today (counter reset; sandbox absorb budget raised to 500).

## Technical impact

- `ImageJobService._run_one_job`: on failure → `pending` if `attempt_count < max` and error is retryable.
- `BatchRepository.requeue_auto_retry_failed_jobs` + call from `run_pending_jobs`.
- `run_image_jobs_until_empty` waits briefly for auto-retry requeues.
- Config: `PLATFORM_IMAGE_JOB_MAX_ATTEMPTS` / `image_job_max_attempts` (default 3).
- Sandbox env: `PLATFORM_DAILY_FAIL_ABSORB_BUDGET=500`.

## Files touched

- `platform_api/config.py`
- `platform_api/services/image_job_service.py`
- `platform_api/services/image_job_runner.py`
- `platform_api/services/image_progress_log.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/tests/test_image_job_auto_retry.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-07-20-image-auto-retry.md`

## Migration / deploy

1. Deploy `platform_api` to sandbox and restart API (picks up new code + absorb budget env).
2. No alembic migration.
3. Desktop: refresh Image page / Run pending if jobs are still queued.

## Tests

- `pytest platform_api/tests/test_image_job_auto_retry.py` — 3 passed.

## Follow-ups

- Surface attempt count + “auto-retrying” in desktop Image UI.
- Consider admin action to clear fail-absorb for a user without SSH.
