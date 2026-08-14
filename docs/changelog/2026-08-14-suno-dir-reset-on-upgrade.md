# Preferences Suno folder reset to default after installer

**Date:** 2026-08-14  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `release/desktop-1.2.6`

## Summary

A saved **Suno output dir** (for example `D:\Suno Generated`) could revert to
`%LOCALAPPDATA%\Camxora\Media\Suno` after installing a new desktop build.
Startup treated a missing/low-space drive as “heal to default” and wrote that
default into the per-device store. A leftover
`device-workspace-paths.json` at the Camxora AppData root was also skipped
when the account folder already had other workspace files.

## Product impact

- Preferences **Suno output dir** survives app upgrades and first launch after
  an installer.
- A temporarily missing or low-space drive no longer silently replaces the
  saved folder with AppData `Media\Suno`.
- An older root-level device-path file is merged into
  `users\{userId}\device-workspace-paths.json` on login (custom folder wins
  over a healed default).

## Technical impact

- `apply_workspace_path_defaults` keeps a saved non-default device-store path
  when mkdir / free-space checks fail (cloud leftovers still self-heal).
- `ensure_workspace_defaults` / hydrate persist with
  `replace_machine_defaults=False` so a heal cannot overwrite a custom root.
- Login migrates/merges `%LOCALAPPDATA%\Camxora\device-workspace-paths.json`
  even when the scoped user folder already has music/video prefs.
- Load falls back to that root file when the scoped store is still empty.

## Files touched

- `camxora_python/shared/lib/workspace_defaults.py`
- `camxora_python/shared/lib/device_workspace_paths.py`
- `camxora_python/shared/services/workspace_defaults_sync.py`
- `camxora_python/shared/services/local_user_scope.py`
- `camxora_python/tests/test_device_workspace_paths.py`
- `camxora_python/tests/test_local_user_scope.py`
- Root `CHANGELOG.md`

## Migration / deploy

Desktop-only. Ship with the next desktop build; no API/sandbox deploy.
Users who already lost the preference: set **Suno output dir** once in
Preferences and Save (or relaunch if the old root JSON is still present).

## Tests

- `pytest camxora_python/tests/test_device_workspace_paths.py -q`
- `pytest camxora_python/tests/test_local_user_scope.py -q`
- `pytest camxora_python/tests/test_workspace_defaults.py -q`
