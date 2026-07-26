# Export failure diagnostics in desktop logs

**Date:** 2026-07-25  
**Status:** implemented (desktop v0.4.2 build)

## Summary

GTX 1050 Ti Progress exports were failing with bare `Export failed with exit code 1` (or hanging on Analyzing audio) while synced diagnostics only showed UI summary lines. Export now persists renderer crash tails and milestone stage messages into the app logger so Send diagnostics can capture the real cause.

## Product impact

- **Before:** Diagnostics showed only “exit code 1” / “Auto-video started…”, no traceback.
- **After:** Failed exports log multiline detail under `[export]`; stage lines (analyzing / cache / encoder) appear while a hang is in progress. Progress row still shows a short first-line status.

## Technical impact

- `ExportJob` keeps `last_error_detail` from daemon + subprocess stdout / `MG_EVENT failed`.
- `VideoPipelineExportWorker` formats failure with backend + detail and `log_error`s it.
- Milestone filter in `export_failure_log.py` avoids logging every render frame.

## Files touched

- `camxora_python/features/video/lib/export_failure_log.py`
- `camxora_python/features/video/services/export_job.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/features/video/workers/manual_export_worker.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/tests/test_export_failure_log.py`
- Version/release: `pyproject.toml`, `app-version.txt`, `app_version.py`, `Camxora.iss`, `release-notes.txt`, `CHANGELOG.md`

## Migration / deploy

1. Build: `cd camxora_python; .\scripts\build-desktop.ps1 -Environment sandbox -BuildInno`
2. Install `dist/installer/CamxoraSetup-0.4.2.exe` on the 1050 Ti PC (or publish via Admin → Software Updates).
3. Reproduce fail/hang → Settings → Send diagnostics → re-pull sandbox `client_log_batches`.

## Tests

- `pytest camxora_python/tests/test_export_failure_log.py camxora_python/tests/test_app_version.py`

## Follow-ups

- Use new diagnostics to fix 1050 Ti exit-code-1 / analyzing hang root cause.
- Optional: stop auto-video rapid retry loop on hard fails (separate UX change).
