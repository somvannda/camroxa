# Export / merge path contract + validity

## Summary

Fix manual export merge (path mismatch) and stop pipeline merge from concatenating incomplete/broken MP4s by aligning output paths, verifying media before skip/merge, and rebuilding merge inputs from usable files only. When concat stream-copy fails, re-encode using the same export quality settings (resolution / FPS / speed mode).

## Product impact

- Manual batch export with Auto merge now merges the real `{stem}.mp4` files the visualizer writes.
- Pipeline export re-encodes files that are large but media-incomplete (no video stream / truncated vs audio).
- Merge skips unusable MP4s and requires at least two usable inputs; clearer warning when merge cannot run.
- Auto-merge toggle is no longer cleared after a merge finishes.
- Merged files use **lossless stream copy only** (same quality as exports). Incompatible leftovers/mismatches fail clearly instead of soft re-encode.
- New exports force AAC **48 kHz stereo**; early-skip re-exports stale files that don't match current batch resolution/FPS/audio.
- Manual export **Tier** → **Resolution** (same list as Output resolution; no custom).
- ffprobe `returncode == 0` no longer rejected as failed (exports were marked unusable; merge skipped).
- TRACK LIST supports Remove / Delete (list-only); saved `mp3Order` is the playlist until Select MP3 Folder reloads.
- Export Speed **Quality** no longer fails CLI (`--speedMode quality` was an invalid argparse choice).
- Export Speed list: **Best Quality** (new top tier) → Quality → Balance → Fast → Very Fast.
- Export encode uses **Recommended VBR bitrate** (resolution × FPS × Speed), CapCut-inspired; CQ/constqp removed.

## Technical impact

- Visualizer honors `--output` / `GpuOptions.output_path`; `ExportJob` passes it.
- Manual export names match visualizer (`{stem}.mp4`); success requires a usable on-disk file.
- New `export_output_validity` helpers (video stream + duration vs audio).
- `collect_verified_merge_inputs` rebuilds merge lists; used by Video page + automation.

## Files touched

- `camxora_python/features/video/lib/export_output_validity.py` (new)
- `camxora_python/features/video/lib/render_scene_request.py`
- `camxora_python/features/video/lib/pipeline_merge.py`
- `camxora_python/features/video/services/export_job.py`
- `camxora_python/features/video/services/in_process_export.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/video/workers/manual_export_worker.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/features/video/workers/pipeline_merge_worker.py`
- `camxora_python/features/video/widgets/export_queue_panel.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/services/video_local_store.py`
- `camxora_python/visualizer/main.py`
- `camxora_python/visualizer/gpu_render.py`
- Tests + root `CHANGELOG.md`

## Migration / deploy

Desktop-only. No API/migration. Ship with next desktop build; no sandbox API deploy.

## Tests

- `camxora_python/tests/test_export_output_validity.py`
- `camxora_python/tests/test_pipeline_merge.py`
- `camxora_python/tests/test_render_scene_request.py`
- `camxora_python/tests/test_export_job_daemon_routing.py`

## Follow-ups

- Optional black-frame luma sampling for dark-but-valid false negatives.
- Electron WebGPU manual `autoMerge` wiring if that path is still shipped.
