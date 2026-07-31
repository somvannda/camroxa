# Spectrum ring side + face-out raise

**Date:** 2026-07-29  
**Status:** implemented (desktop branch)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Clarifies **Ring Side** (Top/Bottom/Left/Right/All around): side chooses *where bars sit*; each bar raises *the way it faces* (radially), not all bars shoving one screen direction.

## Product impact

- **Before:** “Bar Growth → Top” sat bars on the top arc but raised every bar straight up.
- **After:** Control is **Ring Side**. Top/Bottom/Left/Right = that arc; each bar raises outward along its face. **All around — face out/in** = full ring spikes out or into the circle.

## Technical impact

- `generate_points_curved(..., gravity=top|…)` uses per-bar radial normals for side modes (same as outward).
- UI label: Bar Growth → Ring Side; option copy updated.
- Linear rows still use uniform Top/Left/Right/Bottom raise (a straight row has one face).

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-ring-side-face-raise.md`

## Migration / deploy

- Desktop-only. Restart Camxora.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py -q`

## Follow-ups

- Optional: separate “Face out / Face in” toggle paired with Ring Side for side arcs facing inward.
