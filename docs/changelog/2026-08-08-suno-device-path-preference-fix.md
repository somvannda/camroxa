# Fix Preferences Suno root wiped by account settings

**Date:** 2026-08-08  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `bugfix/suno-device-path-preference`

## Summary

Preferences could show `E:\SUNO` while downloads wrote under
`%LOCALAPPDATA%\Camxora\Media\Suno` because saving Preferences re-persisted
**cloud** `sunoOutputDir` into the per-device store. Absolute media roots are
now device-local only; Preferences UI keeps FFmpeg + Suno root.

## Product impact

- Setting **Suno output dir** sticks across Preferences saves and batch runs.
- Stale AppData `Media\Suno` folders no longer win when the configured root is elsewhere.
- Removed Downloads / Merged / optional Image output fields from Preferences
  (auto-defaults; run assets still land under the Suno tree).

## Technical impact

- `_after_settings_saved` / path-only save persist `device_paths_dict_from_draft`
  — never API response media roots
- `build_system_settings_patch` omits absolute media path keys
- `ensure_workspace_defaults` / `hydrate_local_suno_output_dir` strip media keys
  from cloud PATCH
- `local_run_dir_for_disk` rebases existing default AppData Suno paths onto the
  configured root (Change Run Folder outside that tree still kept)

## Files touched

- `camxora_python/shared/lib/device_workspace_paths.py`
- `camxora_python/shared/lib/settings_workspace.py`
- `camxora_python/shared/lib/workspace_defaults.py`
- `camxora_python/shared/services/workspace_defaults_sync.py`
- `camxora_python/features/settings/views/settings_view.py`
- `camxora_python/tests/test_device_workspace_paths.py`
- `camxora_python/tests/test_settings_workspace.py`
- Root `CHANGELOG.md`

## Migration / deploy

Desktop-only. No platform_api deploy. After upgrade: set Suno output dir once
and Save Preferences (rewrites `device-workspace-paths.json`).

## Tests

- `pytest camxora_python/tests/test_device_workspace_paths.py -q`
- `pytest camxora_python/tests/test_settings_workspace.py -q`
- `pytest camxora_python/tests/test_workspace_defaults.py -q`

## Follow-ups

- Ship in next desktop installer (force-update recommended for operators hitting
  AppData vs E: split).
