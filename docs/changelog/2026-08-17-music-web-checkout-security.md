# Music web checkout and top-up security tightening

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

Checkout and top-up now refuse fulfillment unless the CutLuy payment is the one bound to the caller’s pending row. Client-supplied return URLs and iframe checkout URLs are allowlisted so a paid KHQR cannot activate a swapped plan or redirect into a third-party page.

## Product impact

- Paying an old KHQR after changing plan/pack no longer activates the new (usually more expensive) row.
- Hidden or non-web-music plans/packs cannot be purchased from the public API.
- Status polling is rate-limited so it cannot be used to hammer CutLuy.

## Technical impact

- Fulfill SQL requires `status = pending` and `external_*_id = payment_id`. Webhooks look up by payment id, not metadata `subscription_id` / `topup_id`.
- Amount is checked when CutLuy reports one; payment ids are sanitized before they are interpolated into CutLuy URLs.
- `success_url` / `cancel_url` are rewritten to music-web origins (`music.camxora.com`, sandbox, localhost).
- Checkout iframe only loads `https://*.cutluy.com` with a restricted sandbox.
- Purchase: 8/min. Status poll: 45/min.

## Files touched

- `platform_api/services/v2/payment_security.py`
- `platform_api/services/v2/subscription_service.py`
- `platform_api/services/v2/topup_service.py`
- `platform_api/services/shared/cutluy_service.py`
- `platform_api/routers/v2_subscriptions.py`
- `platform_api/routers/v2_topups.py`
- `platform_api/middleware/rate_limit.py`
- `platform_api/tests/test_payment_security.py`
- `platform_api/tests/test_web_music_owned_checkout.py`
- `music_web/src/lib/subscription-api.ts`
- `music_web/src/components/cutluy-checkout-modal.tsx`

## Migration/deploy

No schema change. File-scoped sandbox hotfix of the API and music-web files above. Production stays untouched until asked.
