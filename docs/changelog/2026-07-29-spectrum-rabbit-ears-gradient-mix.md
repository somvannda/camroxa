# Spectrum rabbit ears top→bottom + gradient mix palettes

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Rabbit ears (Inward) now hang from the **top** of the ring and raise toward the center (top → bottom). Around-ring gradients use smoothstep + neighbor mixing so hues join instead of hard color wedges, and built-in/style palettes were retuned to neon multi-stop sets that mix better.

## Product impact

- **Before:** Inward rabbit ears sat on the bottom arc (or looked static at the crest); ring colors often showed hard teal | green | blue bands; presets included flat RGB primaries.
- **After:** Inward crest raises from top downward into the logo; colors blend across the ring; gradient presets favor neon cyan / violet / magenta / heat mixes.

## Technical impact

- `resolve_curved_spectrum_basis("bottom")` uses top semicircle (`π/2`) with `radial_sign=-1`.
- `build_spectrum_vertex_rgba` applies Hermite smoothstep between stops and circular neighbor mixing.
- `SPECTRUM_GRADIENT_PRESET_OPTIONS` and `STYLE_PRESET_PATCHES` colors refreshed (removed harsh RGB Flow / flat emerald triples).

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `camxora_python/tests/test_spectrum_color_engine.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-rabbit-ears-gradient-mix.md`

## Migration / deploy

- Desktop-only. Restart the app.
- Re-select **Inward (rabbit ears — top→bottom)** and/or a new gradient preset if the draft still holds old solid-band colors.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py camxora_python/tests/test_spectrum_color_engine.py`

## Follow-ups

- Optional: expose a “gradient softness” slider if users want harder wedges back.
- Existing saved drafts keep their old `gradientColors` until the user picks a new preset.
