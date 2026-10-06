# Web-music paid upgrade grants the full allowance — 2026-10-06

**Surfaces:** `platform_api/` (v3 period grants).

## Why

The first fix for a Free→paid upgrade grand-total'd the period to the new plan's
allowance:

```
grant = allowance − already_granted   (1000 − 50 = 950, on top of the leftover)
```

That is wrong policy: credits a user already **spent on the Free plan** are
theirs and must not reduce the paid plan's allowance. Reported by
`iamduke1987@gmail.com`: paid $5 Starter, ended at `1000 − 49 (free usage) = 951`
instead of the full 1,000.

## What changed

`platform_api/services/v3/period_grant_service.py` — when a period lot already
exists and is **smaller** than the resolved plan's allowance (a Free→paid
upgrade), grant the **full** plan allowance on top instead of the difference.
The user's existing balance is untouched.

`platform_api/services/v3/store.py` — `grow_period_lot(lot_id, extra_units, *,
below_units)` adds `extra_units` once the lot sits below `below_units`; the guard
keeps repeated hourly `grant_maintenance` sweeps idempotent (no double-credit).
Replaces the earlier `top_up_period_lot` (which netted prior usage).

Result for a Free user with `leftover` credits upgrading to an `allowance` plan:

```
new_balance = leftover + allowance
```

Free balance is preserved; prior free usage is never deducted.

## Not prorated

Proration (charge/credit only the remaining days of the first month) was
considered and rejected: it does not apply to a Free→paid first purchase and
adds billing complexity. The paid period grants the full allowance.

## Verification

- `platform_api/tests/test_v3_period_grant.py` →
  `test_period_grant_grants_full_allowance_on_paid_upgrade`: Free lot (50) exists,
  upgrade to Starter 1000 → wallet `50 + 1000 = 1050`, one lot, idempotent.
- Focused suite (`test_v3_period_grant`, `test_v3_credits_only`,
  `test_credit_repo`, `test_web_music_owned_checkout`): 86 passed.

## Account correction

`iamduke1987@gmail.com` was corrected to exactly the plan allowance (1,000) so
the earlier `allowance − free_usage` grant (951) does not leave them short.

## Follow-ups

- `main` still lacks per-lot spend tracking (`atomic_deduct` FIFO /
  `consume_lots`), so `credit_wallet_lots.remaining_units` can read higher than
  the authoritative `credit_wallets.balance`.
- The production reconcile script still subtracts **all-time** net spend; scope it
  to the current billing period before ever applying it.
