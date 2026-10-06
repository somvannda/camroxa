# Reconcile script: scope spend to the current period — 2026-10-06

**Surfaces:** `scripts/deploy/_reconcile_web_music_paid.py`.

## Why

The paid-web reconcile computed `net generations` as **all-time** v3 debits minus
refunds, then set `wallet = allowance + non_grant − net_spend`. For a monthly plan
that over-deducts: it charges the current allowance for spend from earlier
periods. Observed on `iamduke1987` — the script wanted to **debit 165** (951 → 786)
because it subtracted 214 lifetime credits against a 1,000 allowance, even though
only ~49 were spent in the current period.

## What changed

- `_target_units()` now resolves a `period_start` (the subscription's
  `current_period_start` when active, else the calendar month start for a lapsed /
  Free user) and filters the spend query with `created_at >= period_start`.
- Docstring updated to state the period scope.

This makes re-running the reconcile safe (idempotent and period-correct) instead
of harming users.

## Verification

- `py_compile` OK.

## Note

The script is a manual companion tool; this does not change the shipped renewal
flow. Dry-run before any `--apply`, as always.
