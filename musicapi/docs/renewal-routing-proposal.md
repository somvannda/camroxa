# Proposal: how routing should treat past-due / paused Suno plans

**Status:** proposal — no behaviour change. Nothing in this document is implemented.
**Date:** 2026-10-25
**Context:** follow-up to #445 (subscription badges), #446 (persisted renewal
date), #447 (plan cost), #448 (allowance usage + annual pricing).

## The question

A paid Suno plan that is **past due**, **paused**, or **scheduled to pause**
keeps serving generations from its remaining balance but will never refresh its
credits. Today the console badges those accounts (#445) and the alert loop raises
`subscription_past_due`, but dispatch ignores the flags entirely:
`orderForDispatch()` ranks by `preferFree`, over-cap, credits and load, and
`pickFrom()` only drops an account under the credit floor or a 429 cooldown.

Should dispatch deprioritise or skip a flagged account?

## What the live pool looks like (2026-10-25, production probe)

Read-only `AccountPool.listHealth()` snapshot over SSH — 10 accounts, the same
call the alert loop makes.

| | count | credits |
|---|---|---|
| paid (Premier) | 3 | 5,840 |
| free | 7 | 692 |
| **flagged** (past due / paused / pause-scheduled) | **0** | — |

Per-account detail worth noting:

| account | plan | credits left | period usage | renews |
|---|---|---|---|---|
| ksomvannda@gmail.com | Premier | **50** | 10,000 / 10,000 | 2026-11-04 |
| iamduke1987@gmail.com | Premier | 2,650 | 7,350 / 10,000 | 2026-11-07 |
| kduke168@gmail.com | Premier | 3,140 | 6,860 / 10,000 | 2026-11-17 |
| 7 free accounts | free | 92–100 each | 0–10 / 100 | — |

### Findings

1. **No evidence yet.** Zero accounts carry any subscription flag right now, so
   there is nothing to justify a routing change today. Any rule we add would be
   guesswork about a state we have never observed.
2. **Paid accounts are ~89% of pool credits** (5,840 of 6,532). Each paid account
   is roughly a third of the *usable* generation capacity — free accounts hold
   only 100 credits each. Excluding one on a transient flag is expensive.
3. **The risk is already material without flags.** `ksomvannda@gmail.com` is at
   50 credits with 10,000/10,000 used; `belowCreditFloor(50)` is false with the
   default `SUNO_MIN_CREDITS=10`, so it stays selectable and will serve a few
   more jobs before hitting 402s. That is a credit-floor question, not a
   subscription one — see *Related* below.

## Options

### A. Alert only (today)
Keep dispatch unchanged; rely on `subscription_past_due` + the badge.
- **Cost:** none. **Risk:** a drained flagged account can still be picked, and
  the failure surfaces as a 402 (`markCreditExhausted` then zeroes it for the
  cache TTL).
- **Verdict:** acceptable while flags are unobserved.

### B. Deprioritise, never exclude *(recommended)*
Add a subscription term to the `orderForDispatch` rank tuple, below the
existing "funded / not over cap" terms but above the credit tie-break:

```
rank = [
  preferFree && paid ? 1 : 0,
  atMaxPerAccount ? 1 : 0,
  pastDue || paused || pauseScheduled ? 1 : 0,   // new
  creditAware ? -credits : 0,
  load,
]
```

- Flagged accounts are only chosen when nothing better is left — the pool never
  shrinks, so a transient `is_past_due` costs nothing but latency in the worst
  case.
- Pure-function change in `src/pool.ts`; trivially unit-testable with the
  existing `test/pool.test.ts` helpers.

### C. Hard skip
Exclude flagged accounts from `pickFrom()` entirely.
- **Rejected for now:** a transient flag (card retry, dunning) would remove ~33%
  of paid capacity and push load onto the remaining accounts. Revisit only if
  telemetry shows flagged accounts actually fail.

### D. Conditional skip
Skip only when `paused || pauseScheduled` **and** credits are below the floor —
i.e. when the account has nothing to lose.
- Reasonable, but it is a special case of B with extra branches; not worth the
  complexity until B proves insufficient.

## Recommended sequence

1. **Telemetry first (prerequisite).** Persist the flags so transitions
   accumulate: migration `0041` adding `suno_accounts.past_due`,
   `paused`, `pause_scheduled`, `flags_observed_at`, written by the same
   conditional-update path as `renews_on` (#446). Without history we cannot tell
   a real lapse from a one-tick blip.
2. **Observe for ~1 week.** Count transitions per account and correlate job
   failures (`jobs.status='error'`, 402s) with flagged windows.
3. **Then implement B** with a unit test, and only consider C/D if the data
   shows flagged accounts failing while still being selected.

### Decision criteria for step 3

| Observation | Action |
|---|---|
| Flagged accounts keep generating successfully (>95% of attempts) | Keep A; the flag is cosmetic |
| Flagged accounts fail with 402/captcha >20% of attempts | Implement B |
| A flagged account is *preferred* by `balanced` because it still has credits | Implement B immediately — that is the failure mode we care about |
| `pauseScheduled` never appears in a week | Drop it from the dispatch rule |

## Related, and independently worth doing

- **Credit floor vs plan scale.** `SUNO_MIN_CREDITS` defaults to 10 against a
  10,000-credit Premier plan. An account at 50 credits is effectively dry but
  still selectable. Consider a percentage-of-allowance floor (e.g. skip below 1%
  of `monthly_limit`) rather than an absolute one, evaluated only when
  `monthly_limit` is known.
- **Free-plan allowance is rendered too.** Suno reports `monthly_limit = 100`
  for free accounts, so the "N / 100 used" line added in #448 appears for them as
  well — accurate, but it contradicts that changelog's "free accounts keep a bare
  balance" wording. Behaviour is fine; the note is corrected in this PR.

## Non-goals

- No routing change in this PR.
- No new outbound Suno calls: everything above reads the existing 30 s
  `billing/info` cache.
- No change to the alert thresholds or the badges shipped in #445.
