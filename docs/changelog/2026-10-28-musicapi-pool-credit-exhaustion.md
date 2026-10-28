# musicapi: honest "no credits" failures from the Suno account pool

## Summary

A generation job could fail with the user-visible error
`All 1 attempts failed: No Suno account with available credits for this model.`
That text is the pool's internal routing reason, shown verbatim in the
playground and stored on `jobs.error`. Two problems sat behind it:

1. A **bare 402** from Suno marked the account as drained, even when the 402 was
   not about credits (restricted or billing-held account). One such rejection
   per account parked the whole pool as "out of credits" for a full health-cache
   window, so jobs were refused with no real drain behind them.
2. When the pool *was* genuinely drained, the message named no account and read
   like a per-attempt failure, which hid the operational action (top up / add a
   funded paid account).

## Product impact

- A drained pool now shows: *"Music generation is temporarily unavailable:
  every Suno account is out of credits for this model. Please try again in a few
  minutes."* — no `All N attempts failed` wrapper and no internal account labels.
- Fewer phantom "no credits" outages: a 402 that is not about credits no longer
  blanks an account's balance.
- Nothing changes for a funded pool; charging, refunds and retries are untouched.

## Technical impact

- `pool.ts`
  - `pickFrom` now throws the typed `PoolCreditExhaustedError`. `message` is
    user-safe; `detail` (`model`, `policy`, `${id} (${credits})` per drained
    account, floor) is for logs only.
  - New `lowCreditSummary(accounts, floor)` renders the operator detail.
  - New `cachedCredits(id)` exposes the last probed balance.
- `sunoError.ts`
  - New `isDefiniteCreditExhaustion(err)`: true only for an explicit
    `not_enough_credits`-style `error_type` or message. `isInsufficientCreditsError`
    keeps its broad "any 402" meaning for retry classification.
- `server.ts`
  - `noteAccountCreditFailure(id, err)` zeroes the cached balance only on a
    definite credit exhaustion, or when the cached balance is already at/below
    the floor; otherwise it logs the 402 and keeps the balance.
  - `failOnPoolExhaustion(job, err)` ends the job with the clean message (and the
    balances in `app.log.warn`) instead of wrapping it as an attempt failure.

## Files touched

- `musicapi/src/pool.ts`
- `musicapi/src/sunoError.ts`
- `musicapi/src/server.ts`
- `musicapi/test/pool.test.ts`
- `musicapi/test/suno-error.test.ts`

## Migration/deploy

- No migration. API-only change; restart the musicapi process to pick it up.
- No env or admin setting added; existing `SUNO_MIN_CREDITS` (floor) and the
  `low_credits` alert keep their meaning. The alert's default threshold (50)
  already sits above the floor (10), so operators are paged before dispatch
  starts refusing work.

## Tests

- `npx tsc --noEmit` — clean.
- `npm run test:unit` — 124 passing, including the new cases: only a
  credit-specific 402 is a definite exhaustion; a bare/restricted 402 is not;
  `lowCreditSummary` lists every drained account; `PoolCreditExhaustedError`
  keeps account labels out of `message` and in `detail`.

## Follow-ups

- Confirm the production pool's per-account balances (admin → Accounts). This
  change makes the failure honest; it does not top up a genuinely drained pool.
- Consider surfacing "capacity exhausted" as a distinct job status/code so the
  playground can show a "retry later" hint instead of a generic error.
