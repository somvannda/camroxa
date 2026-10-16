# musicapi: credit-aware Suno account routing (use richer accounts first, drain together)

## Summary

Pool routing had gone credit-blind. `orderByLoad()` ranked eligible accounts by
routing preference, per-account in-flight cap, then least in-flight — credits
were only a hard floor (`belowCreditFloor` / `SUNO_MIN_CREDITS`). With a burst,
job counts were equalised across accounts but the *balances* were not: a job
counts the same whether it lands on an account holding thousands of credits or
one about to run dry, so an existing gap was preserved and the low account was
driven to a 402 while richer peers sat idle. A bare `pool.pick()` (several
routes pass no `load`) is even worse — with all loads at 0 the sort is stable,
so it always returned the first configured account.

Two operator asks that turn out to be the same mechanism: *use the account with
more credit first* and *keep all accounts at the same credit*.

## Product impact

- Account selection now prefers the highest-balance eligible account, so work is
  drawn from accounts that can afford it.
- `balanced` (default) reserves each in-flight job's estimated spend against the
  account's balance, so concurrent jobs spread across the pool and the accounts
  drain toward a common level instead of one being emptied first.
- No change to user billing or to which models/features an account may serve.

## Technical impact

- `src/config.ts`: new `CreditStrategy` type and `suno.creditStrategy`
  (`SUNO_CREDIT_STRATEGY`, default `balanced`) + `suno.creditReserve`
  (`SUNO_CREDIT_RESERVE`, default 10). An unset or unrecognized strategy value
  falls back to `balanced`, so a typo can't silently disable credit awareness.
- `src/pool.ts`:
  - New pure, exported `orderForDispatch()` — rank `prefer_free` → over-`maxPerAccount`
    → credit balance (highest first, skipped for `off`) → least in-flight. The
    credit term sits *above* load so job counts converge on the balances, not on
    equal counts. `orderByLoad()` is kept as the `strategy: "off"` wrapper.
  - New `reservedCredits` map with `reserveCredits()` / `releaseCredits()` and a
    private `effectiveCredits()`. A reservation is cleared whenever a fresh
    `billing/info` read arrives (that value already includes settled spend) and on
    `reload()`. `reserveCredits()` is a no-op unless the strategy is `balanced`.
  - New private `probeHealth()` / `orderCandidates()` / `pickFrom()` helpers;
    `pick`, `pickExcept`, `pickFeature`, and `pickFeatureExcept` all dispatch
    through the shared credit-aware path. Behavioral guarantees preserved: probe
    failures are still captured per account and surfaced as the last error, an
    unadvertised model is still attempted as a last-resort fallback, and the
    existing "no paid account" / "no credits" messages are unchanged.
- `src/runtimeSettings.ts`: `creditStrategy` (string) and `creditReserve`
  (number) added to the **Suno concurrency (jobs)** group and applied to `config`
  on save, so the strategy is editable from the admin console with no restart.
- `src/server.ts`: `markAccountStart` now reserves `config.suno.creditReserve`
  and `markAccountEnd` releases it.
- `test/pool.test.ts`: six new `orderForDispatch` cases (off == legacy ordering,
  off ignores credits, highest-balance first, `prefer_free` preserved, over-cap
  last, least-loaded tiebreak on equal balances).
- `musicapi/.env.example`: documented both new variables.

No schema change.

### Design note: `balanced` vs `max_first`

`balanced` and `max_first` produce the *same* ordering in `orderForDispatch`;
the ordering difference an operator might expect from a "pool average" cut is a
no-op (any above-average account already has more credits than any below-average
one, so a single-cut demotion cannot reorder versus a plain credit-desc sort).
The genuine distinction is the reservation: `balanced` reserves in-flight spend
so concurrent picks spread and converge; `max_first` reserves nothing and keeps
drawing from the richest account within each 30s window. `off` ignores credits
entirely (legacy behaviour).

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/runtimeSettings.ts`
- `musicapi/src/server.ts`
- `musicapi/test/pool.test.ts`
- `musicapi/.env.example`
- `docs/changelog/2026-10-16-musicapi-credit-aware-routing.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain
  (`sync_musicapi_sandbox.py` → `deploy_musicapi_production.py`).
- New optional env: `SUNO_CREDIT_STRATEGY` (default `balanced`) and
  `SUNO_CREDIT_RESERVE` (default 10). No `.env` change required. Both are also
  editable at runtime from **Admin → Settings → Suno concurrency (jobs)**, so the
  change is revertible without a redeploy (`creditStrategy = off`).

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run test:unit` (musicapi) → 82/82 pass, including the six new
  `orderForDispatch` cases.

## Follow-ups

- The reservation is in-process, so a second API node would under-count
  in-flight spend; fine for the current single-process deployment.
- Optional: persist the last `billing/info` read into the existing (currently
  unused) `suno_accounts.plan` / `credits_left` columns so routing still has a
  balance when `billing.info` momentarily fails (today the fallback is 0, which
  the floor treats as unusable).
- Because Suno allowance credits do not roll over and reset on each account's own
  billing date, strictly equalising balances is not the same as minimising waste;
  a future "drain the account nearest its reset" strategy would need per-account
  reset dates we do not currently fetch.
