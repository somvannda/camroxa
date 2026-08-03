# Per-device workspace media paths (desktop 1.0.17)

**Date:** 2026-08-03  
**Status:** included in desktop **v1.0.17**  
**Base:** spectrum/force-update **v1.0.16** (`b9b2f9a`)

## Summary

Same Camxora account on two Windows machines no longer permanently shares one
absolute `sunoOutputDir` / `downloadsDir` / image folder root. Each PC keeps
its own roots under
`%LOCALAPPDATA%\Camxora\users\{userId}\device-workspace-paths.json`. The active
desktop still PATCHes those roots into account settings so server run-dir
planning matches the machine currently generating. Pending Suno downloads that
were planned under another PC's path are remapped onto this machine's Suno
root (keeping `channel/date_album`).

## Product impact

**Before:** Logging into PC B could leave cloud `sunoOutputDir` pointing at
PC A's AppData (or vice versa). New batches planned there; the other machine
skipped foreign pending downloads or wrote to the wrong drive.

**After:** Each machine remembers its own folders. Login overlays local roots,
pushes them while that desktop is active, and remaps stuck pending MP3s into
the local Suno tree.

## Technical impact

- New `shared.lib.device_workspace_paths` local JSON store + remap helpers
- `apply_workspace_path_defaults` overlays device store before heal/defaults
- `ensure_workspace_defaults` persists local roots and PATCHes local-vs-cloud diffs
- Shell warmup runs ensure on login; Settings save writes the device store
- `MusicDownloadSyncWorker` remaps pending `output_dir`/`target_path` before download

## Files touched

- `camxora_python/shared/lib/device_workspace_paths.py` (new)
- `camxora_python/shared/lib/workspace_defaults.py`
- `camxora_python/shared/services/workspace_defaults_sync.py`
- `camxora_python/shared/lib/music_download_utils.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/shared/workers/shell_warmup_worker.py`
- `camxora_python/features/settings/views/settings_view.py`
- `camxora_python/tests/test_device_workspace_paths.py` (new)
- `camxora_python/tests/test_music_download_coordinator.py`
- version bump to 1.0.17 + `CHANGELOG.md` / release notes

## Migration / deploy

Desktop-only. No platform_api / DB changes. Ships in the v1.0.17 installer
(includes 1.0.16 spectrum save + force-update). Album/run-dir lock remains a
separate already-deployed API fix.

## Tests

- `pytest camxora_python/tests/test_device_workspace_paths.py -q`
- `pytest camxora_python/tests/test_workspace_defaults.py -q`
- `pytest camxora_python/tests/test_music_download_coordinator.py -q`
- `pytest camxora_python/tests/test_app_version.py -q`
