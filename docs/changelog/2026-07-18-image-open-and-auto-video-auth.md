# Image open download + auto-video auth fixes

**Date:** 2026-07-18  
**Status:** implemented

## Summary

Fixed a `FileNotFoundError` when opening image outputs from the Image queue before PNGs were synced locally. Auto-video billing now uses the authenticated shell `PlatformApi` instead of a fresh unauthenticated client, with quieter handling when the session is missing.

## Product impact

- **Before:** Double-click or context-menu “Open Background/Thumbnail File” could crash or traceback when the server reported success but the PNG was not yet on disk. Auto-video repeatedly showed “Auto-video blocked (billing): Unauthenticated” every poll cycle.
- **After:** Open actions download the image first when needed, then open in the OS viewer. Missing files show a friendly footer warning instead of an exception. Auto-video billing uses the signed-in session; auth failures pause with a short message and a 2-minute retry cooldown.

## Technical impact

- New `ensure_image_output_local()` shared helper used by preview sync, output sync, and a new `ImageOpenWorker`.
- `controls_queue_card.job_open_requested` now emits `(path, job_id)`.
- `open_path()` guards missing files with log + shell status.
- `PipelineAutomationService` accepts injected `PlatformApi`; coordinator passes `self._api` and applies longer cooldown on 401.

## Files touched

- `camxora_python/shared/lib/image_output_utils.py` (new)
- `camxora_python/shared/services/file_service.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/image/widgets/controls_queue_card.py`
- `camxora_python/features/image/views/image_view.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_image_output_and_pipeline_auth.py` (new)
- `camxora_python/tests/test_file_service_paths.py`

## Migration / deploy

- Desktop app only — restart CAMXORA after pulling.

## Tests

- `pytest camxora_python/tests/test_file_service_paths.py camxora_python/tests/test_image_output_and_pipeline_auth.py`

## Follow-ups

- None.
