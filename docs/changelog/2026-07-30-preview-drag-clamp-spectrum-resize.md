# Preview drag clamp + freer spectrum length/width

**Date:** 2026-07-30  
**Status:** implemented (desktop local; full app restart required)

## Summary

Dragging Spectrum, Logo, or Lightning on the preview could push objects far outside the visible frame (legacy ±1000 template-unit clamp). Drag is now clamped so the object center stays inside the preview, flush to edges (no forced inset). Linear spectrums were hard-capped at 80% of frame width; they can now span the full preview via **Row Width**. Spectrum size controls were also opened up (Bar Length / Width / gap / Global Height Gain).

## Product impact

- **Before:** Spectrum/logo could be dragged off-canvas; linear rows stopped ~80% wide with side gaps; a 6% margin blocked sitting flush on the bottom; height/width sliders topped out early.
- **After:** Drag keeps the center in-frame and allows flush bottom/side placement. **Row Width (preview span)** goes to **1.0 = full preview width**. Use **Bar Length**, **Bar Width**, **Layer Gap / Ring Size**, and **Global Height Gain** for freer sizing.

## Technical impact

- `clamp_template_offset_to_preview` (default `margin_frac=0`) in preview mouse-move for lightning / logo / spectrum.
- Layer field `linearSpan` (0.1–1.0, default 1.0) drives linear path length in `generate_spectrum_layer_geometry` (preview + export).
- Runtime clamps: thickness ≤ 600, barWidth ≤ 240, radiusOffset ≤ 800; bar height mult ≤ 12.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_preview_drag_clamp.py`
- `camxora_python/tests/test_spectrum_linear_span.py`
- `camxora_python/tests/test_spectrum_bar_width.py`
- `docs/changelog/2026-07-30-preview-drag-clamp-spectrum-resize.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart the app. Existing linear templates without `linearSpan` normalize to **1.0** (full width). Dial **Row Width** down if you want the old ~80% look. No API/DB migrate.

## Tests

- `pytest camxora_python/tests/test_preview_drag_clamp.py camxora_python/tests/test_spectrum_linear_span.py camxora_python/tests/test_spectrum_bar_width.py`

## Follow-ups

- Optional: clamp numeric X/Y inspector fields the same way as drag.
- Optional: hide Row Width when Circle Form is on (ring modes ignore it).
