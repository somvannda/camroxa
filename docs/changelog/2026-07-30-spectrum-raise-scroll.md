# Spectrum Raise Scroll — free spike position along path

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart required)

## Summary

Default linear spectrums put bass/spikes on one side. A new continuous **Raise Scroll (along path)** layer control slides that energy freely left↔right (or around a ring) — not three fixed left/center/right options.

## Product impact

- **Before:** Spikes stayed fixed on the bass-left (or mirrored center) mapping; no way to slide the raise.
- **After:** Spectrum layer editor → **Raise Scroll (along path)** (`0.00`–`0.99`). Drag freely; `0` = default bass-left. Works on linear rows and circular rings.

## Technical impact

- Layer field `frequencyScroll` (wrap `[0, 1)`).
- `scroll_spectrum_heights` applied after mirror/smooth, before resample (preview + export).
- Normalized in `template_runtime`.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_frequency_scroll.py`
- `docs/changelog/2026-07-30-spectrum-raise-scroll.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart the app. Existing layers default to `0` (unchanged look).

## Tests

- `pytest camxora_python/tests/test_spectrum_frequency_scroll.py`

## Follow-ups

- None.
