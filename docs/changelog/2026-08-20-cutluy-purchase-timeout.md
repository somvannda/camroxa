# CutLuy purchase 500 after provider outage

**Date:** 2026-08-20  
**Surfaces:** platform_api

## Summary

After CutLuy came back, pack purchase still failed. Sandbox logs showed two causes: CutLuy `ReadTimeout` was returned as a generic 500 (`An unexpected error occurred.`), and leftover pending top-up rows (no payment id) blocked later buys with 422 “Too many pending checkouts.”

## Product impact

**Before:** Buying a credit pack could show a generic 500, then keep failing after CutLuy recovered.

**After:** A provider timeout is a retryable 422. Stale pending rows without a CutLuy payment id are marked failed so the next buy can proceed. KHQR drawing is in `docs/changelog/2026-08-20-cutluy-khqr-modal.md`.

## Technical impact

- Map `httpx.TimeoutException` to `ValueError` so the router returns 422.
- Coerce missing `expires_at` to `""` so response validation cannot 500.
- Flatten nested CutLuy `data` only for `checkout_url` / payment id.
- Fail pending top-ups with a null payment id after 2 minutes, and immediately if CutLuy create raises.

## Files touched

- `platform_api/services/shared/cutluy_service.py`
- `platform_api/services/v2/topup_service.py`
- `platform_api/routers/v2_topups.py`
- `platform_api/routers/v2_subscriptions.py`
- `platform_api/tests/test_web_music_owned_checkout.py`

## Migration/deploy

Sandbox file-scoped API hotfix only. Production not deployed.

## Tests

`pytest platform_api/tests/test_web_music_owned_checkout.py`

## Follow-ups

Retry pack buy on `music.sandbox.camxora.com` after the hotfix. Complete or ignore the one remaining pending checkout that already has a CutLuy payment id.
