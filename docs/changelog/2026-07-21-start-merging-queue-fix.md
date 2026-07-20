# Start Merging was blocked by settings poll / auto-export steal

**Date:** 2026-07-21  
**Status:** implemented (desktop; restart app)

## Summary

Start Merging failed with “Video pipeline is still loading settings” whenever the auto-poll worker was busy; clearing Stop-Export pause then let auto-export start instead. Manual merge/export is now queued onto the in-flight settings load, and Continue Progress prefers merge when local MP4s already exist.

## Product impact

**Before**
- Export finished (`Export complete · 10/10`) without merge when Auto Merge was off.
- Start Merging often no-oped; auto-video restarted export.

**After**
- Start Merging queues and runs when settings finish loading.
- Continue Progress merges when MP4s are already on disk.
- Merge no longer requires the Video catalog template (only exported MP4s in the run folder).
- Rebuild / Force Regenerate honor Music → **Auto Merge** (same as auto-video) instead of always stopping after MP4 export.
- Auto merge after export still needs Music → **Auto Merge** checked.

## Technical impact

- `VideoPipelineCoordinator._on_payload_ready` honors `_pending_manual` first
- `run_manual_action` queues instead of aborting on busy poll worker
- `continue_progress._prefer_merge_over_export`
- `_run_video_pipeline_action` skips `evaluate_video_export_readiness` for `merge`; checks run folder + branch MP4s only
- Manual `rebuild_export` / `force_export` no longer pass `auto_merge=False`

## Files touched

- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/features/progress/lib/continue_progress.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/tests/test_continue_progress.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-21-start-merging-queue-fix.md`

## Migration / deploy

- Restart desktop app.
- Optional: enable Music → Auto Merge for automatic merge after export.

## Tests

- `pytest camxora_python/tests/test_continue_progress.py`
