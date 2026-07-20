# FrameIntegrator slice 2 — camera shake + bg vibrate

**Date:** 2026-07-19  
**Status:** implemented (local)

## Summary

REQ-2.1 slice 2 centralizes camera shake and background vibrate integration in `frame_integrator.py`, wires preview `paintGL` and remaining `gpu_render.py` export paths to shared kick/bass + shake helpers, and fixes live preview camera shake (was declared but never updated).

## Product impact

- Live preview camera shake now applies to spectrum/logo anchor (matches export when `effects.camera_shake.enabled`).
- Background vibrate and kick/bass envelopes use the same integrator on preview and all GPU export paths.

## Technical impact

- New APIs: `integrate_camera_shake`, `integrate_bg_vibrate` (+ state/config dataclasses).
- `preview_widget.py` uses integrators; removed duplicate inline kick/bass and bg-vibrate blocks.
- `gpu_render.py` alternate paths (~thumbnail capture, GLFW live preview loop) use shared integrators.

## Files touched

- `camxora_python/visualizer/frame_integrator.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_frame_integrator.py`

## Migration / deploy

None.

## Tests

- `python -m pytest tests/test_frame_integrator.py -q` — 9 passed

## Follow-ups (slice 3)

- Extract particle audio/trigger envelope integration into `frame_integrator`.
- Wire `preview_worker.py` shake state to integrator.
- Consolidate duplicate spectrum FFT smoothing blocks across preview/export.
