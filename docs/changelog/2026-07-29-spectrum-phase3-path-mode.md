# Spectrum Phase 3: pathMode circle|rect + LogoBounds

**Date:** 2026-07-29  
**Status:** implemented (desktop branch)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Phase 3 lets spectrum bars follow a **rectangle perimeter** around square logos. Layer field `pathMode` (`auto` / `circle` / `rect`) plus a small `LogoBounds` DTO keep Logo ↔ Spectrum coupling narrow. Preview and export share `generate_spectrum_layer_geometry()`.

## Product impact

- **Before:** Attached spectrum always sat on a circle, even with a square (unmasked) logo.
- **After:** **Path Shape → Auto** uses a rectangle path when attached to a square logo (Full Circle walks all four edges; Circle Raise uses the Bar Growth edge). Force **Circle** or **Rectangle** to override.

## Technical impact

- `pathMode` on spectrum layers (normalized in `template_runtime`).
- `LogoBounds` / `build_logo_bounds` / `normalize_logo_shape` in `logo_spectrum_bindings.py`.
- `generate_points_rect` + `generate_spectrum_layer_geometry` in `_spectrum_fast.py`.
- Preview + export (including GPU pre-register and legacy loops) dispatch through the shared helper.
- Layer editor: **Path Shape** combo.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/lib/logo_spectrum_bindings.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_phase3_path_mode.py`
- `docs/SPECTRUM_ENHANCEMENT_PHASES.md`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-phase3-path-mode.md`

## Migration / deploy

- Desktop-only. Restart Camxora.
- Set Logo shape to **Square**, keep **Attach Spectrum**, Circle Form **Full** or **180°**, Path Shape **Auto** (default).

## Tests

- `pytest camxora_python/tests/test_spectrum_phase3_path_mode.py -q`

## Follow-ups

- Phase 4: particle motion trails.
- Optional: rounded-rect corners; AABB half_w/half_h from logo alpha instead of square half-size.
- Optional: remove Logo “Attach Spectrum” if ring always tracks logo size.
