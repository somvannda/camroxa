# Progress Merge showed “merging” but wrote no MERGED file

## Summary

Progress **Start Merging** / Continue could show “Merging…” and then finish with **no** `MERGED_*.mp4` in the run folder. The worker treated a skipped merge as success, and merge-only jobs still required today’s export settings (resolution / FPS / 48 kHz) instead of joining the files that were already exported.

## Product impact

- Clicking **Merge** on a finished export either writes `MERGED_*.mp4` in the run folder or shows a real error (not a silent skip).
- Already-exported albums (older FPS / sample rate) can merge if the tracks match **each other** for lossless concat.
- Windows antivirus/indexer touching file mtimes no longer causes every MP4 to be skipped as “unstable.”
- A successful Progress merge now marks the channel row pipeline-complete so it leaves the active board.

## Technical impact

- `VideoPipelineMergeWorker` fails when fewer than two usable MP4s remain; it no longer emits `succeeded` with `mergedOutputPath: None`.
- `merge_video_outputs` raises with skip details instead of returning `None` after dropping inputs.
- Progress merge-only (`start_manual_merge`) sets `match_export_specs=False` so current Video settings are not used as a filter.
- `_is_file_stable` checks size hold only (3 short retries).
- `PipelineAutomationService._on_merge_succeeded` requires an on-disk merged path and calls `mark_desktop_pipeline_complete`.

## Files touched

- `camxora_python/features/video/lib/pipeline_merge.py`
- `camxora_python/features/video/workers/pipeline_merge_worker.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/tests/test_pipeline_merge.py`

## Migration / deploy

Desktop-only. Ship with the next desktop build; no API/sandbox deploy.

## Tests

- `camxora_python/tests/test_pipeline_merge.py`
