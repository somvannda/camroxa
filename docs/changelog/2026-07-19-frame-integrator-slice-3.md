# FrameIntegrator slice 3 — particle audio + FFT smooth helper

**Date:** 2026-07-19  
**Status:** implemented (local)

## Summary

REQ-2.1 slice 3 centralizes particle reactive audio and spawn trigger envelope integration in `frame_integrator.py`, wires preview and all `gpu_render.py` export paths to `integrate_particle_audio`, deduplicates the log-FFT exponential smooth one-liner via `_spectrum_fast.smooth_fft_envelope`, and removes the redundant `_smooth_env` alias from `preview_widget.py`.

## Product impact

- No user-visible behavior change; particle spawn/reactivity and spectrum smoothing math unchanged.

## Technical impact

- New APIs: `integrate_particle_audio` (+ state/config dataclasses).
- `preview_widget._prepare_particle_audio` delegates to integrator.
- `gpu_render.py` main export, thumbnail, and GLFW live-preview loops use shared particle integrator.
- `smooth_fft_envelope` shared between preview `paintGL` and export frame loop.

## Files touched

- `camxora_python/visualizer/frame_integrator.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/tests/test_frame_integrator.py`

## Migration / deploy

None.

## Tests

- `python -m pytest tests/test_frame_integrator.py -q`

## Follow-ups (REQ-2.1 completion / REQ-2.7)

- Unified per-frame `FrameIntegrator.step()` returning all uniforms/state in one call.
- 60 Hz analysis sub-step loop shared between preview and export.
- Golden frame parity tests (preview PNG vs export PNG at t=1s, t=30s).
