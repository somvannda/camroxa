# Quit-safe auto-video after API recovery

**Date:** 2026-07-25  
**Status:** implemented (desktop restart required)

## Summary

Closing the desktop app right after auto-video logged “API recovered — resuming auto-video pipeline…” could still deliver a queued orchestration `succeeded` signal during `closeEvent` `processEvents`, start a new export worker, then destroy that QThread with the parent window — logging `QThread: Destroyed while thread '' is still running`.

## Product impact

- **Before:** Closing during/after API recovery often printed a Qt thread warning (harmless but noisy; could leave a short-lived orphaned worker).
- **After:** Background coordinators disconnect workers on stop, ignore late payloads when inactive/quitting, and refuse new auto-export/merge once quit has started.

## Technical impact

- `VideoPipelineCoordinator.stop` disconnects signals and clears `_worker`.
- Payload/manual/fail handlers check `_active` + `is_app_quitting()`.
- `PipelineAutomationService.start` / merge path refuse work while quitting.
- Same disconnect pattern on music download, image sync, progress sync, and pipeline recovery coordinators.
- Named `MusicHistoryRefreshWorker` / `PipelineRecoveryWorker` for clearer diagnostics if a race remains.

## Files touched

- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/shared/services/music_download_coordinator.py`
- `camxora_python/shared/services/image_output_sync_coordinator.py`
- `camxora_python/shared/services/progress_local_sync_coordinator.py`
- `camxora_python/shared/services/pipeline_recovery_coordinator.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/tests/test_video_pipeline_quit_safety.py`
- `CHANGELOG.md`

## Migration / deploy

- Desktop only — restart the app (no API deploy).

## Tests

- `pytest camxora_python/tests/test_video_pipeline_quit_safety.py`

## Follow-ups

- Longer term: parent all History/Progress page workers with `parent=None` + `track_app_thread` the same way shell coordinators do.
