# Visualizer export daemon argv + readback fixes

**Date:** 2026-07-19  
**Status:** implemented (dev verified; sandbox pending)

## Summary

Fixed GPU video export failures when jobs run through the warm visualizer daemon (frozen `--visualizer` launcher argv) and when framebuffer readback allocates PBO buffers. Empty `--logo` values are preserved during argv normalization so argparse no longer fails immediately with exit code 1.

## Product impact

- **Before:** Export could fail at startup with exit code 1 — argparse treated `--visualizer` as `mp3_path`, or `--logo` lost its empty value and raised "expected one argument". GPU encode could crash when creating async readback buffers.
- **After:** Daemon and direct export paths produce MP4 successfully on Windows with NVENC; warm daemon handles consecutive jobs.

## Technical impact

- `normalize_visualizer_job_argv` strips `--visualizer` / `-m visualizer.main` without dropping empty string flag values.
- `AsyncFramebufferReader` uses `ctx.buffer(reserve=size)` (moderngl API).
- Daemon sets `CAMXORA_DAEMON_JOB=1`; GPU render skips `glfw.terminate()` between jobs.

## Files touched

- `camxora_python/visualizer/main.py`
- `camxora_python/visualizer/readback.py`
- `camxora_python/visualizer/daemon.py` (prior)
- `camxora_python/features/video/services/visualizer_daemon.py` (prior)
- `camxora_python/visualizer/gpu_render.py` (prior)
- `camxora_python/tests/test_visualizer_daemon_argv.py`

## Migration / deploy

No DB or env changes required. Optional kill-switch: `CAMXORA_USE_VISUALIZER_DAEMON=0` forces subprocess fallback.

## Tests

- `pytest tests/test_visualizer_daemon_argv.py tests/test_export_readback.py` — 10 passed
- Direct GPU export: 3s MP3, 640×360, 15 fps, very_fast → MP4 OK
- Daemon with frozen `--visualizer` argv + empty `--logo` → exit 0
- Warm daemon: two sequential 1280×720 balanced exports → both exit 0

## Follow-ups

- Re-verify on installed frozen build (`Camxora.exe --visualizer-daemon` path).
- User acceptance test from Video workspace UI with real project assets.
