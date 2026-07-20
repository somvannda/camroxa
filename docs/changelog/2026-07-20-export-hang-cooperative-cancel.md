# Export hang: cooperative cancel + no instant auto-restart

**Date:** 2026-07-20  
**Status:** implemented (desktop; restart app)

## Summary

Video export often *looked* hung without API errors: the warm daemon render loop had **no cancel_check**, so Cancel only worked by killing the process (and auto-video could restart the same batch within seconds). Added a per-job cancel flag file checked between frames and while blocked on the encode queue, soft-cancel before hard kill, and a 45s auto-video pause after user cancel.

## Product impact

**Before**
- Cancel Active Export often left “Stopping… when it finishes” while the daemon kept encoding.
- Auto-video could immediately re-start the same run → “already running” / feels stuck.

**After**
- Cancel signals the renderer to stop between frames / unblock the encode queue, then kills if needed.
- After user cancel, auto-video waits ~45s before picking up again (manual Start Export / Continue Progress still works).

## Investigation note (live)

A “stuck” horizon-batch export was actually still encoding (`1. Neon Heart…mp4` size growing; NVENC busy). Lack of soft-cancel + immediate auto-restart made it feel hung.

## Technical impact

- `CAMXORA_EXPORT_CANCEL_PATH` flag file; daemon job JSON includes `cancelPath`
- `run_gpu_render(..., cancel_check=export_cancel_requested)`
- Encode queue submit loops poll the cancel flag
- `VideoPipelineCoordinator._user_cancel_until`

## Files touched

- `camxora_python/features/video/lib/export_cancel.py`
- `camxora_python/features/video/services/export_job.py`
- `camxora_python/features/video/services/visualizer_daemon.py`
- `camxora_python/visualizer/daemon.py`
- `camxora_python/visualizer/main.py`
- `camxora_python/visualizer/encode_pipeline.py`
- `camxora_python/visualizer/native_encode_writer.py`
- `camxora_python/shared/services/video_pipeline_coordinator.py`
- `camxora_python/tests/test_export_cancel.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-20-export-hang-cooperative-cancel.md`

## Migration / deploy

- Restart desktop app so daemon + cancel path load.

## Tests

- `pytest camxora_python/tests/test_export_cancel.py tests/test_export_job_daemon_routing.py`

## Follow-ups

- Stall watchdog: if no progress event for N seconds, auto-fail the track.
- Surface live `Rendering N/M` on Progress export cell (not only shell status).
