# Export WYSIWYG: multi-Spectrum, Lightning, motion parity, 1080p60

**Date:** 2026-08-03  
**Status:** implemented (desktop local; full app restart required)  
**Branch:** `bugfix/export-spectrum-lightning-parity`

## Summary

Export now draws **all enabled Spectrum instances** (not only instance 0), samples Lightning and audio envelopes at preview rate (60 Hz) so 24 FPS exports still catch strikes, and passes the **live** Spectrum/Lightning state into manual and pipeline export. Export panel shows the resolved `WxH · FPS` so Standard/Master + Preferences `1920×1080` + FPS `60` is obvious.

## Product impact

- **Before:** Multiple Spectrums visible in preview; export often showed only the first. Lightning flashes looked sparse/wrong at 24 FPS. Unsaved Spectrum/Lightning edits could be missing from pipeline export.
- **After:** Export matches preview Spectrum stacks; Lightning peaks over the encode interval; live draft ships; panel shows effective resolution/FPS (Draft stays 720p@24).

## Technical impact

- `run_gpu_render` loops `_spectrum_draw_jobs` with per-instance center/style/audio/layers; GPU preregister keys are `(inst, layer)`.
- Analysis catch-up advances kick/bass/particle envelopes + peaks Lightning at 60 Hz; shake/bg vibrate use media `wall_time`.
- Manual/pipeline export flush + `spectrum_instances` / live lightning layers (same as preview).
- `render_lightning_layers_gl(..., flash_override=...)` keeps short strikes visible when encode FPS < 60.
- Preview shake/bg vibrate also use `wall_time=current_time` for deterministic media-clock motion.

## Files touched

- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/features/video/lib/lightning_render.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/widgets/export_queue_panel.py`
- `camxora_python/tests/test_spectrum_instances.py`
- `camxora_python/tests/test_lightning_layers.py`
- `docs/changelog/2026-08-03-export-wysiwyg-spectrum-lightning.md`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Fully restart the Camxora desktop app. No API / sandbox deploy.

## Tests

- `pytest camxora_python/tests/test_spectrum_instances.py camxora_python/tests/test_lightning_layers.py -q`

## Verify manually

1. Template with 2+ Spectrums → Standard, Preferences 1920×1080, FPS 60 → all Spectrums in the MP4.
2. Same at 24 FPS → Spectrums still present; Lightning still flashes.
3. Lightning positions/styles match preview.
4. Export panel shows `Output: 1920×1080 · 60 FPS` (Draft shows 720p · 24).
