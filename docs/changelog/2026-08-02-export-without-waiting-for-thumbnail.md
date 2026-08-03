# Export readiness: background only (no thumbnail wait)

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/export-bg-only-ready`

## Summary

Progress/export stayed on Image until thumbnail finished even when the background was already ready. Desktop already treated thumbnail as YouTube-only; the API still required BG+TH for `long_ready` / `image_complete`. This ports the excluded server fix from `fix/startup-freeze-hardening`.

## Changes

- `compute_long_ready` / `compute_reel_ready` → background path only
- Add `compute_youtube_*_ready` for upload completeness (BG+TH)
- Progress `image_complete` no longer waits on thumbnail job counters
- Manual asset resolve: BACKGROUND gated on BG; THUMBNAIL gated on TH paths

## Files

- `platform_api/services/channel_asset_service.py`
- `platform_api/routers/progress.py`
- `platform_api/services/batch_service.py` (`_resolve_manual_asset_outputs`)
- `platform_api/tests/test_channel_asset_service.py`
