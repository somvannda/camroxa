# REQ-2.3 slice 2 — more GPU bar styles + docs status

**Date:** 2026-07-20  
**Status:** implemented

## Summary

Extended the GPU instanced spectrum path to cover remaining single-quad slice-2 bar styles (mirror, drift, ignition/neon). Updated `GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md` / `VIDEO_EXPORT_ROADMAP.md` status tables to match shipped Phase 2 work. NativeEncodeBridge C++ scaffold proceeds in parallel (not deferred).

## Product impact

- With `CAMXORA_GPU_SPECTRUM=1`, more marketplace bar styles stay on the GPU path during export (lower CPU on GTX 1050 Ti–class cards).
- Still CPU: `pulse-beads` / `dot-matrix`, all waveform styles (e.g. Bass Drive `liquid`).

## Technical impact

- Vertex shader `style_mode`: 0 default, 1 mirror, 2 drift; `style_sf` for drift offsets.
- Docs: Phase 2 REQs marked done/partial; REQ-3.5 explicitly not deferred.

## Files touched

- `camxora_python/visualizer/spectrum_gpu.py`, `gpu_render.py`
- `camxora_python/tests/test_spectrum_gpu.py`
- `docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md`, `docs/VIDEO_EXPORT_ROADMAP.md`
- `CHANGELOG.md`

## Migration / deploy

No migration. Optional: `$env:CAMXORA_GPU_SPECTRUM=1`.

## Tests

- `pytest tests/test_spectrum_gpu.py` — pass.

## Follow-ups

- Beads/dot-matrix multi-quad GPU; waveform GPU; preview parity.
- NativeEncodeBridge real NVENC after stub scaffold.
- Phase 2 exit: default-on in-process + 1050 Ti ≥5× + v0.4.0.
