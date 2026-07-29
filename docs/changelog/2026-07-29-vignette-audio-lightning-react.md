# Vignette audio/lightning reaction

**Date:** 2026-07-29  
**Status:** implemented (desktop)

## Summary

Background **Vignette** now has **Vignette Audio React**. On bass/kick and lightning strikes, the vignette opens (opacity/strength drop) so a bright background can flash through with the bolt. Lightning peak flash also adds a small brightness punch even when background Audio Reactivity is low.

## Product impact

- **Before:** Vignette was static; bright backgrounds stayed boxed in dark corners during lightning.
- **After:** Background → Corner Effects → **Vignette Audio React** (0–5). Raise it with Vignette on + a brighter Brightness setting; strikes open the corners and lift the plate with the bolt.

## Technical impact

- Template: `effects.vignette.reactivity` (draft key `vignetteReactivity`).
- Shared helpers: `peak_lightning_flash`, `apply_vignette_reactivity` in `lightning_render.py`.
- Preview + all three `gpu_render` atmosphere paths apply the same flash env.

## Files touched

- `camxora_python/features/video/lib/lightning_render.py`
- `camxora_python/features/video/lib/video_template_draft.py`
- `camxora_python/features/video/lib/video_template_save.py`
- `camxora_python/features/video/lib/template_draft_domains.py`
- `camxora_python/features/video/lib/background_style_registry.py`
- `camxora_python/features/video/widgets/background_inspector.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_lightning_layers.py`

## Migration / deploy

- Desktop-only. Restart the app. Existing templates default `reactivity: 0` (no change until the slider is raised).

## Tests

- `pytest camxora_python/tests/test_lightning_layers.py` (includes vignette react + lightning peak flash).

## Follow-ups

- Optional smoke opacity react on the same flash env.
