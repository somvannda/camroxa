# Progress filters: Active / Stage before Limit

**Date:** 2026-08-06  
**Status:** implemented (sandbox API deploy pending with this change)  
**Branch:** `bugfix/progress-filters-composition`

## Summary

Progress page Limit did not mean “N matching rows.” The API (and sometimes the client) sliced to Limit on a mixed-stage set, then Active only / Stage dropped rows — so **Active only + Limit 10** could show far fewer than 10 active runs even when many existed.

## Product impact

Filter order is now:

1. Date range (From / To)
2. Load + desktop overlays (effective stage)
3. **Active only** (hide Done / Completed; Error stays)
4. **Stage** (Export includes Converter; Merge includes Merger)
5. **Limit** (slice to N)

So **Active only + Limit 10** → up to **10 active** rows in the date window.  
**Stage=Music + Limit 10** → up to **10 Music** rows from the loaded set (over-fetched so Stage still has room).

Stats follow Active + Stage (before Limit). Meta still shows visible vs loaded counts.

## Technical impact

- Desktop Progress view over-fetches from `GET /progress` (up to `min(100, max(limit*5, 50))`), applies Active/Stage/Limit **after** overlays, and no longer sends `active_only` to the API (post-overlay truth is client-side).
- API `active_only=true` still filters before the row slice; batch over-fetch uses the full cap (100) so server-side active+limit callers also fill correctly.
- Electron Progress page aligned with the same composition.

## Files touched

- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/tests/test_progress_view.py`
- `camxora/src/renderer/src/features/shell/ProgressPage.tsx`
- `platform_api/routers/progress.py`
- `platform_api/tests/test_progress_router.py`
- root / platform_api changelogs

## Tests

- `pytest camxora_python/tests/test_progress_view.py -k "active_only or stage_filter or overfetch"`
- `pytest platform_api/tests/test_progress_router.py -k fetch_limit`
