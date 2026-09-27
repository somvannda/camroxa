# Web credit card splits the wallet balance instead of stale grant lots

**Date:** 2026-09-27
**Branch:** `fix/music-web-credit-merge-v2`
**Surfaces:** music_web
**Status:** implemented

## Summary

The account credit card derived the monthly / daily / top-up breakdown from
wallet **grant lots** (`credit_wallet_lots.remaining_credits`). Lots are only
zeroed when they **expire** — spending debits `credit_wallets` and never the lot
— so every lot reported the amount originally **granted**, not what was left.
Paid and free users alike saw `grant_remaining`, `monthly_credits_used`,
`topup_credits`, `daily_free_used`, and the breakdown computed from that stale
figure (for example, a 100/month plan showing 0 used after 40 credits had been
spent, or a top-up being hidden behind a full grant lot).

`mergeV3CreditBalance` now splits the **authoritative wallet balance**
(`/api/v3/me/credits` → `balance_credits`, which reads the shared
`credit_wallets` table) into the daily, monthly, and top-up pots. `total_credits`
was already correct and is unchanged.

## Product impact

- The credit card shows real usage: `Used` and `Remaining` for the monthly grant
  reflect credits actually spent this period, not the amount granted.
- Top-up credits are no longer masked by a full monthly grant lot, so the
  `Top-up` line appears as soon as the balance exceeds the monthly pool.
- The Free daily grant shows the credits left today (expiring first), matching
  the header number.

## Technical impact

- New `music_web/src/lib/credit-merge.ts` exports the pure
  `splitCreditBalance(total, dailyLimit, monthlyPool)` helper (zero imports, so
  it is unit-testable with `node --test`). It consumes the expiring daily grant
  first, then the monthly grant, then top-ups, and never returns negatives.
- `mergeV3CreditBalance` in `music_web/src/lib/subscription-api.ts` now maps
  `balance_credits` through that helper; the `lots` field of the V3 wallet view
  is no longer read. The `v2` argument remains an optional fallback for fields
  V3 omits (`daily_free_limit`, `monthly_credits`) and for
  `current_period_end` / `reset_at`.

## Files touched

- `music_web/src/lib/credit-merge.ts` (new)
- `music_web/src/lib/credit-merge.test.ts` (new)
- `music_web/src/lib/subscription-api.ts`

## Migration / deploy

- Frontend only; no DB migration, no settings change.
- Deploy with the normal `music_web` build; sandbox first.

## Tests

- `music_web/src/lib/credit-merge.test.ts` — 7 cases over `splitCreditBalance`:
  free daily grant vs stale lot, monthly usage from balance, top-up above the
  monthly pool, daily-spent-before-monthly ordering, empty balance, V2 pool
  fallback, negative-balance clamp.
- Full `music_web/src/lib` suite passes (54 tests, 14 suites).

## Follow-ups

- None for this fix. The legacy `web_music_free_daily_limit` /
  `web_music_free_daily_credits` settings cleanup is tracked separately.
