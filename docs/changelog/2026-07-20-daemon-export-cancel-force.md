# Daemon export cancel actually stops hung ffmpeg

**Date:** 2026-07-20  
**Status:** implemented (desktop; restart app to pick up)

## Summary

Pipeline export cancel was a no-op when using the warm visualizer daemon: `ExportJob.cancel()` only terminated `self.proc`, which is unset on the daemon path. A hung render (daemon CPU frozen + ffmpeg waiting on `pipe:0`) left Progress stuck on “Video pipeline is already running” and Cancel only printed “Stopping…”. Cancel now kills the daemon process tree (Windows `taskkill /T`) and does not fall back into a second subprocess export after cancel.

## Product impact

**Before**
- Right-click **Cancel Active Export/Merge** while a daemon export was wedged did not free the pipeline.
- Users had to restart the app (or manually kill `python -m visualizer.daemon` / ffmpeg).

**After**
- Cancel kills the warm daemon and its ffmpeg children so Start Export can run again.
- Mid-job daemon death without `job_done` no longer silently restarts the same track as a one-shot subprocess.

## Technical impact

- `VisualizerDaemonClient.cancel_active()` + `_terminate_process_tree()` (Windows `/T /F`).
- `ExportJob.cancel()` calls daemon cancel when `proc` is unset; `run_blocking` returns on cancel instead of falling through to subprocess.
- `PipelineAutomationService.cancel_active()` always pokes the daemon client.
- `run_command` returns `1` (not `None`) on cancel / mid-job death so callers do not treat it as “daemon unavailable”.

## Files touched

- `camxora_python/features/video/services/visualizer_daemon.py`
- `camxora_python/features/video/services/export_job.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/tests/test_visualizer_daemon_argv.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-20-daemon-export-cancel-force.md`

## Migration / deploy

- Restart the desktop app (dev: re-run `python main.py`) so the fixed cancel path loads.
- No API/DB changes. Sandbox 502s around the same window were a separate API process restart (`/health` uptime reset); unrelated to export cancel.

## Tests

- `pytest camxora_python/tests/test_visualizer_daemon_argv.py` — cancel tree + ExportJob→daemon cancel.

## Incident

- Stuck local export: `visualizer.daemon` PID + child `ffmpeg` encoding `8. Ghost Light Rush Transmission_OK.mp3` with frozen CPU; force-killed via `taskkill /T /F` so the user could continue while the cancel fix shipped.

## Follow-ups

- Soft cancel into the daemon job (stdin cancel message) without full process recycle when the render loop is healthy.
- Progress UI: if cancel does not clear `is_busy` within N seconds, auto force-clear + toast.
