# Multi-channel plan quota charging (songs + draft display)

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/quota-charging-multi-channel`

## Summary

Dual-channel Suno packages were metering daily song usage only on the Primary (OK) channel, so Secondary (ALT) stayed at `0/70` even when both channels received tracks. Draft slot metering was also Primary-only (lyric+title+album ≈ `2N+1`), so Secondary drafts stayed at `0` while Primary looked “~2× songs.” Per-channel draft limits/usage were also missing from `/credits/quota-status` before this change.

## Point-by-point

| Point | Cause | Fix |
|-------|--------|-----|
| Songs only on Bass Drive (OK) | `_submit_song_to_suno` charged `music` only to `ok_profile_id` | After Primary charge, attribute Secondary **daily** music usage without doubling the monthly package meter |
| Drafts always `0/0` | `ChannelDailyQuota` / quota-status omitted daily draft fields; UI defaulted to 0 | Expose `daily_drafts_*` from plan + `usage_tracking` (`draft`); show on desktop + user portal |
| Drafts only on Primary; Secondary `0` | Batch draft deduct used `ok_profile_id` only | After Primary slot deduct, attribute the same daily draft slot count to Secondary (`include_monthly=False`); preflight reserves drafts on both channels. Slot math unchanged (`2N+1`) |
| Export/merge ~half (10 vs 20, 1 vs 2) | Account-wide meters; billing is per Progress/Video consume call with `channel_profile_id`. Half usually means only one channel’s export/merge path ran consume (images already billed both). | No API double-charge change; verified consume already accepts per-channel ids and sums account-wide. Re-check desktop that both OK+ALT rows call `/generation/video/consume` |
| Images correct on both | Per-channel image jobs already increment each profile | Unchanged (confirmed correct) |

## Technical notes

- `usage_tracking.increment_usage(..., include_monthly=False)` supports Secondary daily attribution.
- `UsageEnforcementService.attribute_secondary_daily_usage` for `music` and `draft`; refunds release Secondary daily on failure.
- Channel daily display uses `billing_today()` (Asia/Phnom_Penh), not `date.today()`.
- Draft “overcharge vs songs” is intentional slot metering (not a bug): lyric + title per song + one album.

## Files

- `platform_api/repositories/usage_tracking_repo.py`
- `platform_api/services/usage_enforcement_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/services/quota_display_service.py`
- `platform_api/models/schemas.py`
- `platform_api/routers/credits.py`
- `platform_api/tests/test_usage_tracking_repo.py`
- `platform_api/tests/test_quota_display_service.py`
- `camxora_python/shared/models/platform.py`
- `camxora_python/features/dashboard/widgets/daily_channel_quota_card.py`
- `user_portal/src/lib/quota.ts`
- `user_portal/src/app/dashboard/page.tsx`
- `user_portal/src/app/dashboard/credits/credits-panel.tsx`
