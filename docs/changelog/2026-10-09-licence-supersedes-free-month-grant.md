# Licence grant supersedes a lingering Free month lot

**Date:** 2026-10-09
**Branch:** `fix/credit-free-lot-superseded-by-licence`
**Surfaces:** platform_api
**Status:** implemented (tests pass); sandbox/production deploy pending

## Summary

A licence **lapse → renew** could leave an account holding **two live `grant`
lots**: the Free plan's calendar-month lot (the lapse window was reconciled as
Free) plus the licence's activation-anchored monthly lot minted on renewal. This
trips the daily `CREDIT INVARIANTS` alert ("multiple live grant lots") and hands
a licensed account a small duplicate Free allowance.

Observed on production for `tepchanpanharith@gmail.com`:

- Free calendar-month lot: `period_start=2026-10-01`, 50 cr, remaining 50,
  created 2026-10-05 (by `_clawback_stacked_period_grant.py` while the licence
  was lapsed).
- Licence lot: `period_start=2026-10-02`, 5,150 cr, remaining 5,150,
  created 2026-10-07 (licence renewed).

The 5,150 is correct; the 50 is a superseded artifact.

## Root cause

`PeriodGrantService.ensure_period_grant()` only expires lots that are **past**
`expires_at` (`expire_unused_grants`). The Free month lot stays live until the
next month boundary, so when the licence grant is minted the two coexist — the
`credit_wallets`/`credit_wallet_lots` ledger has no notion that the licence
allowance *supersedes* the Free one.

`scripts/deploy/_clawback_stacked_period_grant.py` cannot repair this class: its
target SQL excludes users with an active licence.

## Fix

When `ensure_period_grant()` runs for a licence/subscription account
(`monthly_allowance=False`), retire any live Free calendar-month `grant` lot
before minting the licence allowance:

- `V3BillingStore.live_grant_lots_at_period(user_id, period_start, *,
  exclude_period_start)` — live (unspent, unexpired) `grant` lots at a period,
  with the licence's own lot excluded.
- `PeriodGrantService._revoke_superseded_free_grant(user_id, *,
  licence_period_start)` — claws each live Free month lot's remaining credits
  (`v3_free_grant_superseded`) and zeroes the lot, mirroring
  `expire_unused_grants`. Idempotent: spent/expired lots are skipped, so repeat
  sweeps are no-ops.
- `usage_transaction_labels`: label `v3_free_grant_superseded` → "Free grant
  superseded".

The guard runs on the hourly grant-maintenance sweep and on every
`ensure_period_grant()` call, so it self-heals existing accounts on the next
tick as well as preventing recurrence.

## Files touched

- `platform_api/services/v3/store.py`
- `platform_api/services/v3/period_grant_service.py`
- `platform_api/services/usage_transaction_labels.py`
- `platform_api/tests/test_v3_period_grant.py`
- `scripts/deploy/diag_prod_credit_grant_lots.py` (read-only diagnostic)

## Tests

- New `test_licensed_renewal_revokes_lingering_free_month_grant`: a live Free
  month lot + a licensed context → `ensure_period_grant` claws the Free lot to
  zero, mints the licence lot, and leaves exactly **one** live grant lot.
- `platform_api/tests/test_v3_period_grant.py` + `test_period_grant_carryover.py`:
  **12 passed**.
- Credit/billing/grant/ledger selection: **376 passed**.

## Deploy / follow-up

- No schema migration, no settings change. Deploy `platform_api` and restart
  `camxora-api` (and workers). Sandbox first; production only on explicit
  request.
- Verify: for the affected account, a forced `ensure_period_grant` should claw
  the 50-cr Free lot and leave one live lot; the daily invariant alert should
  stop firing.
- The existing production 50-cr Free lot is left in place until the guard runs
  for that user or it expires at the month boundary (2026-11-01 00:00 +07).
