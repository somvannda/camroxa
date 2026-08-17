# Desktop Progress stuck on background after image jobs succeed

**Date:** 2026-08-16  
**Status:** implemented locally, sandbox next  
**Branch:** `bugfix/progress-trust-image-job-success`

## Summary

`sophay@camxora.com` retried image jobs; every job is `success` and `batch_channel_assets` already stores `D:\SUNO\...\background-16x9.png`. Desktop Progress still showed **Image** with “Background generation is still in progress (needed before video export).”

## Product impact

**Before:** Successful background/thumbnail jobs did not advance Progress. Continue Progress offered “Retry image jobs” because the row stayed on the Image stage.

**After:** Progress stops claiming generation is still running once background jobs succeed. Export readiness is unchanged: desktop still needs a real local PNG. Continue Progress will not retry already-successful jobs, and will not start export until `long_ready` is true from local files.

## Technical impact

Split two flags:

- **Generation complete** — all background image jobs `success`. This only moves the Progress *stage/notes* off “still in progress.”
- **Export assets verified** — `long_ready` / `reel_ready` from files this host can open. Desktop overlay, auto-export, and Continue export still use this.

Desktop `GET /progress` does **not** inject `server://image-job-ready` placeholders and does **not** trust unverified `D:\SUNO\...` paths for `meta.long_ready`. Those would make the desktop overlay treat images as present locally and could start export without a file.

Admin Pipeline Ops still uses `mark_ready_from_image_jobs` (watch-only board). That helper now refuses to mark a kind ready if it still has failures.

Continue Progress: retry images only when jobs failed or are not READY; Converter/Export requires `long_ready` or `reel_ready`.

## Files touched

- `platform_api/services/channel_asset_service.py` — shared trust / overlay / job-ready helpers; failed-job guard
- `platform_api/routers/progress.py` — generation-complete vs export-verified
- `platform_api/services/admin_pipeline_service.py` — call the shared helpers
- `camxora_python/features/progress/lib/continue_progress.py` — do not retry READY jobs; do not export without local assets
- `platform_api/tests/test_channel_asset_service.py`
- `platform_api/tests/test_progress_router.py`
- `camxora_python/tests/test_continue_progress.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

No migration. Sandbox `platform_api` sync + API restart. Production only on explicit request. Desktop app does not need a rebuild for the Progress API change.

## Tests

- `test_trust_persisted_asset_paths_keeps_windows_desktop_paths`
- `test_mark_ready_from_image_jobs_without_local_files`
- `test_progress_leaves_image_stage_when_background_jobs_succeed_without_local_files`
- `test_progress_stays_on_image_when_background_jobs_incomplete`

## Follow-ups

- Desktop `ImageOutputSyncWorker` still lists only 40 recent success jobs; users with many batches may not pull every PNG locally. Separate from this API display bug.
- Most of sophay’s channel-asset rows still have `pipeline_complete = false` even though `batches.status = completed`. Unrelated; does not block image-stage promotion after this fix.
