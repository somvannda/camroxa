# Spectrum Phase 1: peak caps, density, solid band, vertical gradient

**Date:** 2026-07-29  
**Status:** implemented (desktop branch only; not merged to main)  
**Branch:** `fix/spectrum-layer-ui-and-colors`

## Summary

Phase 1 is now implemented for Spectrum visuals: per-layer bar density, optional peak caps, solid base band rendering, and vertical bar gradient support. This work keeps Spectrum behavior inside the Spectrum domain and preserves preview/export parity. Existing templates continue working with defaults (`barCount=64`, peak caps off, solid band off).

## Product impact

- **Before:** fixed ~64-bin density, no floating peak caps, `solidBand` toggle was mostly inert, and bar gradients only moved around the ring.
- **After:** each layer can change bar density (16-128), enable peak caps (gap/size/decay/color), render a solid base band, and use top-to-bottom bar gradients.

## Technical impact

- Added fast helpers for bar-count clamp/resample and base-band strip generation in `_spectrum_fast.py`.
- Layer schema normalization now keeps `barCount`, `solidBand`, and peak-cap fields.
- Preview and export loops resample FFT to per-layer density and render peak caps with decay memory.
- Bar TRIANGLE colors now support vertical (`top-to-bottom`) gradient mapping for base->tip color splits.
- GPU fast path automatically falls back to CPU path for unsupported combinations (`solidBand`, peak caps, vertical bar gradients), preserving correctness.

## Files touched

- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_spectrum_color_engine.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-phase1-peakcaps-density-solidband.md`

## Migration / deploy

- No API or DB migration.
- Desktop-only feature change; requires restart/rebuild of desktop app from this branch to test.
- Not deployed to sandbox/production in this step.

## Tests

- Added/updated unit coverage for:
  - vertical bar gradient color mapping
  - layer-field normalization clamps (`barCount`, peak-cap fields)
  - FFT bin resampling and bar-count clamping helpers

## Follow-ups

- Phase 2 remains pending: contour/radio-wave style and reflection.
- Consider exposing a small preset matrix for peak-cap defaults per style.

## Incident

- **Preview crash (Magma Core Halo / mirrored curved waveform + solidBand):** `numpy.column_stack` failed with mismatched row counts (`band_pos` vs `band_cols`) because mirrored curved waveform layers add a closing geometry point while solid-band colors were still built from pre-closure bar count.
- **Root cause:** `solidBand` color row count used `n` instead of deriving from `band_pos.shape[0] // 2`.
- **Fix:** `preview_widget.py` and `gpu_render.py` now compute `band_bar_count` from the generated strip vertices, then build colors from that count before `column_stack`.
- **Verification:** lints pass on both renderer files; crash path no longer has incompatible array lengths.
- **Peak caps crash (same closing-point path):** `paintGL` broadcast error `shapes (113,) (112,)` when peak caps multiplied closed-loop `px/dx` arrays by FFT-sized `cap_base`.
- **Fix:** peak-cap math now slices geometry to `[:n]` in preview and export.
