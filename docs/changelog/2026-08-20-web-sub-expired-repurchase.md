# Web-music plan buy 500 after an expired subscription

**Date:** 2026-08-20  
**Surfaces:** platform_api

## Summary

`web_subscriptions.user_id` is unique. Plan checkout only reused **pending** rows, so an expired (or cancelled) subscriber hit a unique violation, then the UniqueViolation handler recursed until the API returned 500.

## Product impact

**Before:** Buying a plan after an expired subscription showed “An unexpected error occurred.”

**After:** Checkout reuses that row, sets it back to pending, and returns CutLuy KHQR as usual.

## Technical impact

- `_upsert_pending_subscription` treats `pending`, `expired`, `cancelled`, and `past_due` as reusable.
- UniqueViolation updates the existing non-active row; it does not recurse.

## Files touched

- `platform_api/services/v2/subscription_service.py`
- `platform_api/tests/test_web_music_owned_checkout.py`
- `platform_api/CHANGELOG.md`
- `scripts/deploy/hotfix_web_sub_expired_repurchase_production.py`

## Migration/deploy

No schema change. File-scoped API upload + `camxora-api` restart.

## Tests

`pytest platform_api/tests/test_web_music_owned_checkout.py`

## Follow-ups

None.
