# Spectrum bar growth: Top / Bottom / Left / Right only

**Date:** 2026-07-29  
**Status:** implemented (desktop)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Removed rabbit-ears / Outward special modes. Bar Growth is only **Top**, **Bottom**, **Left**, and **Right** — bars raise in that screen direction on both linear and circular layouts.

## Product impact

- **Before:** Outward + rabbit-ears / inward special cases; confusing and often looked broken.
- **After:** Four clear directions. Top raises up, Bottom down, Left left, Right right. On a circle, bars sit on that side and raise that way.

## Technical impact

- `normalize_spectrum_gravity()` maps legacy `normal` → `top`.
- `resolve_curved_spectrum_basis()` returns `(start_angle, growth_dx, growth_dy)`; curved bars use uniform screen-space raise (not radial inward).
- Removed `resolve_inward_draw_radius` / `rabbit_ear_length_multipliers`.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/features/video/lib/spectrum_style_registry.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `camxora_python/tests/test_spectrum_gpu.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-directional-bar-growth.md`

## Migration / deploy

- Desktop-only. **Restart Camxora**.
- Old drafts with `gravity: "normal"` become Top automatically.

## Tests

- `pytest camxora_python/tests/test_spectrum_gravity.py camxora_python/tests/test_spectrum_gpu.py -q`

## Follow-ups

- Logo “Attach Spectrum” toggle still separate; can remove later if still unwanted.
