# Force update: install progress + auto-restart

**Date:** 2026-07-25  
**Status:** implemented (desktop; needs rebuild to ship in packaged 0.4.x)

## Summary

Mandatory software updates already downloaded in the gate dialog, but silent install often never finished or never relaunched Camxora. The installer helper is now detached from the kill-on-exit job, Setup.exe is staged outside temp, and after download the same dialog shows install/restart status before quitting so the helper can install and reopen the app.

## Product impact

**Before**
- Progress stuck on “Downloading…” / install appeared to no-op.
- App might quit without a successful install or fail to reopen.

**After**
1. Download progress in the update box (0–85%).
2. Status switches to Preparing / Installing in the same box.
3. Camxora exits briefly; silent Setup finishes and **relaunches** Camxora.

## Technical impact

- `popen_hidden_orphan` — update helpers must not join the KILL_ON_JOB_CLOSE job.
- EXE/MSI: copy to `%LOCALAPPDATA%\Camxora\updates\`, PowerShell waits for parent PID → `/VERYSILENT` (or msiexec quiet) → `Start-Process` Camxora.exe.
- Gate titles: Downloading / Installing / Restarting.

## Files touched

- `camxora_python/shared/lib/subprocess_utils.py`
- `camxora_python/shared/services/software_update_installer.py`
- `camxora_python/shared/workers/software_update_worker.py`
- `camxora_python/shared/services/software_update_service.py`
- `camxora_python/shared/widgets/software_update_gate.py`
- `camxora_python/tests/test_software_update_installer.py`
- `CHANGELOG.md`

## Migration / deploy

- Rebuild sandbox desktop (recommend **0.4.1**) so users on 0.3.0/0.4.0 receive a client that can complete force-update installs.
- No API/migration changes.

## Tests

- `python -m pytest camxora_python/tests/test_software_update_installer.py -q`

## Follow-ups

- Ship 0.4.1 with this fix + purple progress bar polish.
- Manual smoke: publish mandatory update → Update now → confirm download → install message → app reopens on new version.
