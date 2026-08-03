# Force update: visible Setup + honest completion

**Date:** 2026-08-03
**Status:** implemented (desktop v1.0.16)
**Branch:** `fix/force-update-visible-install`

## Summary

Force update already auto-installed the downloaded Inno Setup, but it used
`/VERYSILENT` (no UI) and reported success as soon as the helper script was
spawned. Users saw “Install ready — Camxora will restart…”, the app closed,
and opening the desktop shortcut minutes early still showed the previous
version while Setup was still writing files.

## Fix

- EXE helper uses `/SILENT` (visible Inno progress) instead of `/VERYSILENT`.
- Gate / worker copy says Camxora is closing so Setup can run, and that Setup
  may take a few minutes — never that the new version is already installed.
- Helper writes `%LOCALAPPDATA%\Camxora\updates\update-status.json` phases
  (`waiting` → `installing` → `verifying` → `done` / `failed`).
- After Setup exit 0, helper reads installed `app-version.txt` and only
  relaunches when it matches the published target version.
- Mandatory update + `install_in_progress` persist to
  `pending-update.json`. Startup restores the gate; active helper status
  shows “Finishing update…”.

## Files

- `camxora_python/shared/services/software_update_installer.py`
- `camxora_python/shared/services/software_update_service.py`
- `camxora_python/shared/workers/software_update_worker.py`
- `camxora_python/shared/lib/software_update_persistence.py`
- `camxora_python/shared/widgets/software_update_gate.py`
- `camxora_python/shared/lib/software_update_copy.py`
- `camxora_python/app/root_window.py`
