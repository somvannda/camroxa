# Spectrum Phase 4: particle motion trails

**Date:** 2026-07-29  
**Status:** implemented (desktop branch)  
**Branch:** `fix/spectrum-vivid-position-audio`

## Summary

Phase 4 adds optional **Motion Trails** to the Particles domain: a per-particle position history rendered as fading styled quads behind each head. Settings live only in `particlesSettings` (no Spectrum/Logo coupling).

## Product impact

- **Before:** Particles were single dots/sprites with no motion streak.
- **After:** Enable **Motion Trail** in the Particles inspector; tune **Trail Length**, **Trail Fade**, and Advanced **Trail Width**. Trails draw under particle heads in preview and MP4 export.

## Technical impact

- Template fields: `trailEnabled`, `trailLength` (2–24), `trailFade`, `trailWidth`.
- Draft keys: `particlesTrailEnabled` / `Length` / `Fade` / `Width`.
- `ParticleSystem` keeps `(N, L, 2)` history; `build_trail_draw_arrays()` emits NDC quads.
- Preview + main GPU export draw trails before heads via existing styled-quad path.

## Files touched

- `camxora_python/visualizer/particles.py`
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/template_runtime.py`
- `camxora_python/features/video/lib/video_template_draft.py`
- `camxora_python/features/video/lib/video_template_save.py`
- `camxora_python/features/video/lib/template_draft_domains.py`
- `camxora_python/features/video/widgets/particles_inspector.py`
- `camxora_python/tests/test_particle_phase4_trails.py`
- `docs/SPECTRUM_ENHANCEMENT_PHASES.md`
- `CHANGELOG.md`
- `docs/changelog/2026-07-29-spectrum-phase4-particle-trails.md`

## Migration / deploy

- Desktop-only. Restart Camxora.
- Particles tab → enable **Motion Trail**.

## Tests

- `pytest camxora_python/tests/test_particle_phase4_trails.py -q`

## Follow-ups

- Optional: include trail fields in motion presets.
- Optional: legacy GL_POINTS export paths.
- Optional: remove Logo “Attach Spectrum” if ring always tracks logo size.
