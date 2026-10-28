# Pool credit telemetry and refund-rate alerting

**Date:** 2026-10-28
**Branch:** `feat/pool-credit-telemetry`
**Surface:** Core API (`musicapi`) — account pool, alerting/observability

## Summary

Two observability gaps turned today's Suno pool exhaustion into a user-reported
incident at 09:45 instead of an operator alert at 09:03.

1. **Balances were invisible.** `suno_accounts.credits_left` was `NULL` for all 10
   accounts: the live balance from `billing/info` only ever lived in a 30-second
   in-memory cache. Nothing in the DB, the admin console, or `/health` could show
   that the pool was empty.
2. **No alert covered delivery failure.** The existing alerts watch job *errors*,
   low API-key credits, captcha state and queue backlog. A drained pool does not
   necessarily raise errors — today it produced 48 of them, but a deferred or
   refunded job can look healthy in every existing metric.

This change persists the probed balance and adds a refund-rate alert.

## Product impact

- Operators can see the pool balance in the database and in the admin Suno
  accounts view without probing accounts by hand.
- A refund spike pages ops on its own, with the observed rate and window, instead
  of waiting for a support message.
- No user-facing behaviour change.

## Technical impact

- `AccountPool.healthFor()` now writes the probed balance back to
  `suno_accounts.credits_left` (`WHERE label = $1`, matching the table's existing
  identity used by cookie rotation and type sync). Best-effort: a failed write is
  swallowed, exactly like `persistCookie`, so telemetry can never fail routing.
- New `alerts.refund_rate_threshold` (default `0.1`) and
  `alerts.refund_rate_min_jobs` (default `10`), wired through the same
  `coerceAlerts` / admin validation path as the other numeric thresholds, `0`
  disables the check.
- New alert `refund_rate` in `AlertType`, computed from `credit_transactions`:
  `count(type='refund') / count(type='spend')` over `window_minutes`. Every
  settled job writes a `spend` row and a failed job additionally writes a
  `refund` row, so the ratio measures delivery failure directly. Severity is
  `critical` at ≥ 50%, `warning` at the threshold.
- The check is gated on `refund_rate_min_jobs` so a quiet window with one refund
  cannot page anyone.

## Files touched

| File | Change |
|---|---|
| `musicapi/src/pool.ts` | Persist `credits_left` from each successful billing probe |
| `musicapi/src/server.ts` | `refund_rate_*` settings, `AlertType`, refund-rate alert block |

No migration: `suno_accounts.credits_left` already exists (nullable).

## Migration/deploy

- No schema change, no backfill required — the column fills in as accounts are
  probed (routing probes every account within a few minutes of boot, and the
  keep-alive loop refreshes sessions).
- Defaults are active immediately; an operator can raise
  `refund_rate_threshold` or set it to `0` from the admin alerts settings.

## Tests

- `npm run typecheck` — clean.
- `npm run test:unit` — **133 passed**.
- Verification after deploy: `SELECT label, credits_left FROM suno_accounts;`
  should show non-`NULL` balances within minutes, and the alert list should
  include `refund_rate` only when the window actually crosses the threshold.

## Follow-ups

- Surface the persisted balance in the admin Suno accounts table (the column now
  has data; the UI still doesn't show it).
- Alert on **total pool headroom** directly (e.g. `sum(credits_left) < N`), which
  is the complement of this refund signal and fires even earlier.
- platform_api's retry sweep still ignores capacity; it should stop re-submitting
  while musicapi reports a deferred/pending job or a dry pool.
