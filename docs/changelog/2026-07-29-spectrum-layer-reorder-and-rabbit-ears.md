# Spectrum layer reorder, per-layer clarity, curved rabbit-ears

**Date:** 2026-07-29  
**Status:** implemented (local desktop; restart Camxora from this branch)  
**Branch:** `fix/spectrum-multi-stop-gradient`

## Summary

Spectrum Layers UI now supports **Up/Down reorder**, clearer labels for global vs per-layer controls, and Add/Duplicate auto-offsets **Layer Gap** so stacked rings are visible. Curved **Bottom (Rabbit Ears)** now grows **inward** (bottom→top on the lower ring) instead of matching Normal outward growth.

## Product impact

- **Before:** No way to change which ring draws on top; Bar Height looked like a per-layer control but affected all layers; new rings often sat on the same radius; curved rabbit-ears did nothing useful on circular layers.
- **After:** Up/Down reorders stack (last = on top). Labels mark “all layers” vs “this layer”. New rings get a larger Layer Gap. Bottom gravity flips radial growth inward.

## Technical impact

- `resolve_curved_spectrum_basis()` + `generate_points_curved(..., radial_sign)` shared by preview + export.
- `SpectrumLayerEditor` emits `layer_move_up_requested` / `layer_move_down_requested`.
- `VideoView` swaps layer list entries and selects the moved index.
- Opacity bind no longer treats missing values as `0`.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/widgets/spectrum_inspector.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-layer-reorder-and-rabbit-ears.md`

## Migration / deploy

- Restart desktop app from this branch to load UI + gravity fix.
- No API/DB migration. No sandbox deploy required for desktop-only change.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py -q`

## Follow-ups

- Optional: drag-and-drop reorder in the layer combo/list.
- Optional: move Bar Height into the Audio section entirely.
