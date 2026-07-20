# Progress row cancel for active export/merge

**Date:** 2026-07-20  
**Status:** implemented (desktop)

## Summary

The Progress page already had a right-click menu, but it lacked a cancel action. Only one local pipeline export/merge can run at a time; without cancel, users were stuck with “Video pipeline is already running” and could not start another row’s export. Added **Cancel Active Export/Merge** on every operational row context menu.

## Product impact

**Before**
- Right-click offered Start Export / retries / open folder, but no way to stop the active export/merge from Progress.
- Starting another export while busy only showed a warning (or failed silently via coordinator).

**After**
- Right-click any Progress row → **Cancel Active Export/Merge** stops the live worker or clears stuck busy flags.
- If Start Export is blocked because the pipeline is busy, the warning tells the user to use that cancel action first.

## Technical impact

- `PipelineAutomationService.cancel_active()` cancels export/merge workers or recovers stale busy state.
- `VideoPipelineCoordinator.cancel_active_export()` / `is_busy()` exposed for Progress.
- `OperationalRowsCard.cancel_job_requested` + Progress view handler.

## Files touched

- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/tests/test_pipeline_automation_stale_recovery.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-20-progress-cancel-active-export.md`

## Migration / deploy

- Desktop rebuild/restart only; no API/DB changes.

## Tests

- `pytest camxora_python/tests/test_pipeline_automation_stale_recovery.py` — cancel_active cases.

## Follow-ups

- Row-scoped cancel (only stop if the active job matches that batch/role).
- Optional: cancel pending image jobs for Error rows via API clear/retry path.
