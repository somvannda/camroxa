# Music web owns checkout after CutLuy payment

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

Music web was embedding CutLuy’s hosted checkout URL, which reused the portal/desktop payment link. After KHQR pay, that hosted page redirected into user-portal onboarding (“Confirm your email”). The modal never polled, never granted credits on its own, and never returned to Create.

CutLuy is now credentials + KHQR only. Music web polls our API, fulfills credits if the webhook has not already run, shows a success popup, and Close returns to `/create`.

## Product impact

- Plan and top-up checkout stay on music web.
- After payment: success popup with credits added and a Close button to Create.
- Failed/expired payments show an error on music web instead of portal email confirm.

## Technical impact

- Web-music CutLuy payments no longer send `payment_link_id`.
- `GET /v2/subscriptions/payments/{payment_id}` and `GET /v2/topups/payments/{payment_id}` poll CutLuy and fulfill idempotently.
- Retrying checkout reuses a pending `web_subscriptions` row instead of inserting a second row (unique `user_id` was returning 500).
- Success popup shows `Starter (Monthly)` instead of `starter_monthly`. Account credit meter shows remaining / total including top-up credits (was used / monthly grant, so a pack looked like `0 / 1,000`).
- Checkout modal polls every 2s and replaces the KHQR frame on paid/failed.

## Files touched

- `platform_api/services/shared/cutluy_service.py`
- `platform_api/services/v2/subscription_service.py`
- `platform_api/services/v2/topup_service.py`
- `platform_api/routers/v2_subscriptions.py`
- `platform_api/routers/v2_topups.py`
- `platform_api/tests/test_web_music_owned_checkout.py`
- `music_web/src/components/cutluy-checkout-modal.tsx`
- `music_web/src/components/pricing-modal.tsx`
- `music_web/src/components/pricing-page-client.tsx`
- `music_web/src/components/topup-modal.tsx`
- `music_web/src/lib/subscription-api.ts`

## Migration/deploy

No migration. Deploy sandbox `platform_api` then `music_web`.

## Tests

- `platform_api/tests/test_web_music_owned_checkout.py`: payload omits payment link; poll fulfills subscription and top-up; already-active is idempotent.
