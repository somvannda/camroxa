# Studio scene axis wiring audit + live drivers

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Findings

Palette / background / spectrum were already compile→GPU wired (with known collapses). Remaining axes were mostly wired into the renderer dict, but several looked “fake” because values were frozen at `time_sec=0` on `set_template`.

## Fixes

- `apply_live_composition_motion` re-evaluates camera, background motion offsets, logo spin, overlay amount, particles/lighting drive, and audio mapping each preview frame.
- Particle type colors keep catalog tints unless a palette is selected.
- Camera rotate/tilt/roll contribute a small orbital offset in preview.
- Film grain / RGB split / chromatic get visible preview proxies; vignette/bloom map onto existing preview uniforms.

## Still partial (honest)

- Background motions still collapse to zoom/vibrate/both families.
- Full NLE timeline, true chromatic shader, and HDR bloom remain limited / flag-gated.
- Vocals/Melody/Snare stay v1 FFT heuristics.
