# musicapi: bound the Suno concurrency gate's waiting queue

## Summary

The concurrency gate added in #237 let excess jobs wait in memory without limit.
A sustained flood would grow the pending-promise queue unboundedly (the global
edge limiter caps arrival *rate*, not backlog). This adds `SUNO_MAX_QUEUE`
(default 1000): once that many jobs are waiting, a new job is failed out with a
retryable error and its charge refunded, instead of being queued forever.

## Product impact

- Under a flood, clients past the backlog bound get a fast, clear failure
  (`Server busy: too many queued jobs. Please retry shortly.`) with credits
  refunded via the normal settlement path and an error webhook callback — rather
  than an accumulating queue that eventually degrades the process.
- Normal bursts are unaffected: only the jobs beyond `SUNO_MAX_QUEUE` waiting are
  rejected.

## Technical impact

- `src/concurrency.ts`: `ConcurrencyGate` gains a `maxQueue` bound and throws
  `QueueFullError` from `acquire()` when the wait list is full (`0` = unbounded).
  Slot accounting is unchanged — a rejected job never holds a slot, so the queue
  still drains FIFO with no leak. `stats()` now reports `maxQueue`.
- `src/server.ts`: the gate is constructed with `config.suno.maxQueue`;
  `withSunoSlot()` catches `QueueFullError` and settles the job (`status=error`,
  message, `finalizeJob()` → refund + callback) instead of propagating, so a
  rejected job can never be left pending. `/metrics` `suno` block now includes
  `maxQueue`.
- `src/config.ts`: `suno.maxQueue` from `SUNO_MAX_QUEUE` (default 1000).

No schema change; no new endpoint.

## Files touched

- `musicapi/src/concurrency.ts`
- `musicapi/src/server.ts`
- `musicapi/src/config.ts`
- `musicapi/.env.example`
- `docs/changelog/2026-10-04-musicapi-gate-queue-bound.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain. New optional env:
  `SUNO_MAX_QUEUE` (default 1000; set lower to fail faster, 0 for unbounded).

## Tests

- `npm run typecheck` → clean.
- Unit probe of the bounded gate (`max=1`, `maxQueue=2`): 1 active + 2 waiting;
  the 4th `acquire()` rejected with `QueueFullError`; on release the queue
  admitted in FIFO order (`waiting` 2 → 1 → 0) and `active` returned to 0 (no
  leaked slots). Temp harness removed after.

## Follow-ups

- Alerts on gate depth (`suno.waiting`) and Suno credit burn, especially ahead of
  the planned 2-Premier-account switch (~2,000 generations/month ceiling).
