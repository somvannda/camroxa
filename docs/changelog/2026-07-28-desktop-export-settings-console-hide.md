# Desktop — Video export settings honor + hide worker consoles

**Date:** 2026-07-28  
**Status:** implemented (desktop rebuild)

## Summary

Video **Standard** tier now honors the Video page FPS and speed (not only Master). Export workers already ran as separate hidden `Camxora.exe --visualizer` processes; the N black console flashes came from bare `nvidia-smi` / `taskkill` grandchildren — now routed through `run_hidden`. Each export logs applied `WxH @ fps · speed=…` so settings are verifiable.

## Product impact

- **Before:** Standard forced encode FPS=24 (UI FPS ignored for Manual); N black consoles on multi-worker export.
- **After:** Standard uses Preferences resolution + Video FPS/speed; workers stay background with no console flash; Progress/Manual log the applied encode settings.

## Technical impact

- `resolve_export_tier_settings`: Standard reads `videoExportFps` + `videoExportSpeedMode`
- `export_gpu_tier._probe_nvidia_smi` + daemon `taskkill` → `run_hidden`
- `ExportJob` sets `CAMXORA_GPU_TIER` on child env and emits settings status line
- Draft remains fixed 720p / 24 / very_fast

## Files touched

- `camxora_python/shared/lib/export_tiers.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/widgets/export_queue_panel.py`
- `camxora_python/visualizer/export_gpu_tier.py`
- `camxora_python/features/video/services/visualizer_daemon.py`
- `camxora_python/features/video/services/export_job.py`
- `camxora_python/tests/test_export_tiers.py`
- `docs/changelog/2026-07-28-desktop-export-settings-console-hide.md`

## Migration / deploy

Rebuild desktop installer from hotfix worktree; no API/DB.

## Tests

- `pytest camxora_python/tests/test_export_tiers.py camxora_python/tests/test_subprocess_console_guard.py camxora_python/tests/test_export_gpu_tier.py`

## Follow-ups

- Optional: align Progress Start Export with Draft tier resolution (720p) when tier=draft
