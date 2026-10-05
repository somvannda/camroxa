# Free monthly grant reset (stop daily restacking)

**Date:** 2026-10-05
**Branch:** `fix/web-music-free-monthly-grant-stacking`
**Surfaces:** platform_api
**Status:** implemented (local tests green; sandbox/prod not deployed)

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

## Migration / deploy

- No schema migration, no settings change. Deploy `platform_api` and restart
  `camxora-api` (and workers). Sandbox first; production only on explicit request.

## Tests

- `platform_api/tests/test_v3_period_grant.py`: new
  `test_period_grant_anchors_license_less_free_to_calendar_month` (one grant per
  month, month-start anchor, next-month expiry, re-grant next month) and
  `test_period_grant_uses_license_cycle_when_subscribed` (licensed accounts keep
  the activation anchor). Suite: **23 passed**.

## Follow-ups

- Existing stacked Free grants are already in `credit_wallet_lots`; they will be
  clawed back by `expire_unused_grants()` as each lot hits its original expiry.
  A one-off wallet reconciliation is optional and out of scope here.
