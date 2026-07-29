# Spectrum radial bar spikes (outside / inside)

**Date:** 2026-07-29  
**Status:** implemented (desktop branch)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Adds two radial **Bar Growth** modes for classic circle spikes: **Outside** (bars raise away from the ring) and **Inside** (bars raise into the circle). Works on circle and rectangle paths.

## Product impact

- **Before:** Bar Growth was only Top / Bottom / Left / Right (uniform screen raise on one side).
- **After:** Also **Outside (spikes out)** and **Inside (spikes in)**. Picking either on a Linear layer auto-enables Full Circle Raise.

## Technical impact

- Gravity values `outward` / `inward` (+ aliases `outside` / `inside`).
- `generate_points_curved(..., gravity=)` sets per-bar radial normals.
- Rect path: radial modes walk the full perimeter; inward negates edge normals.
- Template normalizer accepts the new values.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-radial-bar-spikes.md`

## Migration / deploy

- Desktop-only. Restart Camxora.
- Spectrum Layers → Bar Growth → Outside or Inside; use Full Circle Raise for a full ring.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py -q`

## Follow-ups

- Optional: clamp inward spike length so tips stop before the logo.
