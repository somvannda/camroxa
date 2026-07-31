# Particle music notes + neon glow

**Date:** 2026-07-29  
**Status:** implemented (desktop preview + export path)

## Summary

Adds a **Music Notes** particle style (random eighth / beamed / quarter / treble-like icons) and a **Neon Glow** slider that blooms both music icons and ordinary dots (and other particle shapes). Matches the neon floating-note look from reference art without requiring external image assets.

## Product impact

- **Before:** Particle styles were Dot / Soft Glow / Ring / Spark / Bokeh only; no tunable neon bloom beyond the fixed Soft Glow shape.
- **After:** Particles → Style → **Music Notes**; raise **Neon Glow** (0–1) to get hot core + halo on notes **and** on Dot/Bokeh/etc.

## Technical impact

- Procedural atlas in `particle_music_icons.py`; GPU samples atlas when `pt_style == 5`.
- Per-particle random icon index + rotation stored on `ParticleSystem`.
- `particlesSettings.glow` / draft `particlesGlow` wired through draft/save/normalize.
- Preview and export share `_render_particle_styled_quads` with glow + atlas.

## Files touched

- `camxora_python/features/video/lib/particle_music_icons.py`
- `camxora_python/features/video/lib/particle_settings.py`
- `camxora_python/features/video/lib/video_template_draft.py`
- `camxora_python/features/video/lib/video_template_save.py`
- `camxora_python/features/video/lib/template_draft_domains.py`
- `camxora_python/features/video/widgets/particles_inspector.py`
- `camxora_python/visualizer/particles.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/tests/test_particle_music_glow.py`

## Migration / deploy

- Desktop-only. Restart the app to pick up Python module changes.
- Existing templates default `glow=0` (no visual change until raised).

## Tests

- `pytest camxora_python/tests/test_particle_music_glow.py`

## Follow-ups

- Optional discrete icon pickers (eighth-only, treble-only).
- Richer SVG/font-based treble glyph if we want closer score notation.
