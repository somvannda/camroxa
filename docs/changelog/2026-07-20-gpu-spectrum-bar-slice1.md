# GPU spectrum vertex path — slice 1 (bar export)

**Date:** 2026-07-20  
**Status:** implemented (sandbox pending deploy)

## Summary

Adds an optional GPU instanced-bar spectrum path for export (`run_gpu_render`). Smoothed FFT bins upload as a 64×1 R32F texture each frame; bar quads expand in a vertex shader instead of rebuilding full vertex buffers on the CPU. Slice 1 covers default bar geometry only (`orbit-spikes` / classic vertical bars). Waveform styles and specialized bar styles remain on the existing CPU `_spectrum_fast.build_bar_vertices` path.

## Product impact

- **Before:** Every export frame rebuilt bar vertex buffers in NumPy (64 bars × glow passes × layers).
- **After:** With `CAMXORA_GPU_SPECTRUM=1`, default bar layers upload ~256 bytes of FFT data per frame and draw via instancing. Default export behavior unchanged (flag off).

## Technical impact

- New module `visualizer/spectrum_gpu.py` — FFT/color texture packing, instanced bar shader, layer registration.
- `visualizer/gpu_render.py` — pre-registers static bar layouts before the frame loop; per-frame GPU draw when enabled.
- Env flag: `CAMXORA_GPU_SPECTRUM=1` (default off).

## Files touched

- `camxora_python/visualizer/spectrum_gpu.py` — new
- `camxora_python/visualizer/gpu_render.py` — GPU path integration in `run_gpu_render`
- `camxora_python/tests/test_spectrum_gpu.py` — new unit tests (no GL)
- `CHANGELOG.md` — unreleased entry
- `docs/GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md` — REQ-2.3 slice 1 note

## Migration / deploy

No migration. Enable locally for benchmarking:

```powershell
$env:CAMXORA_GPU_SPECTRUM = "1"
```

## Tests

- `pytest camxora_python/tests/test_spectrum_gpu.py -v`
- `pytest camxora_python/tests/test_export_golden_frames.py -v` (GPU + display required; flag off by default)

## Follow-ups — slice 2

- GPU paths for remaining bar styles: `mirror-blades`, `signal-needles`, `pulse-beads`, `grid-steps`, `ignition-flare`, `drift-capsules`.
- GPU waveform styles (`aurora-ribbon`, `magma-ridge`, `plasma-bloom`) via triangle-strip shader.
- Curved `fillCircle` fan pass on GPU.
- Preview widget parity (`preview_widget.py`) behind the same flag.
- Benchmark CPU usage delta on 3-minute 1080p fixture per REQ-2.3 acceptance.

## Incident — benchmark A texture crash (2026-07-20)

**Symptom:** `CAMXORA_GPU_SPECTRUM=1` export crashed in `register_layer()` with `_moderngl.Error: data size mismatch 1024 != 256`.

**Root cause:** Per-pass color textures were allocated at fixed `(_BINS, 1)` with ModernGL default `dtype='f1'` (256 bytes for 64 texels), while `pack_color_rgba_texture()` supplies **RGBA32F** data (1024 bytes for 64 bars). The `256` in the error is the **expected f1 byte size**, not bar count 16.

**Fix:** Allocate color textures at `(n, 1)` with `dtype="f4"` to match packed float32 colors; pad FFT uploads to `_BINS` width in `draw_pass()`. Pre-register fallback default spectrum layer when template `layers` is empty (matches per-frame fallback).

**Benchmark A (180 s, subprocess, RTX 3060):** exit 0, **0.26× realtime** (704 s wall) — same as CPU baseline; Phase 2 ≥5× gate not met. `CAMXORA_INPROCESS_EXPORT=1` does not apply to `scripts/benchmark_gpu_export.py` (cold `ExportJob` subprocess).

**Tests:** `pytest camxora_python/tests/test_spectrum_gpu.py camxora_python/tests/test_export_golden_frames.py -q` — 12 passed.
