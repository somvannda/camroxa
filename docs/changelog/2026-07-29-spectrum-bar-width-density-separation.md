# Spectrum bar width, density ceiling, and height label clarity

**Date:** 2026-07-29  
**Status:** implemented (desktop; restart app to pick up UI)  
**Branch:** `fix/desktop-cli-env-arg` (spectrum worktree)

## Summary

Clarified that Global Height Gain and Bar Length are not duplicates, made Bar Width visibly drive thickness while reserving a gap between bars, and raised per-layer density max from 128 to 192. Width and density share the same slot along the ring, so high density correctly lowers the usable width ceiling to keep bars separated.

## Product impact

- **Before:** “Bar Height” vs “Spike Height” looked like duplicates; Bar Width often felt stuck (high density soft-capped width near full slot, needles used only 28% of width); density topped out at 128; bars could nearly touch.
- **After:** Labels/tooltips distinguish global gain vs per-layer length; width tracks the slider until a ~28% gap reservation; density goes to 192; needle styles track width more clearly (~55%).

## Technical impact

- `resolve_bar_pixel_width` reserves `_BAR_SLOT_MAX_FILL` / `_BAR_MIN_GAP_PX` instead of filling 95% of the slot.
- `_MAX_BAR_COUNT` and template normalization clamp to 192.
- Needle half-width scale updated in fast builder, GPU helper, and export CPU path.

## Files touched

- `camxora_python/visualizer/_spectrum_fast.py`
- `camxora_python/visualizer/spectrum_gpu.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/widgets/spectrum_layer_editor.py`
- `camxora_python/tests/test_spectrum_bar_width.py`
- `camxora_python/tests/test_spectrum_gravity.py`
- `camxora_python/tests/test_spectrum_gpu.py`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-bar-width-density-separation.md`

## Migration / deploy

- Desktop-only. Restart the Camxora desktop app from this worktree.
- No API / DB / sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_spectrum_bar_width.py camxora_python/tests/test_spectrum_gravity.py camxora_python/tests/test_spectrum_gpu.py`

## Follow-ups

- Optional: show effective max width in the slider label when density clamps it.
- Screenshot still showing Curve 180 / Mirror 360 means an older UI binary — restart to get Circle Form.
