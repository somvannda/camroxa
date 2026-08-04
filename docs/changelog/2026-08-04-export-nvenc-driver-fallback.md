# Export falls back to x264 when NVENC driver is too old

**Date:** 2026-08-04  
**Status:** implemented (desktop 1.0.19+)  
**Surfaces:** `camxora_python` installer

## Summary

Video export failed immediately after “Encoder started (NVENC…)” with:

`Driver does not support the required nvenc API version. Required: 13.0 Found: 12.2`  
(`BrokenPipeError` / FFmpeg pipe closed)

Bundled FFmpeg needs NVIDIA driver **570+** for NVENC. The old fallback only
switched to libx264 if FFmpeg exited within ~200ms of spawn — NVENC often stays
alive until the first frames are written, so the mismatch never triggered
fallback and the export crashed.

## Fix

- Probe `h264_nvenc` with a one-frame lavfi encode before starting the pipe.
- If the probe fails (or `CAMXORA_FORCE_X264=1`), start with **libx264**.
- Keep a post-spawn safety net that rewrites NVENC → x264 when stderr shows
  driver/API/unknown-encoder failures.
- Remember NVENC is unavailable for the rest of the process so later tracks in
  a batch do not hit the same failure.
- After a driver update + app restart, the probe runs again and NVENC is used.

## Workaround (without this build)

Update the NVIDIA Game Ready / Studio driver to **570.0 or newer**, then retry
export.

## Files

- `camxora_python/visualizer/nvenc_capability.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/encode_pipeline.py`
- `camxora_python/visualizer/main.py`
- `camxora_python/tests/test_nvenc_capability.py`
- `docs/changelog/2026-08-04-export-nvenc-driver-fallback.md`
- `CHANGELOG.md`
