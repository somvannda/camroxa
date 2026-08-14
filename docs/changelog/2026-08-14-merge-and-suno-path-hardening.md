# Harden Progress merge + Preferences Suno path

**Date:** 2026-08-14  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `release/desktop-1.2.6`

## Summary

Follow-up hardening after the 1.2.6 merge-skip and installer Suno-folder reset.

**Merge:** success requires a real on-disk `MERGED_*.mp4`; nested duplicate run
folders are used when they hold more exports; today’s export specs no longer
hide already-exported albums; a stale `MERGED_*.mp4` is rebuilt if inputs are
newer.

**Suno path:** a `.bak.json` copy recovers a custom folder if the primary store
was healed to AppData; persist after logout still writes the last signed-in
account folder, not the Camxora root.

## Product impact

- Clicking Merge never reports done without a merged file on disk.
- Nested `channel/album/channel/album` run trees still merge.
- Auto-merge can join existing exports even if Video FPS/size changed.
- Preferences Suno dir survives installer, missing drive, and logout persist.

## Technical impact

- `merged_output_ready` + worker/success handlers refuse empty or tiny outputs
- `resolve_merge_run_dir` picks the folder with more branch MP4s
- `collect_verified_merge_inputs` retries without export-spec filters
- `merge_video_outputs` raises when `<2` inputs; remakes stale MERGED files
- Device store backup + last-activated user id for persist

## Files touched

- `camxora_python/features/video/lib/pipeline_merge.py`
- `camxora_python/features/video/workers/pipeline_merge_worker.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/settings/views/settings_view.py`
- `camxora_python/shared/lib/device_workspace_paths.py`
- `camxora_python/shared/services/local_user_scope.py`
- `camxora_python/tests/test_pipeline_merge.py`
- `camxora_python/tests/test_device_workspace_paths.py`

## Migration / deploy

Desktop-only. Next installer cut. No API/sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_pipeline_merge.py -q`
- `pytest camxora_python/tests/test_device_workspace_paths.py -q`
- `pytest camxora_python/tests/test_local_user_scope.py -q`
