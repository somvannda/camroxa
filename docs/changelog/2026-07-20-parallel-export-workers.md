# Parallel export workers (Preferences) actually run in parallel

**Date:** 2026-07-20  
**Status:** implemented (desktop; restart app)

## Summary

Preferences → Export Workers was saved to `videoExportWorkers` / `perfExportWorkers` and read by the pipeline worker pool, but every track still went through the **single-job warm visualizer daemon**, so exports ran one-at-a-time. When workers > 1, export now uses parallel one-shot subprocesses (daemon only for workers=1).

## Product impact

**Before**
- Setting Export Workers to 2–10 still exported tracks sequentially.

**After**
- Workers=1: warm daemon (fast startup).
- Workers>1: N concurrent visualizer+ffmpeg subprocesses (gated by ExportGate).
- Status shows `· N workers`.

## Billing / API / quota

**Not involved in concurrency.** Pipeline billing still charges once at batch start with `count=len(mp3s)` (monthly video quota / credits). Parallel workers do not create extra consume calls.

## Technical impact

- `ExportJob.run_blocking(allow_daemon=…)`
- `run_subprocess_export(..., allow_daemon=worker_count <= 1)`
- Daemon `run_command` fully serialized with `_job_lock`

## Files touched

- `camxora_python/features/video/services/export_job.py`
- `camxora_python/features/video/services/export_coordinator.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/features/video/services/visualizer_daemon.py`
- `camxora_python/tests/test_export_job_daemon_routing.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-20-parallel-export-workers.md`

## Migration / deploy

- Restart desktop app. Set Preferences → Export Workers (e.g. 2–3 on RTX 3060). Save settings.
- On low VRAM (1050 Ti), keep 1–2 workers to avoid NVENC/OOM pressure.

## Tests

- `pytest camxora_python/tests/test_export_job_daemon_routing.py tests/test_export_coordinator.py`

## Follow-ups

- Optional pool of N warm daemons for parallel+amortized startup.
- Surface active worker count in Progress export cell.
