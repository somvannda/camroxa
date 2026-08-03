# Spectrum rabbit ears visible top→bottom raise

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Inward rabbit ears looked broken because tips grew into/under the logo and `fillCircle` painted a near-static disk. The ring now seats outside the logo, tips raise top→bottom toward center (visible), twin-ear amplitude bias shapes the crest, and center-fill is disabled for inward growth.

## Product impact

- **Before:** Choosing Rabbit ears / Inward often looked unchanged (tips hidden under logo; plasma fill covered the center).
- **After:** Rabbit ears hang from the top and clearly pulse toward the logo; twin peaks appear on the top shoulders.

## Technical impact

- `resolve_inward_draw_radius()` inflates base radius by ~0.92× bar length when `radial_sign < 0`.
- `rabbit_ear_length_multipliers()` boosts top shoulder bins.
- Preview + export skip `fillCircle` TRIANGLE_FAN when growing inward.
- UI label: **Rabbit ears (hang top→bottom)**.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-rabbit-ears-visible-raise.md`

## Migration / deploy

- Desktop-only. **Restart Camxora** (running process still has old modules loaded).
- Select **Rabbit ears (hang top→bottom)**; use Circle Raise or Full Circle.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py -q`

## Follow-ups

- Optional softness slider for ear bias strength.
