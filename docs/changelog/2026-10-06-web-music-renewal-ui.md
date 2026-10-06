# Web-music renewal UI — 2026-10-06

**Surfaces:** `music_web/`.

## Why

The renewal backend (`GET/POST /api/v3/subscriptions/renewal`,
`GET /api/v3/subscriptions/renewals/{id}`) shipped in PR #355. CutLuy is
one-time, so periods now correctly expire — users need an in-app way to pay for
the next period before losing access.

## What changed

- `music_web/src/lib/subscription-api.ts`
  - `RenewalOffer` type + `fetchRenewalOffer()`.
  - `purchaseRenewal({ success_url, cancel_url })`.
  - `fetchRenewalCheckoutStatus(paymentId)`.
- `music_web/src/components/cutluy-checkout-modal.tsx`
  - `kind` accepts `'renewal'` and the status poller uses
    `fetchRenewalCheckoutStatus` for it (vs. subscription/topup).
- `music_web/src/components/subscription-section.tsx`
  - Loads the renewal offer; renders a banner when eligible + renewable
    (amber "renews soon" within the 7-day window, red once expired), shown on
    both the subscribed card and the not-subscribed state.
  - "Renew now" → `purchaseRenewal` → KHQR `CutluyCheckoutModal` in renewal mode.

## Behaviour

- The banner only appears inside the renewal window (7 days before
  `current_period_end`) or once expired, for paid plans.
- Renewal is a fresh KHQR charge; the period extends only after a verified
  payment (backend), stacking an early renewal from `current_period_end`.

## Verification

- `npx tsc --noEmit`: no errors (only the repo's pre-existing `.test.ts` `TS5097`).
- `npm test` (`node --test`): 50 passed.

## Follow-ups

- Email reminder before expiry (`renewal_reminder_sent_at` reserved).
- Extend `renewal_alert` to web subscriptions; credit-period anchoring.
