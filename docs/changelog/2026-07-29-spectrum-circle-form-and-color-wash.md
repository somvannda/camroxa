# Spectrum UI: circle form + color wash fixes

**Date:** 2026-07-29  
**Status:** implemented (desktop branch)

## Summary

Clarified Spectrum layer controls that were confusing (unlabeled Gravity vs Blend dropdowns), added explicit **Circle Form** options for semicircle vs full-circle bar raise, and fixed several color-quality issues that made most spectrum styles look washed-out / “cheap.”

## Product impact

**Before**
- Two unlabeled dropdowns stacked: top = growth direction, bottom = blend mode. Changing the bottom one made colors look brighter/washed, which felt like a broken color control.
- Full-circle raise required finding “Mirror 360” checkbox.
- Glow passes and Additive/Screen blending washed saturated colors toward white haze.
- Radial / Circular / Diagonal gradient directions mostly did nothing different from Around-ring.
- Ignition Flare looked like thick blocky bars.

**After**
- Labeled controls: **Circle Form**, **Bar Growth**, **Blend Mode** (with warnings that Additive/Screen can wash colors).
- Circle Form: Linear / Circle Raise (180°) / Full Circle Raise (360°).
- Glow passes keep more saturated color (dampened RGB instead of white haze).
- Radial = Base→Tip, Circular = Around Ring, Diagonal blends both.
- Ignition Flare uses tapered tips (wider base, sharper tip).

## Technical impact

- `spectrum_layer_editor.py`: circle-form combo maps to `curved` + `mirrored`.
- `spectrum_color_engine.py`: radial/diagonal/circular mapping + `dampen_spectrum_glow_rgba`.
- Preview + export glow passes use dampened colors.
- Ignition geometry taper in `_spectrum_fast.py` and legacy `gpu_render.py` paths.

## Files touched

- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/tests/test_spectrum_color_engine.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-circle-form-and-color-wash.md`

## Migration / deploy

- Desktop-only. Restart app to pick up UI + renderer changes.
- Existing templates keep working; open Layers and set Circle Form to **Full Circle Raise (360°)** when you want a full ring.

## Tests

- Unit tests for glow dampen + radial/diagonal bar quads.

## Follow-ups

- Consider defaulting new circular templates to Full Circle Raise + Blend Normal + glow ≤ 25.
- Optional: remove white from default gradient presets (white stops amplify wash).
