# Web-music subscription renewal flow (backend) — 2026-10-06

**Surfaces:** `platform_api/` (subscriptions router + v2 SubscriptionService + migration).

## Why

CutLuy is a **one-time KHQR** gateway, so a paid web-music period cannot be
charged automatically. After the stop-free-auto-renewal fix (PR #353), an ended
period simply expires and the user drops to Free — with no way to pay for the
next period except re-buying from the pricing page. This adds a proper renewal
checkout.

## What changed

- **Migration** `135_web_subscription_renewal`: adds
  `web_subscriptions.pending_renewal_payment_id` (+ index) and
  `renewal_reminder_sent_at` (reserved for the email reminder).
- **`platform_api/services/v2/subscription_service.py`**
  - `RENEWAL_WINDOW_DAYS = 7`.
  - `get_renewal_offer(user_id)`: returns the user's renewable plan and window
    (`renewable` within 7 days of `current_period_end`, or once expired);
    `None` for Free / non-paid.
  - `create_renewal_checkout(...)`: creates a CutLuy KHQR checkout for the user's
    own plan and records `pending_renewal_payment_id`.
  - `get_renewal_status(...)`: polls CutLuy; on a verified, amount-matched
    `paid` it extends the period; clears the pending id when the KHQR expires.
  - `_fulfill_renewal(...)`: extends **one cycle** — stack early renewals from
    `current_period_end`, start from now when expired — resets the monthly grant,
    reactivates, and re-syncs the v3 grant. Idempotent on
    `pending_renewal_payment_id`.
  - `_handle_payment_completed`: also fulfills renewals bound by
    `pending_renewal_payment_id` (with user + amount verification).
- **`platform_api/routers/v2_subscriptions.py`** endpoints (auth + rate-limited):
  - `GET  /subscriptions/renewal` — offer/window.
  - `POST /subscriptions/renewal` — start the KHQR checkout.
  - `GET  /subscriptions/renewals/{payment_id}` — poll/fulfill.

## Behaviour

- Renewal is only offered within 7 days of `current_period_end`, or once expired.
- The period extends **only** on a verified CutLuy `paid` event with a matching
  amount; an early renewal stacks from the current period end (no lost days).

## Verification

- `platform_api/tests/test_web_music_subscription_renewal.py`: offer window
  open/closed, Free → `None`, `_fulfill_renewal` stacking / expired→now /
  idempotency. Focused suites: 15 + 42 passed.
- Router imports and registers `/subscriptions/renewal` (+ `renewals/{id}`);
  migration `135_web_subscription_renewal` chains from
  `134_streaming_upload_job_dedup`.

## Follow-ups

- `music_web` UI: renewal banner (window-aware) + KHQR checkout via
  `CutluyCheckoutModal`, polling `/subscriptions/renewals/{id}`.
- Email reminder before expiry (`renewal_reminder_sent_at` reserved).
- Extend `renewal_alert` (`subscription_renewal_alert_service`) to web subs.
- Move credit-period anchoring from calendar-month to the subscription period.
