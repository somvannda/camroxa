# Image dependency gate: stop charging thumbnails before their background exists

**Date:** 2026-10-28
**Branch:** `fix/image-dependency-gate`
**Surface:** Platform API (image jobs), credit ledger

## Summary

Thumbnail image jobs are chained to a background image through
`image_jobs.source_job_id`. The batch runner claimed them on `status = 'pending'`
alone (`claim_image_jobs_for_run`), and `_run_one_job` performed the wallet hold
(`reserve_and_hold_before_provider` → `atomic_deduct`) **before** checking whether
that source artefact existed. The chained job then waited only 10 seconds
(`_wait_for_source_job_output`: 20 × 0.5s), raised `DependencyPendingError`, and
the service refunded the charge as `image_generation_deferred` and put the job
back to `pending` — to be charged and refunded again on the next sweep.

Production on 2026-10-28 showed the cost of that loop: **21 `v3_image` debits
against 14 refunds (7 `image_generation_failed`, 7 `image_generation_deferred`)**
— a 67% refund rate, with each deferred attempt writing a debit and a refund row
for work that could not have run.

This change gates the job on its dependency: a chained image is not claimable
until its source is terminal, and the service re-checks readiness **before** the
wallet hold. A not-ready dependency now costs nothing and writes no ledger rows.

## Product impact

- No user-visible behaviour change on the happy path: thumbnails still use the
  same composite pipeline once the background image is ready.
- The `image_generation_deferred` refund disappears from the user's ledger for
  new jobs (historical rows are untouched).
- A thumbnail whose background genuinely failed still fails, now with the
  existing explicit message (`Thumbnail image job source background job failed.`)
  rather than a silent charge/refund loop.
- Fewer spurious "refund" entries, so ledger history becomes trustworthy.

## Technical impact

Two layers, deliberately redundant:

1. **Claim-time gate** (`ImageJobRepository.claim_image_jobs_for_run`): rows with a
   `source_job_id` are only claimable when the source row is `success` or
   `failed`. Terminal-inclusive on purpose — a failed source must still be claimed
   so it can fail fast with a clear error instead of parking forever.
2. **Pre-billing gate** (`ImageJobService._ensure_dependency_ready`): called after
   prompt validation and **before** `reserve_and_hold_before_provider`. Raises
   `DependencyPendingError` when the source is still running, or `ValidationError`
   when the source is missing/failed. Because it runs before the hold,
   `quota_reserved` stays `False`, so the existing exception handler resets the job
   to `pending` without touching wallet or quota. This also covers jobs claimed by
   an older build or passed explicitly via `job_ids`.

`_wait_for_source_job_output` is retained as a last-resort safety net; with the
gates in place it returns immediately.

No schema change and no migration: the gate is a read-only predicate over the
existing `image_jobs` table (`id` is the primary key, so the `EXISTS` join is an
index lookup).

## Files touched

| File | Change |
|---|---|
| `platform_api/repositories/batch_repo.py` | Dependency predicate in `claim_image_jobs_for_run` |
| `platform_api/services/image_job_service.py` | `_ensure_dependency_ready` helper + call before the billing hold |
| `platform_api/tests/test_image_dependency_gate.py` | New coverage (below) |

## Migration/deploy

- No migration, no configuration, no feature flag.
- Safe to deploy in any order relative to other services; it only removes
  premature claims and premature charges.
- Rollback is a revert of the two files; no data repair needed (the gate never
  writes).

## Tests

`platform_api/tests/test_image_dependency_gate.py`:

1. Thumbnail with a still-running source → `_run_one_job` returns `False`, the job
   goes back to `pending`, and **no wallet hold / no refund** is requested.
2. Thumbnail with a failed source → terminal `failed` status with the explicit
   message, and still no wallet hold.
3. Thumbnail with a successful source and output → proceeds past the gate (the
   regression guard for the happy path).

Existing suites that must stay green: `test_image_job_service.py`,
`test_image_job_service_retry.py`, `test_image_job_auto_retry.py`,
`test_image_job_server_cache.py`, `test_image_job_source_remap.py`,
`test_prepaid_image_billing.py`.

## Follow-ups (not in this change)

- **Capacity is not a failure.** `musicapi` should defer generation jobs on
  pool-credit exhaustion (requeue + backoff, hold intact) instead of failing them
  terminally after one attempt (`runResultJobWithRetryImpl` breaks on
  `pool.pickExcept`). Today: 48 errors, 45 blind retries, 59 refunds.
- **Split the admin System Health tile.** `complete 72 / error 28` is a 60-minute
  in-memory window (`JOB_TTL_MS`), not a backlog; it conflates deferred with
  failed.
- **Persist `suno_accounts.credits_left`** on each `billing/info` probe and alert
  on low pool headroom — all 10 rows are `NULL`, which is why the 09:03 outage was
  invisible until users reported it.
- **Alert on refund rate** (Suno hit 79% today, images 67%) — the cheapest early
  warning available.
- **Retries re-bill draft work**: ~16 extra `v3_lyric` debits today were never
  refunded. Reuse stored lyrics on retry.
- **Desktop failure telemetry**: `client_log_batches` had zero rows for the
  affected user, so the rendered message could not be verified.
