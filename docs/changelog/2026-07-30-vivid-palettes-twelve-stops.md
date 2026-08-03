# More vivid color palettes + up to 12 gradient stops

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart required)

## Summary

Spectrum / particle Color Engine palettes were limited and capped at 5 stops. The shared catalog now includes more vivid multi-stop presets (rainbow / carnival / laser looks), and users can add up to **12** gradient/palette stops via Add Color / Add Stop.

## Product impact

- **Before:** ~12 milder presets; Add Color stopped at 5 stops.
- **After:** 24 vivid presets (shared by Spectrum gradient + Particle palette dropdowns). Add Color / Add Stop works up to 12 stops. New presets include Carnival Riot, Hyper Pop, Rainbow Rush, Laser Party, Full Spectrum, Ultraviolet Sweep, Cyber Rainbow, and more.

## Technical impact

- `MAX_GRADIENT_COLOR_STOPS` raised 5 → 12 in `spectrum_color_engine.py` (also used by particles + text normalize).
- Expanded `SPECTRUM_GRADIENT_PRESET_OPTIONS`; particles inherit via alias.
- Spectrum / particle editors use the constant instead of hardcoded `5`.
- Electron `spectrumColorEngine.ts` kept in sync for the same catalog/cap.

## Files touched

- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/widgets/particle_color_editor.py`
- `camxora_python/tests/test_spectrum_color_engine.py`
- `camxora/src/renderer/src/features/video/domains/spectrum/spectrumColorEngine.ts`
- `docs/changelog/2026-07-30-vivid-palettes-twelve-stops.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart the app. No API/DB migrate. Existing templates keep their colors until you pick a new preset or add stops.

## Tests

- `pytest camxora_python/tests/test_spectrum_color_engine.py`

## Follow-ups

- Optional: “Apply this palette to all engines” (spectrum + particles + lightning + background accents).
- Optional: Raise Scroll control for shifting spectrum energy left↔right.
