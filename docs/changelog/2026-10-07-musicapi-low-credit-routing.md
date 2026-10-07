# musicapi: skip low-credit Suno accounts and retry 402/429 across the pool

## Summary

A pooled Suno account reports a positive credit balance right up until it hits
zero, so an account with a couple of credits still looked "healthy" and was
picked for new work. Every job sent to it then failed upstream with
`generate/v2 failed (402): "You don't have enough credits right now"`. The
cross-account retry never rescued those jobs either: `RETRYABLE_ERROR` matched
`rate limit` and 5xx, but **not** `402`, nor the `429` body's
"Too many requests" / `rate_limited`, so the failure was terminal on the first
attempt.

In production this concentrated 55/72 errors on a single drained account and
pushed the `/admin/system` failure-rate alert to **33.3% (53/159)**.

## Product impact

- Jobs no longer get routed to a nearly-drained account: accounts below
  `SUNO_MIN_CREDITS` (default 10) are skipped during selection, so the first
  attempt already lands on a funded account instead of burning the request.
- A `402` (insufficient credits) or `429` (rate limited) on one account now
  retries on a **different** pooled account instead of failing the job outright.
- No change to user billing: a job is charged once and only refunded on terminal
  failure, and settlement stays idempotent.
- No duplicate risk from these retries — `402` and `429` are definitive
  rejections (nothing is created upstream), and only the successful attempt's
  clips are ever used.

## Technical impact

- `src/config.ts`: new `suno.minCredits` (`SUNO_MIN_CREDITS`, default 10).
- `src/pool.ts`: new pure, exported `belowCreditFloor(credits, floor)`; used by
  `pick`, `pickFeature`, `pickExcept`, and `pickFeatureExcept` in place of the
  old `credits <= 0` check. The floor is clamped to `>= 1` so the historic rule
  that an exactly-empty account is never selected still holds when the setting is
  `0`. (`sawZeroCredits` → `sawLowCredits`.)
- `src/server.ts`: `RETRYABLE_ERROR` now also matches `402`, `429`,
  `rate_limited`, `too many requests`, and `not enough credits`, so the existing
  retry loops (`excludeAttemptedIds`) switch accounts.
- `test/pool.test.ts`: unit tests for the floor boundary and the empty-account
  guarantee.

No schema change.

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/.env.example`
- `musicapi/test/pool.test.ts`
- `docs/changelog/2026-10-07-musicapi-low-credit-routing.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain
  (`sync_musicapi_sandbox.py` → `deploy_musicapi_production.py`).
- New optional env: `SUNO_MIN_CREDITS` (default 10). No `.env` change required;
  set it to `0` to restore the old "only skip exactly-empty accounts" behaviour.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run test:unit` (musicapi) → 52/52 pass, including the two new
  `belowCreditFloor` cases.
- Regex checked against the exact production error strings: `402`/`429`/5xx →
  retryable; `400`/`422` invalid-model/prompt → still terminal.

## Follow-ups

- Ambiguous failures (timeout / 5xx after the upstream may have accepted the
  submit) were already retryable and can still duplicate a generation — tracked
  in issue #368 (idempotency key on the Suno submit).
- Optional hardening (out of scope here): quarantine a drained account by
  zeroing its cached health on a `402`, so it is not retried inside the 30s
  health-cache window.
