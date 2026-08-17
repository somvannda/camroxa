# Progress P2: defer Video prewarm audio + persist pipeline_complete

**Date:** 2026-08-17  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `bugfix/progress-skip-idle-disk-scans`

## Summary

Shell prewarm built the Video page and immediately decoded the last preview
MP3 (full analysis). That competed with Progress disk work at startup.

Historical Long completed albums often never saved `pipeline_complete`, so
after a restart the client had to keep inferring “done” from merge labels.

## Product impact

- Opening the app no longer decodes Video preview audio until the user opens
  Video. First visit still loads the last track as before.
- When Progress sees a conclusive local `MERGED_*.mp4`, or an idle Long
  completed row that never latched, it writes `pipeline_complete` to the API.
  After restart those albums stay frozen even if track files were moved.

## Technical impact

- `VideoView` keeps `_preview_audio_enabled` false during construct/prewarm;
  `activate_page` enables audio and flushes the preview.
- `should_persist_pipeline_complete` / `persist_discovered_pipeline_complete`
  in `pipeline_completion.py`.
- `WorkflowLoadWorker` persists latches after the Progress payload is emitted.
- `build_local_progress_sync_items` does not walk idle folders; it can still
  send a latch-only sync. `ProgressLocalSyncWorker` now forwards
  `pipeline_complete`.

## Files touched

- `camxora_python/features/video/views/video_view.py`
- `camxora_python/shared/lib/pipeline_completion.py`
- `camxora_python/shared/lib/progress_local_sync.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/tests/test_pipeline_completion.py`
- `camxora_python/tests/test_progress_local_sync.py`
- `camxora_python/tests/test_video_view.py`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart `python main.py production` (or the next installer).
The latch writes through the existing `/progress/sync-local` API — no
migration or sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_pipeline_completion.py camxora_python/tests/test_progress_local_sync.py camxora_python/tests/test_video_view.py camxora_python/tests/test_progress_local_overlay.py camxora_python/tests/test_video_runtime_inspection.py -q`
