# Stop Exporting — pause auto pipeline until manual start

**Date:** 2026-07-21  
**Status:** implemented (desktop; restart app)

## Summary

Added Progress right-click **Stop Exporting**: cancels the live export/merge and sets a session pause so auto-video and the pipeline helper agent will not start new work until the user explicitly Start Export / Rebuild / Force Regenerate / Continue Progress / Start Merging on a row.

## Product impact

**Before**
- Cancel could stop a job, but auto-video / helpers often restarted shortly after.

**After**
- **Stop Exporting** = real stop + auto paused until a manual row action.
- **Cancel Active Export/Merge** still only cancels the current job (short cooldown); it does not set the persistent pause.

## Technical impact

- `shared/services/auto_pipeline_pause.py`
- `VideoPipelineCoordinator` skips auto starts while paused; `run_manual_action` clears pause
- `PipelineRecoveryCoordinator` skips scans while paused
- Progress menu + `_stop_exporting` handler; Continue / Start Export clears pause

## Files touched

- `camxora_python/shared/services/auto_pipeline_pause.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/shared/services/pipeline_recovery_coordinator.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/tests/test_auto_pipeline_pause.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-21-stop-exporting-pause-auto.md`

## Migration / deploy

- Restart desktop app.

## Tests

- `pytest camxora_python/tests/test_auto_pipeline_pause.py`

## Follow-ups

- Optional footer badge when auto pipeline is paused.
