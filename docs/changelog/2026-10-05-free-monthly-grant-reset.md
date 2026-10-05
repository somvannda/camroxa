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

The same happened to **paid web subscribers** (`web_subscriptions` with no
license): they had no subscription context either, so their monthly allowance was
minted daily too. Licenses (desktop) were unaffected — they always anchored to the
license period.

Observed on production (`music.camxora.com`, `camxora_platform`): the Free plan
is configured **50 credits / month, daily 0** (admin-set, see
`docs/changelog/2026-08-28-credit-reset-label-period.md`), yet the wallet held
**235** credits built from daily grants on 09-24, 09-25, 09-30, 10-04 and
10-05 — the "185 → 235 overnight" report. Paid example: `creator_monthly`
(3,500/mo) held 16,647.5 credits from five daily grants.

Separately, `web_subscriptions.monthly_credits_granted` was a snapshot written at
purchase that was **never refreshed on renewal**, so after a plan edit the
subscription record disagreed with the plan/wallet (3,500 vs 2,300).

## Product impact

- A license-less Free account now receives **one** monthly allowance per
  calendar month, anchored to the first day of the billing month
  (`Asia/Phnom_Penh`).
- The grant now expires at the **next month start**, so unused Free credits roll
  off at the period boundary instead of lingering for a full 30 days.
- Paid web subscriptions get one grant per calendar month too (was daily).
- A plan edit takes effect from the **next billing cycle**: on renewal the
  subscription adopts the current plan's allowance. The credits already granted
  for the current period are never increased or reduced by a plan edit.
- Licensed plans are unchanged: they keep the activation-anchored billing period.
- Daily Free plans (`daily_credits > 0`) are unchanged (`ensure_period_grant`
  no-ops; `ensure_daily_grant` mints the daily, non-stacking lot).

## Technical impact

- `platform_api/services/v3/period_grant_service.py`:
  `ensure_period_grant()` now defaults `period_start` to `billing_month_start()`
  (was `billing_today()`) and sets `monthly_allowance=False` only when an active
  subscription context supplies a real billing period. The calendar-month path
  expires the lot at `next_billing_month_start(from_date=period_start)`.
- `platform_api/services/v3/period_grant_service.py` (licensed path): the grant
  lot now expires at the **period boundary** (`next_billing_midnight` after the
  period's last day) instead of `now + billing_cycle_days`. A previous period's
  unused lot therefore expires exactly when the next period starts and is clawed
  by `expire_unused_grants` before the new grant — no more two live lots across
  a licence renewal (observed on 3 desktop accounts).
- `platform_api/services/v2/subscription_service.py`: on monthly renewal
  (`reset_quota_if_needed`) the UPDATE now also writes
  `monthly_credits_granted = plan.monthly_credits`, so the subscription record
  follows the current plan from the next cycle instead of staying on the
  purchase-time value. The current period is untouched.
- Imports `billing_month_start` / `next_billing_month_start` from
  `services/billing_calendar.py` (the helper already documented monthly Free
  rollover at the calendar-month boundary).

## Files touched

- `platform_api/services/v3/period_grant_service.py`
- `platform_api/services/v2/subscription_service.py`
- `platform_api/tests/test_v3_period_grant.py`
- `platform_api/tests/test_web_music_subscription_credit_reset.py`
- `scripts/deploy/_clawback_stacked_period_grant.py`

## Data reconciliation

- `scripts/deploy/_clawback_stacked_period_grant.py` (dry-run by default,
  `--apply` to write) reconciles already-stacked wallets for **both** classes.
  It keeps one allowance — the Free plan's `monthly_credits` (50) for free users,
  the subscription's current-period `monthly_credits_granted` for paid web subs —
  and preserves non-grant credits (`quota_conversion`, packs, admin) by capping
  the claw at the spend-adjusted grant portion. It zeroes the stacked `grant`
  lots and leaves a single current-month lot so later expiry cannot double-claw.
  Idempotent — a rerun reports `changed=0`.
- It also **re-anchors** legacy (daily-dated) grant lots to the month start
  **without adding credits** (`claw=0`), so switching the anchor cannot mint a
  duplicate month allowance for an account that already holds one. Verified that
  no non-licensed account retains an off-month anchor, and that every reconciled
  balance was reduced or unchanged (never increased).
- Applied to production: **7** license-less Free accounts (e.g.
  `iamduke1987@gmail.com` 235 → 50) and **3** paid web subscribers
  (`sommakara84@gmail.com` 16,647.5 → 3,500 keeping the current-period allowance,
  `teangchunpanhavorn@gmail.com` worked 8,743.1 → 2,001,
  `touchphinnarith90@gmail.com` 5,707.5 → 1,000). Verified `ensure_period_grant`
  is a no-op on repeat calls and grants are anchored to the month start.

## Web-music paid audit + reconciliation (2026-10-05)

- Scope: `web_subscriptions` (plan_type `web_music`). Desktop/license plans
  (`desktop_pro`, incl. the $79 Monthly · 2-channel) are excluded.
- `scripts/deploy/_reconcile_web_music_paid.py` computes, per paid web user:
  `real = current-period allowance + non-grant credits (quota_conversion/pack/admin)
  - net generations (v3 debits minus v3 refunds)` and sets the wallet to it
  (recording a `v3_paid_web_reconcile` ledger row; idempotent). It skips accounts
  with no credit activity.
- Findings: web-music has **128 Free** users (303 credits held) and **5 active**
  paid subs — starter_monthly ×4, creator_monthly ×1 — plus 1 expired and 22
  pending (never paid). Signup credit is **0** (wallets are created at 0); the
  only free credit is the Free plan's 50/month.
- Applied: `sommakara84` 3500 → **2647.5**, `teangchunpanhavorn` 2001 → **1743**,
  `touchphinnarith90` 1000 → **657.5** (each nets out their generations);
  `pich.sou11` unchanged at **876** (lapsed period, back on Free);
  `brosean22` skipped (no credit activity).

## Migration / deploy

- No schema migration, no settings change. Deploy `platform_api` and restart
  `camxora-api` (and workers). Sandbox first; production only on explicit request.
  Deployed to sandbox and production on 2026-10-05.

## Tests

- `platform_api/tests/test_v3_period_grant.py`: new
  `test_period_grant_anchors_license_less_free_to_calendar_month` (one grant per
  month, month-start anchor, next-month expiry, re-grant next month) and
  `test_period_grant_uses_license_cycle_when_subscribed` (licensed accounts keep
  the activation anchor).
- `platform_api/tests/test_web_music_subscription_credit_reset.py`: new
  `test_reset_quota_if_needed_monthly_adopts_current_plan_credits` (renewal
  writes the current plan allowance into `monthly_credits_granted`).
- Credit/billing suite: **112 passed**.
- Deploy-time verification (`ensure_period_grant` called three times for a
  license-less Free account): anchor `2026-10-01`, repeat calls `already_granted`,
  no wallet drift, expiry at the next month start.

## Follow-ups

- Push the branch so the deployed code has a reproducible commit (not yet pushed).
