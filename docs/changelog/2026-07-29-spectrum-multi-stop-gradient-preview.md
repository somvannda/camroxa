# Spectrum multi-stop gradient in live preview

**Date:** 2026-07-29  
**Status:** implemented (local; desktop restart to pick up)  
**Branch:** `fix/spectrum-multi-stop-gradient`

## Summary

Live Video preview only blended the **first and last** spectrum `gradientColors` stops, so middle palette colors were ignored. That made rich multi-stop templates look flat / “low color.” Preview now interpolates through every stop (up to 5), matching export. Nebula Pulse was retuned with a vivid magenta→cyan multi-stop ring.

## Product impact

- **Before:** A gradient like white / pink / violet / cyan rendered as a simple first→last blend in preview (middle stops discarded). Colors looked washed and sparse around circular rings.
- **After:** All configured stops paint around the spectrum. Nebula Pulse shows a full neon flow: magenta → deep pink → violet → cyan → aqua.

## Technical impact

- Shared helper `build_spectrum_vertex_rgba()` in `spectrum_color_engine.py`.
- Preview `mk_col_array` and export `_build_spectrum_vertex_colors` both use multi-stop interpolation.
- Local Nebula Pulse catalog entry updated (particles still off / glow 0 for smooth preview).

## Files touched

- `camxora_python/features/video/lib/spectrum_color_engine.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/tests/test_spectrum_color_engine.py`
- `CHANGELOG.md`
- Local AppData: `video-templates.json` (Nebula Pulse) + marketplace zip under `%LOCALAPPDATA%/Camxora/ready-templates/nebula-pulse/`

## Migration / deploy

- Desktop code change: restart Camxora from this branch / local tree to load the preview fix.
- No API/DB migration. No sandbox deploy required for AppData template retune.
- Marketplace zip refreshed at `%LOCALAPPDATA%/Camxora/ready-templates/nebula-pulse/NebulaPulse-marketplace.zip` (upload later if desired).

## Tests

- `python -m pytest camxora_python/tests/test_spectrum_color_engine.py -q` → 4 passed (includes multi-stop mid-bar green assertion).

## Follow-ups

- Optional: turn Nebula Pulse particles back on as sparse kick sparks once color look is approved.
- Optional: Admin marketplace upload of Nebula Pulse zip.
- **v1.4.0 local retune (2026-07-29):** matched Beattok/BassVolt profile — `magma-ridge`, `spectrumAttachToLogo: false`, wider/shorter bars — because attach-to-logo + thin tall `signal-needles` made preview/UI feel heavier than existing marketplace templates. Gradient builder also vectorized.
