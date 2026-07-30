# Fix Fill Circle / Floor Reflection / Peak Caps toggles

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart)

## Summary

Layer toggles looked broken on many templates because each had a different silent gate: Peak Caps required Peak Hold Blend > 0, Fill Circle only drew on waveform styles, and Floor Reflection mirrored through the ring center (a no-op on circular spectra).

## Product impact

- **Peak Caps:** Checkbox alone shows caps; if Peak Hold Blend was 0 it auto-arms to 0.45.
- **Fill Circle:** Works on bar styles (Orbit Spikes, etc.) and auto-enables Circle Form when needed.
- **Floor Reflection:** Mirror sits *under* the spectrum instead of flipping through its center.

## Technical impact

- `mirror_spectrum_points_vertical` shifts the copy below ~2R
- Preview + GPU export: peak-cap effective hold; bar-style fill fan
- Layer editor blocks bind noise; tooltips clarify behavior

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_layer_toggles.py`
- `docs/changelog/2026-07-30-spectrum-layer-toggles.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart app; re-toggle the checkboxes on an affected template.

## Tests

- `pytest camxora_python/tests/test_spectrum_layer_toggles.py`
