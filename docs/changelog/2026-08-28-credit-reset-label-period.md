# 2026-08-28 — Account credit reset follows daily vs monthly grant

Sandbox only. Production not touched.

## Summary

The music-web account card always said **Credit reset daily**, even when Admin set Free to monthly 50 / daily 0. The wallet also only returned a licensed plan, so Free users had no daily/monthly fields to drive the copy.

## Product impact

- Daily grant > 0 → **Credit reset daily**
- Daily = 0 and monthly grant > 0 → **Credit reset monthly**
- Both 0 → the reset line is hidden
- Blank pricing-feature fallbacks for Free monthly now say **Monthly credit reset** instead of daily

## Technical impact

- `/api/v3/me/credits` resolves the charge plan (license → paid web sub → active Free) and returns `reset_label`
- `/me/credits` also runs `ensure_period_grant` so a monthly Free grant is minted when daily is 0
- Music-web maps that label and no longer treats Free monthly credits as a paid subscription

## Files touched

- `platform_api/services/pricing_display.py`
- `platform_api/services/v3/credits_only_billing_service.py`
- `platform_api/services/v3/store.py`
- `platform_api/routers/v3_billing.py`
- `platform_api/routers/plans.py`
- `platform_api/routers/v2_subscriptions.py`
- `music_web/src/lib/subscription-api.ts`
- `music_web/src/lib/credit-display.ts`
- `music_web/src/components/credit-header.tsx`

## Migration/deploy

```
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/rebuild_music_web_sandbox.py
```

No migration.

## Tests

- `platform_api/tests/test_pricing_display.py`
- `platform_api/tests/test_v3_credits_only.py`
- `music_web/src/lib/credit-display.test.ts`

## Follow-ups

- Production after the user asks.
