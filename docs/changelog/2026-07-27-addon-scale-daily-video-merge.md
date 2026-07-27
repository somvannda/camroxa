# Active add-on slots scale account-wide daily video/merge

**Date:** 2026-07-27  
**Status:** implemented (sandbox + production deployed)

## Summary

Account-wide daily video and merge caps now scale with active profile add-on slots the same way period quotas do (`quota_channels / plan_channels`). Per-channel daily song/image/draft limits stay unchanged (total capacity still rises via more channels). Quota-status display uses the scaled daily limits.

## Product impact

**Before:** 2ch plan + active +2 add-on doubled period video/merge but daily video stayed 10 and daily merge stayed 1.  
**After:** same user gets daily video **20** and daily merge **2** once add-on onboarding activates slots.

## Technical impact

- `effective_daily_limit_for_operation()` in subscription entitlement service
- Usage enforcement `_get_daily_limit` / daily bank path passes `addon_slots`
- `GET /credits/quota-status` daily video/merge fields use scaled limits

## Files touched

- `platform_api/services/subscription_entitlement_service.py`
- `platform_api/services/usage_enforcement_service.py`
- `platform_api/routers/credits.py`
- `platform_api/tests/test_subscription_entitlement_service.py`
- `platform_api/tests/test_video_merge_billing.py`
- `docs/changelog/2026-07-27-addon-scale-daily-video-merge.md`
- `platform_api/CHANGELOG.md`

## Migration / deploy

No migration. Deploy/restart `platform_api` (sandbox first).

## Tests

- Unit: add-on 0/2/4/8 scales video/merge dailies; per-channel dailies unchanged
- `test_video_merge_billing` asserts scaled `_get_daily_limit(..., addon_slots=2)`

## Follow-ups

- Wallet `subscription_covers_*` still uses unscaled base period limits (separate known gap).
