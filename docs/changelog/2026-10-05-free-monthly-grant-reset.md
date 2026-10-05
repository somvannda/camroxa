# Free monthly grant reset (stop daily restacking)

**Date:** 2026-10-05
**Branch:** `fix/web-music-free-monthly-grant-stacking`
**Surfaces:** platform_api
**Status:** implemented + deployed (sandbox and production, 2026-10-05); stacked balances reconciled

## Summary

A license-less **Free** account was minted a fresh `v3_period_grant` **every
day**, not once per month. `PeriodGrantService.ensure_period_grant()` anchored
the monthly allowance to `billing_today()` for any user without an active
license/subscription context, while each grant lot stayed valid for the whole
billing cycle (`billing_cycle_days`, 30). The grants therefore stacked: a Free
wallet grew ~50 credits/day while unused, instead of resetting each month.

Observed on production (`music.camxora.com`, `camxora_platform`): the Free plan
is configured **50 credits / month, daily 0** (admin-set, see
`docs/changelog/2026-08-28-credit-reset-label-period.md`), yet the wallet held
**235** credits built from daily grants on 09-24, 09-25, 09-30, 10-04 and
10-05 — the "185 → 235 overnight" report.

## Product impact

- A license-less Free account now receives **one** monthly allowance per
  calendar month, anchored to the first day of the billing month
  (`Asia/Phnom_Penh`).
- The grant now expires at the **next month start**, so unused Free credits roll
  off at the period boundary instead of lingering for a full 30 days.
- Licensed plans are unchanged: they keep the activation-anchored billing period.
- Daily Free plans (`daily_credits > 0`) are unchanged (`ensure_period_grant`
  no-ops; `ensure_daily_grant` mints the daily, non-stacking lot).

## Technical impact

- `platform_api/services/v3/period_grant_service.py`:
  `ensure_period_grant()` now defaults `period_start` to `billing_month_start()`
  (was `billing_today()`) and sets `monthly_allowance=False` only when an active
  subscription context supplies a real billing period. The calendar-month path
  expires the lot at `next_billing_month_start(from_date=period_start)`.
- Imports `billing_month_start` / `next_billing_month_start` from
  `services/billing_calendar.py` (the helper already documented monthly Free
  rollover at the calendar-month boundary).

## Files touched

- `platform_api/services/v3/period_grant_service.py`
- `platform_api/tests/test_v3_period_grant.py`

## Data reconciliation

- `scripts/deploy/_clawback_stacked_period_grant.py` (dry-run by default,
  `--apply` to write) reconciles already-stacked Free wallets. It keeps one
  month's allowance (`plans.monthly_credits`, 50) and preserves non-grant
  credits (`quota_conversion`, packs, admin) by capping the claw at the
  spend-adjusted grant portion. It zeroes the stacked `grant` lots and leaves a
  single current-month lot so later expiry cannot double-claw. Idempotent — a
  rerun reports `affected_users 0`.
- Applied to production: **7** license-less Free accounts reconciled (e.g. the
  reported `iamduke1987@gmail.com` 235 → 50). Verified `ensure_period_grant`
  is a no-op on repeat calls and the grant is anchored to the month start.

## Migration / deploy

- No schema migration, no settings change. Deploy `platform_api` and restart
  `camxora-api` (and workers). Sandbox first; production only on explicit request.
  Deployed to sandbox and production on 2026-10-05.

## Tests

- `platform_api/tests/test_v3_period_grant.py`: new
  `test_period_grant_anchors_license_less_free_to_calendar_month` (one grant per
  month, month-start anchor, next-month expiry, re-grant next month) and
  `test_period_grant_uses_license_cycle_when_subscribed` (licensed accounts keep
  the activation anchor). Suite: **23 passed**.
- Deploy-time verification (`ensure_period_grant` called three times for a
  license-less Free account): anchor `2026-10-01`, repeat calls `already_granted`,
  no wallet drift, expiry at the next month start.

## Follow-ups

- Push the branch so the deployed code has a reproducible commit (not yet pushed).
