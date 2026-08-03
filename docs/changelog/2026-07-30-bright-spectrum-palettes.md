# Bright spectrum style color palettes

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart + re-apply style preset)

## Summary

Replaced the dark spectrum gradient catalog (Ruby Night / Ember Dark / etc.) with 12 bright neon palettes, and wired every built-in style + stacked recipe to those palettes so factory looks read clear on the dark stage.

## Product impact

- **Before:** Style presets used deep navy/maroon stops that looked muddy on `#0a0e27`.
- **After:** Spectrum layer **Gradient Preset** dropdown shows bright sets (Neon Candy, Electric Sky, Prism Beam, …). Re-applying a style (Orbit Spikes, Magma Ridge, …) loads a matching bright palette.

## Technical impact

- `SPECTRUM_GRADIENT_PRESET_OPTIONS` rebuilt as bright catalog
- `STYLE_PRESET_PATCHES` / `STACKED_LAYER_PRESETS` consume that catalog (no duplicated hex lists)
- Fallback solid/gradient default shifted to cyan/magenta neons

## Files touched

- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/tests/test_spectrum_vivid_and_position.py`
- `docs/changelog/2026-07-30-bright-spectrum-palettes.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart app. Existing saved templates keep their old colors until you re-apply a style preset or pick a new gradient preset on the layer.

## Tests

- `pytest camxora_python/tests/test_spectrum_vivid_and_position.py`

## Follow-ups / clarity limits

Bright hex alone cannot fix every “muddy” look — see product note in the user reply (glow, additive blend, dark stage contrast, 8-bit sRGB, overlapping layers).
