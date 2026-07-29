# Spectrum Top raise + dark crystal-clear colors (no glow)

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Bar Growth **Top** now forces Circle Raise (180°) on the top arc with outward twin-peak raise (opposite of rabbit ears). Style / stacked presets use **darker saturated** gradients with **glow=0 / blur=0** for crystal-clear spectrum color (no soft glow wash).

## Product impact

- **Before:** Top looked identical to Outward / did nothing useful on full-circle or linear; style colors were bright neon with soft glow haze.
- **After:** Top = clear upward ears on the top arc. Colors are deep ruby / indigo / teal / ember bands with sharp edges and no glow passes by default.

## Technical impact

- Selecting Top or Rabbit ears always patches `curved=True`, `mirrored=False`.
- Top uses `radial_sign=+1` + ear amplitude bias; Rabbit ears keep inward + radius inflate.
- `SPECTRUM_GRADIENT_PRESET_OPTIONS` + `STYLE_PRESET_PATCHES` + stacked layers retuned; neighbor color wash removed.
- Glow Strength / Softness sliders remain available if the user wants glow later (defaults 0).

## Files touched

- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `camxora_python/tests/test_spectrum_color_engine.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-top-dark-crystal-colors.md`

## Migration / deploy

- Desktop-only. **Restart Camxora**.
- Re-select a spectrum **style** (or set Glow Strength / Softness to 0) so dark colors + no glow apply to the current draft.
- Try Bar Growth **Top (raise up from top arc)**.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py camxora_python/tests/test_spectrum_color_engine.py -q`

## Follow-ups

- Optional “crystal / glow” style toggle in the inspector.
