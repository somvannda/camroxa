# CutLuy KHQR in the music-web pay modal

**Date:** 2026-08-20  
**Surfaces:** platform_api, music_web

## Summary

CutLuy checkout pages send `X-Frame-Options: sameorigin`, so the pay modal iframe is always blank. Purchase now returns CutLuy’s Bakong `qr_string`, and music web draws that KHQR in our modal. “Open full page” remains as a fallback.

## Product impact

**Before:** Pay showed a white box and a console frame error.

**After:** The KHQR appears in the Camxora modal. Users scan with Bakong or a bank app. Status polling is unchanged.

## Technical impact

- Subscription purchase now forwards `qr_string` to the client (it was dropped in `subscription_service`).
- `extract_cutluy_qr_string` also reads CutLuy’s `qr_string` field and any `000201…` EMV string. GET `/v1/payments/{id}` is a fallback only; CutLuy omits KHQR on GET.
- If create omits `qr_string`, API GETs `/v1/payments/{id}`. GET failure does not fail the purchase.
- Timeouts and empty `expires_at` still map to 422 / `""` (not 500).
- No iframe.

## Files touched

- `platform_api/services/shared/cutluy_service.py`
- `platform_api/routers/v2_topups.py`
- `platform_api/routers/v2_subscriptions.py`
- `platform_api/tests/test_web_music_owned_checkout.py`
- `music_web/src/components/khqr-code.tsx`
- `music_web/src/components/cutluy-checkout-modal.tsx`
- `music_web/src/lib/subscription-api.ts`
- `music_web/src/components/topup-modal.tsx`
- `music_web/src/components/pricing-modal.tsx`
- `music_web/src/components/pricing-page-client.tsx`
- `music_web/src/components/subscription-section.tsx`
- `music_web/package.json`
- `scripts/deploy/hotfix_music_web_mobile_khqr_production.py`

## Migration/deploy

No schema change. Sandbox: API file hotfix + music_web rebuild. Production: file-scoped API upload + music_web rebuild (`scripts/deploy/hotfix_music_web_mobile_khqr_production.py`).

## Tests

`pytest platform_api/tests/test_web_music_owned_checkout.py`

## Follow-ups

If CutLuy omits `qr_string` on both create and GET, the modal shows “Open full page” instead of a QR.
