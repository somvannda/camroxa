# Stuck Suno tasks no longer hang `pending` when the provider returns 404

## Summary

A Suno task the provider no longer knows — `check_status` returns HTTP **404** —
never left `pending`. `batch_service.reconcile_pending_suno_tasks` wraps the
poll in `try/except Exception: … continue`, so the terminal 404 was treated like
a transient blip and the row sat in `pending` forever. The song stayed
`pending`, its batch stayed `processing`, and the wallet debit (10 credits) was
never refunded.

Observed in production: user `edmbass1` had **17** such songs (all from the
2026-10-07 batches) and the platform had **23** stale `pending` tasks, every one
of them returning `Suno API error 404: check_status(...)`.

Follow-up to [the retry upsert fix](./2026-10-08-platform-suno-retry-unique-constraint.md);
the two together cover both failure shapes — a stale *failed* row (retry
collides) and a lost *pending* row (reconcile hangs).

## Product impact

- A generation the provider lost is now reconciled as a **failure** instead of
  hanging: the song shows failed and the wallet debit is refunded
  (`suno_generation_failed`), so the customer is not charged for a generation
  that will never arrive.
- A retry (or the retry sweep) then regenerates it — combined with the upsert
  fix, the retry revives the task row and succeeds.
- A 404 *immediately* after submit is still treated as propagation lag and left
  pending (grace window), so a fresh task is never failed prematurely.
- Transient errors (timeouts, 5xx) keep the previous `continue` behaviour.

## Technical impact

- `platform_api/repositories/batch_repo.py` — `list_reconcilable_suno_tasks`
  also selects `created_at` (needed for the age gate).
- `platform_api/services/batch_service.py`
  - `BatchService._SUNO_NOT_FOUND_TERMINAL_AFTER` (`timedelta(minutes=30)`).
  - `_suno_poll_is_terminal_not_found(exc)` — true when the poll raised
    `ExternalServiceError` with `details["status_code"] == 404`.
  - `_suno_task_aged_for_terminal_not_found(created_at, now=…)` — tz-safe age
    check against the grace window.
  - `reconcile_pending_suno_tasks` — new `except ExternalServiceError` branch: an
    aged 404 is turned into a synthetic
    `SunoGeneratePollResult(state="failed", error="Suno task no longer exists
    upstream (404).")`, which flows into the existing FAILED handling
    (`update_status` + `handle_suno_task_update`, which refunds and refreshes the
    batch). Non-404 and non-aged errors keep the old skip.
- `platform_api/tests/test_reconcile_suno_404_terminal.py` (new) — aged 404 →
  terminal failure/refund; recent 404 → not terminal; aged 500 → skipped; grace
  boundary.

No schema change. `platform_api` only.

## Files touched

- `platform_api/repositories/batch_repo.py`
- `platform_api/services/batch_service.py`
- `platform_api/tests/test_reconcile_suno_404_terminal.py` (new)
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-10-08-platform-reconcile-suno-404-terminal.md` (this file)

## Migration / deploy

- No migration. Redeploy `platform_api`, then restart `camxora-api` and the
  `camxora-worker-suno@*` workers.
- Existing stuck rows clear the next time reconcile runs for their user (the
  music-history / pending-downloads path). A one-off backfill can drive
  `reconcile_pending_suno_tasks` for the affected users to clear them
  immediately.

## Tests

- `platform_api/tests/test_reconcile_suno_404_terminal.py` +
  `test_batch_service.py` + `test_suno_sanitize_followups.py`: **61 passed**.

## Follow-ups

- Consider a periodic platform-wide reconcile sweep so lost tasks clear without
  a user opening history.
- `_refund_suno_billing` still relies on the 14-day Redis charge stash
  (`gen_charge:suno:<song_id>`); a task older than that would fail without a
  wallet refund. Tracked separately.
