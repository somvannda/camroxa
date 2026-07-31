# Spectrum vivid colors, free position, live audio knobs

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Retuned built-in and stacked spectrum recipes for vivid RGB (no white lead stops, lower glow, normal blend). Spectrum position is independent of the logo unless **Attach Spectrum to Logo** is on. Desktop Audio UI now only shows knobs that actually affect the Python renderer, and Motion Smoothing is wired correctly.

## Product impact

- **Before:** Many presets looked washed (white gradients + high additive glow). Moving spectrum also moved the logo. Several Audio/Advanced dials did nothing on desktop.
- **After:** Fresh style/stacked applies look saturated and premium by default. Detached spectrum moves freely with logo centered; attached mode still locks ring + shared position. Audio shows Input Gain, Motion Smoothing, Peak Hold Blend only.

## Technical impact

- `STYLE_PRESET_PATCHES` / `STACKED_LAYER_PRESETS` / gradient picker presets retuned.
- `resolve_spectrum_logo_centers()` in `logo_spectrum_bindings.py`; preview + export use it.
- `template_normalizer` maps `motionSmoothing` → `smoothing` (was deleting smoothing).
- Spectrum inspector hides dead Kick/Bass/Contrast/Transient/Treble/Flying Glow controls.

## Files touched

- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/features/video/lib/logo_spectrum_bindings.py`
- `camxora_python/features/video/services/template_normalizer.py`
- `camxora_python/features/video/widgets/spectrum_inspector.py`
- `camxora_python/features/video/widgets/logo_inspector.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_spectrum_vivid_and_position.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-vivid-position-audio.md`

## Migration / deploy

- Desktop-only. Restart app.
- Re-apply a Spectrum style (or stacked preset) / Restore original to pick up new factory colors on existing sessions.
- No API / sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_spectrum_vivid_and_position.py camxora_python/tests/test_spectrum_inspector.py camxora_python/tests/test_spectrum_color_engine.py camxora_python/tests/test_video_domain_inspectors.py`

## Follow-ups

- Optional: port Electron Kick/Bass/Contrast analysis into Python if those dials should return.
- Existing saved templates keep their old colors until user re-applies a style or restores original.
