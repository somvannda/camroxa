# Admin quota "Used" for songs is now authoritative

**Date:** 2026-10-14  
**Surfaces:** platform_api

## Summary

The admin **Plan quota (this period)** card and the user-facing quota display now read the
**authoritative** song count — real `songs` rows with `status='suno_success'` — matching what
enforcement (`_enforce_plan_quotas`) already uses.

## Problem

`QuotaTopupService._used_for_kind("music")` and
`quota_display_service.get_monthly_quota_status(quota_field="songs")` read the incremental
`usage_tracking.monthly_count`. Since the credits-only (v3) migration, generation
short-circuits before `reserve_operation_quota()`:

```python
# usage_enforcement_service._reserve_operation
v3_op = await self._v3_op_if_enabled(operation_type)
if v3_op is not None:
    held = await self._charge_via_v3(user_id, operation_type)  # charges credits
    return OperationHold(..., source="v3")                     # never writes usage_tracking
await self.reserve_operation_quota(...)                        # legacy-only meter increment
```

So `usage_tracking` is no longer incremented, and the card showed **Used = 0 / full
Remaining for every user** — while the monthly song cap was still enforced from the real
`songs` table. An admin could see "Remaining 450" for a user who is actually blocked with
`MONTHLY_QUOTA_EXCEEDED`.

## Fix

- `platform_api/services/quota_topup_service.py` — `_used_for_kind` gained a `period_end`
  arg; for `kind == "music"` it calls `count_generated_songs_for_period` when the repo
  exposes it (fallback to the incremental counter). `grant()` and `build_period_snapshot()`
  now pass `period_end`.
- `platform_api/services/quota_display_service.py` — `get_monthly_quota_status` uses the
  authoritative count for `quota_field == "songs"`.
- **No schema/migration change.** Drafts / images / video / merge still use the incremental
  counter (no authoritative source yet); that is a separate follow-up.

## Tests

- `platform_api/tests/test_quota_topup_service.py` — grant + snapshot use the authoritative
  song count.
- `platform_api/tests/test_quota_display_service.py` — songs remaining uses the authoritative
  count while drafts keep the counter.
