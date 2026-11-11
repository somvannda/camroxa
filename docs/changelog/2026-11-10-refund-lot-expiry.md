# Refund overflow gets a 30-day lot; every lot with room is filled

**Date:** 2026-11-10
**Branch:** `fix/refund-lot-expiry`
**Surfaces:** platform_api
**Status:** implemented (tests pass); not deployed

## Summary

`CreditRepository._restore_lots` looked at **one** live lot. If it was at its
granted cap, the whole refund was minted as a new `grant` lot with
`expires_at = NULL`. Because refunds prefer the newest pack lot — which is
normally full right after a purchase — every failed generation created another
permanent lot.

Production on 2026-11-10: **102 live `grant` lots with no expiry across 7
users**, 60 of them on `pengpheakdey02@gmail.com`. Those are the rows behind the
daily `CREDIT INVARIANTS` "multiple live grant lots" alert, and they contradict
the rule that every credit expires within 30 days (migration 177).

## Fix

- The refund now walks **every** live lot with room (pack first, then newest
  expiry), filling each up to its cap, before creating anything new.
- A genuine overflow lot is stamped `now + 30 days` instead of `NULL`, matching
  the rest of the credit model. A later purchase still extends it through
  `restamp_live_lots`.
- Full, expired and over-capacity lots are excluded in SQL, so the split helper
  only sees lots it can actually fill.

Nothing changes for the common case: a refund fits in the newest pack lot and no
new row is created.

## Tests

- New: fills two lots (50 + 50) and mints nothing; overflow gets an expiry
  between 29 and 31 days; the query skips full/expired lots and no longer uses
  `LIMIT 1`.
- Credit selection (`credit_restore_lots`, `credit_repo`, `credit_ledger`,
  `wallet_sync`, `pack_credit_expiry`, `credit_invariants`,
  `admin_topup_parity`, `free_monthly_grant_ledger`): **80 passed**.

## Follow-ups

- The 102 existing non-expiring lots are not touched by this change. They hold
  real refunded credits (the wallet was credited), so they should be stamped or
  merged — not deleted — in the data-repair step, before 2026-12-01.
- `credit_invariants` still counts any `tag='grant'` lot. Once the data is
  repaired it should count period/free-monthly grants (`period_start IS NOT
  NULL`) so refund artifacts cannot trip it again.
