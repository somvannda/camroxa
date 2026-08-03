# Spectrum save overwrite + Row Width regression

**Date:** 2026-08-03  
**Status:** implemented (desktop local; full app restart required)  
**Branch:** `fix/spectrum-save-and-row-width`

## Summary

Restored previously-shipped Spectrum fixes that had regressed: template Save was rebuilding from a stale `spectrumInstances` snapshot (always snapping back to Orbit Spikes / original look); linear rows were hard-capped at 80% of preview width with the Row Width control missing; and Raise Scroll helpers/UI were missing while preview/export still called them.

## Product impact

- **Before:** Editing an existing or new Spectrum template then Save reloaded the original Orbit Spikes look. Linear spectrums could not span the full preview. Raise Scroll was unavailable.
- **After:** Save persists the live Spectrum instance (style, layers, position, audio). **Row Width (preview span)** is back; `1.0` = full preview width. **Raise Scroll** is back in the layer editor.

## Technical impact

- `_save_template` / server sync pass `spectrum_instances=self._spectrum_instances` after flush; blank-template first-save preserves live instances.
- `clamp_linear_span` + `linear_span` restored on `generate_spectrum_layer_geometry` (call sites in preview/export already passed it).
- `clamp_frequency_scroll` + `scroll_spectrum_heights` restored (required by preview/export imports).
- Spectrum layer editor restores Row Width (`linearSpan`) and Raise Scroll (`frequencyScroll`).

## Files touched

- `camxora_python/features/video/views/video_view.py`
- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_instances.py`
- `docs/changelog/2026-08-03-spectrum-save-and-row-width-regression.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart the Camxora desktop app. No API / DB / sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_spectrum_instances.py camxora_python/tests/test_spectrum_linear_span.py camxora_python/tests/test_spectrum_bar_width.py camxora_python/tests/test_spectrum_frequency_scroll.py`

## Follow-ups

- None.
