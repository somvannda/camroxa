# musicapi: protect a small Suno pool with concurrency gates + a 10s per-user window

## Summary

Production runs a deliberately small Suno account pool (4 accounts at the time of
writing; the operator plans to run 2 Premier accounts). Two gaps made that unsafe:

1. **No cap on concurrent Suno jobs.** Jobs are detached and each calls
   `pool.pick()` then submits in parallel, so a burst of API calls would hit the
   pool all at once — the failure mode is Suno 429s / captcha challenges and
   charged-then-refunded churn. `QUEUE_CONCURRENCY` did not help (it only applies
   to the optional Redis driver and is not tied to pool health).
2. **No short per-user request window.** The per-user limiter only had
   per-minute and per-day budgets, so it could not express sunoapi.org's
   documented **20 requests / 10 seconds** account limit.

This change adds a process-wide concurrency gate for Suno-backed jobs (global
ceiling derived from the account count, plus a per-user cap) and a separate
per-user `requests_per_window` budget whose window length is independent of the
global edge limiter.

## Product impact

- A burst now **queues** instead of stampeding the pool: jobs beyond
  `pool.size × SUNO_CONCURRENT_PER_ACCOUNT` wait for a slot, keeping both
  accounts healthy and avoiding wasted credits on captcha/429 failures.
- One user cannot occupy the whole pool: `max_concurrent_jobs` (default
  `SUNO_MAX_CONCURRENT_PER_USER=2`) caps their in-flight jobs, and all of a
  user's API keys share the budget.
- Admins can now set a per-user **10-second** request budget
  (`requests_per_window`) and concurrent-job cap per user, in addition to the
  existing per-minute / per-day limits.

## Technical impact

- **New `src/concurrency.ts`** — `ConcurrencyGate`, a FIFO, slot-based limiter.
  A waiting job never holds a slot (no deadlock); the global ceiling is a
  function re-evaluated per admission, so **adding a Suno account raises capacity
  without a restart**.
- **`src/server.ts`**
  - One gate wired at build: capacity = `config.suno.maxConcurrent` or
    `pool.size × config.suno.concurrentPerAccount`.
  - `runClipJobWithRetry` / `runResultJobWithRetry` (the two execution entry
    points for every job — inline and queued) now run inside `withSunoSlot()`,
    which acquires a global + per-user slot and releases it in `finally`.
    Per-user cap = the user's `rate_limits.max_concurrent_jobs` override, else
    the configured default.
  - Per-user limiter gained a third window (`requests_per_window` over
    `RATE_LIMIT_USER_WINDOW_MS`), advertised via
    `x-user-rate-limit-window` / `x-user-rate-remaining-window`; the existing
    per-minute/day windows and headers are unchanged.
  - `/metrics` (admin) reports `suno: { active, waiting, capacity,
    maxConcurrentPerUser }`.
  - `/admin/users/:id/rate-limits` GET/PUT now read and write
    `requests_per_window` and `max_concurrent_jobs` (still null-to-clear; the row
    is deleted only when all four limits are null).
- **`migrations/0025_rate_limits_window.sql`** — adds the two nullable columns.
- **`src/config.ts`** — `rateLimit.userWindowMs` (`RATE_LIMIT_USER_WINDOW_MS`,
  default 10s) and a `suno` block (`SUNO_CONCURRENT_PER_ACCOUNT`,
  `SUNO_MAX_CONCURRENT`, `SUNO_MAX_CONCURRENT_PER_USER`).

No route removals; all new fields are optional and default to safe values.
Existing clients see identical responses except for the two new rate-limit
headers when a user has a window budget set.

## Files touched

- `musicapi/src/concurrency.ts` (new)
- `musicapi/src/server.ts`
- `musicapi/src/config.ts`
- `musicapi/migrations/0025_rate_limits_window.sql` (new)
- `musicapi/.env.example`
- `docs/changelog/2026-10-04-musicapi-pool-rate-limits.md` (this file)

The `web-admin` rate-limits form does **not** yet surface the two new fields;
operators can set them via `PUT /admin/users/:id/rate-limits` until the UI lands
(see Follow-ups).

## Migration / deploy

1. Deploy `musicapi` through the normal sandbox-first chain
   (`scripts/deploy/sync_musicapi_sandbox.py`, then the production driver with
   `--yes`). `scripts/migrate.ts` applies `0025_rate_limits_window.sql`.
2. Optional tuning env: `SUNO_MAX_CONCURRENT`, `SUNO_CONCURRENT_PER_ACCOUNT`,
   `SUNO_MAX_CONCURRENT_PER_USER`, `RATE_LIMIT_USER_WINDOW_MS`. Defaults:
   4 per account, per-user 2, window 10s. With a 2-account pool the derived
   ceiling is 8.
3. No restart-order dependency; `ADD COLUMN IF NOT EXISTS` is safe on a live DB
   and the runner is idempotent.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `ConcurrencyGate` unit probe: with global max 2 and per-owner cap 1, observed
  global peak `2`, per-owner peak `1`, and the gate drained to
  `{ active: 0, waiting: 0 }` (no leaked slots). Temp harness removed after.
- `scripts/migrate.ts` on a throwaway DB → `0025` applied; re-run → `0 applied`
  (idempotent); `information_schema` shows `requests_per_window` and
  `max_concurrent_jobs` on `rate_limits`.
- `npx tsx src/serve.ts` against the throwaway DB (port 4103) → booted,
  `GET /health` → `{"ok":true,"accounts":0,"jobs":0}`. Throwaway DB dropped after.
- **Live sandbox burst test** (post-deploy, capacity `8`, `maxConcurrentPerUser`
  default `2`), against `POST /v1/lyrics`, sampling admin `/metrics` `suno` stats:
  - per-user cap raised to 100, 20 requests → `maxActive=8` (global ceiling
    held), `maxWaiting=12`, all `202`.
  - per-user cap 2, 12 requests → `maxActive=2` (per-user cap held),
    `maxWaiting=9`, all `202`.
  - gate drained to `{active:0,waiting:0}` afterwards. Throwaway users + jobs
    removed afterwards.

## Follow-ups

- Surface `requests_per_window` and `max_concurrent_jobs` in the admin console's
  user rate-limits form (`web-admin`).
- Bound the gate's waiting queue (currently unbounded in the in-memory driver)
  and reject with a retryable `429/503` past a depth limit, so a flood cannot
  accumulate detached pending promises.
- Consider route-aware budgets so read-only endpoints (`record-info`, details)
  can stay generous while generation submissions stay tight.
- Scale the pool: Plan for ~2,000 generations/month (Suno Premier ≈ 10,000
  credits ÷ 10 credits/generation) per account; add accounts when sustained
  generation demand approaches the monthly credit ceiling.
