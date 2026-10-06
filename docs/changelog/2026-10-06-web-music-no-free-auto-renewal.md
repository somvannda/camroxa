# Web-music subscriptions no longer auto-renew for free — 2026-10-06

**Surfaces:** `platform_api/` (web subscription maintenance).

## Why

CutLuy is a **one-time KHQR** gateway — it does not charge on a schedule. But the
web-subscription maintenance loop treated an ended period as a renewal:

- `main.py` runs `SubscriptionService.process_due_subscriptions()` every 15 minutes.
- For each `web_subscriptions` row with `status='active' AND current_period_end <= NOW()`,
  `reset_quota_if_needed()` advanced `current_period_start/end` by another cycle,
  reset `monthly_credits_used`, re-granted `monthly_credits_granted`, and called
  `_sync_v3_period_grant()` — **with no payment and no renewal charge**.

Net effect: every paid web subscriber renewed **indefinitely for free** (monthly
plans monthly; yearly plans yearly, plus the 30-day monthly credit refresh inside
the free-extended year) until they manually cancelled.

## What changed

`platform_api/services/v2/subscription_service.py` — `reset_quota_if_needed()` no
longer extends. When `current_period_end <= now` it marks the row `expired` and
returns; no period advance and no credit grant. The yearly mid-term monthly-credit
refresh still runs while `current_period_end > now`.

Entitlement already self-heals: `resolve_charge_plan()` only returns a paid web
plan while the subscription is `active` **and** `current_period_end > NOW()`, so an
expired user falls back to the Free plan. Re-subscribing reuses the row
(`_REUSABLE_CHECKOUT_STATUSES` includes `expired`).

## Impact

A paid period now ends at `current_period_end`. To continue, the user buys again
(a new checkout). Cancelling still works as before.

## Verification

- `platform_api/tests/test_web_music_subscription_credit_reset.py`:
  - `test_reset_quota_if_needed_expires_at_period_end` — ended period → `expired`,
    no re-grant.
  - `test_reset_quota_if_needed_monthly_before_period_end_does_nothing`.
  - Yearly mid-cycle refresh tests unchanged.
- Full backend suite: 3169 passed (2 pre-existing, unrelated `test_media_router.py`
  failures).

## Follow-ups

- **Build the web renewal flow (planned):** before expiry, offer a new KHQR
  checkout (`GET/POST /renewals/web-subscription`, 7-day window anchored to
  `web_subscriptions.current_period_end`), extend only on a verified payment, add
  `renewal_alert` for web subs, and a `music_web` reminder banner + email.
- **Reconcile** properties already extended for free: review the paid web
  subscribers and decide grandfather vs expire.
- Credit-period anchoring is still calendar-month; the renewal flow should move it
  to the subscription period.
