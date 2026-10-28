# Capacity exhaustion is a deferral, not a failure

**Date:** 2026-10-28
**Branch:** `fix/musicapi-capacity-deferral`
**Surface:** Core API (`musicapi`), generation jobs, credit ledger

## Summary

`runClipJobWithRetryImpl` and `runResultJobWithRetryImpl` treated every terminal
submit error the same way: after the cross-account attempts were spent they set
`job.status = "error"` and called `finalizeJob` (usage log + refund + callback).

One of those "errors" is not a delivery failure at all — *"No Suno account with
available credits for this model."* The pool is dry **right now**; the job is
still valid, the accounts refill on their own schedule, and the user has already
been charged. The old behaviour failed the job out, refunded it, and left the
client to re-submit from scratch.

On 2026-10-28 that produced **48 failed jobs and 45 blind re-submissions in 40
minutes**, all against the same empty pool: 75 `v3_music` debits and 59 refunds
for 30 songs.

This change defers capacity-blocked jobs instead: the job stays `pending`, the
charge is **not** refunded (there is nothing to undo — the work is still owed),
and the job is re-armed with exponential backoff. Only after the deferral budget
is exhausted does it settle as a real failure and refund.

## Product impact

- A dry pool no longer destroys the user's job. Songs queued at 09:03 now resume
  automatically once an account has credits, instead of requiring a manual
  retry.
- Fewer ledger entries: one debit per song while deferred, instead of a
  debit/refund pair per attempt.
- No change to genuine failures (content policy, provider 4xx, unplayable
  result): they still settle and refund immediately.
- The user sees the job return to `pending`/queued rather than `*_FAILED`.

## Technical impact

- `Job` gains `capacityDeferrals?: number` (in-memory; a restart re-queues
  pending jobs and the counter restarts — the bound exists to stop one process
  looping, not to enforce a global budget).
- `isCapacityExhaustion(err)` classifies a failure as "pool is empty": Suno 402 /
  insufficient-credits (via the existing `isInsufficientCreditsError`) plus the
  pool-selection messages (`no suno account with available credits`,
  `no usable account`, `no paid suno account is available`).
- `deferForCapacity(...)` runs instead of `finalizeJob` when **every** collected
  attempt error is a capacity error:
  - `status = "pending"`, `error` cleared, `accountId` cleared, persisted;
  - re-armed via `runResultJobWithRetry` / `runClipJobWithRetry` after
    `60s × 2^n` (1, 2, 4, 8, 16, 32 min — ~63 min of cover, 6 deferrals);
  - `finalizeJob` is **not** called, so no usage-log row, no refund and no
    callback while deferred;
  - one `console.warn` per deferral with the attempt counter and reason.
- Mixed error sets are **not** deferred. If any attempt failed for a
  non-capacity reason, the job settles exactly as before — a content-policy
  rejection must not be retried for an hour.

## Files touched

| File | Change |
|---|---|
| `musicapi/src/server.ts` | `capacityDeferrals` on `Job`; `isCapacityExhaustion` + `deferForCapacity`; both retry implementations call it before `finalizeJob` |

No migration: the counter is in-memory and the `jobs` row already carries the
`pending` status the deferral uses.

## Migration/deploy

- No schema change, no configuration, no feature flag.
- Deploy is behaviour-only; rollback is a revert of `server.ts`.
- Jobs already in `error` from before the deploy are untouched (they were
  refunded and remain terminal).

## Tests

- `npm run typecheck` — clean.
- Manual verification on the next dry-pool event: expect `[jobs] <id> deferred for
  capacity (n/6) in Ns: No Suno account with available credits…` and `pending`
  rows instead of an `error` burst, with no new `refund` ledger rows.
- No unit test: both retry implementations are closures inside the server module
  with no seam. The classification is the only pure part; extracting it into
  `sunoError.ts` would make it testable (follow-up).

## Known limitations

- The in-process `setTimeout` re-arm is not durable. If the process restarts
  while a job is deferred, `recoverJobs` re-queues it only when its payload is a
  runnable descriptor; composite music jobs keep the pre-R4 inline path and are
  failed out with `RESTART_INTERRUPT_ERROR` (unchanged from before).
- Deferral does not create capacity. If the pool stays dry for an hour the job
  still fails and refunds — which is the correct outcome, just later.

## Follow-ups

- **Persist `suno_accounts.credits_left`** on every `billing/info` probe and alert
  on low pool headroom. All 10 rows are `NULL` today, which is why a fully dry
  pool was invisible until users reported it.
- **Alert on refund rate** (>10%) — cheapest early warning for exactly this
  class of incident.
- **Admin System Health** shows `complete 72 / error 28` from a 60-minute
  in-memory window; split deferred from failed so a dry pool stops looking like
  28 broken jobs.
- **platform_api retry sweep**: `retry_song_suno` re-submits every ~5 min with no
  capacity awareness; it should read pool health (or the job's `pending` state)
  instead of hammering.
- Extract `isCapacityExhaustion` to `sunoError.ts` with unit tests.
