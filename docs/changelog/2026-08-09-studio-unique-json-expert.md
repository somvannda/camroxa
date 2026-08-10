# Studio unique JSON + Expert controls

**Date:** 2026-08-09  
**Branch:** `feature/studio-v1`

## Uniqueness

- Materials **scale** shape `barWidth`/`thickness` instead of overwriting (circle/ring/starburst/wave stay distinct under the same material).
- Lighting effects carry unique bolt profiles (`thickness` / `glow` / `length` / `flashRate` / `effectId`).
- Overlay **dust** ≠ film_grain (soft diffusion + lighter grain).
- Spectrum animation audio dials are per-behavior (expand ≠ twist, ripple ≠ wave).
- Camera `whip_pan` is continuous instead of sparse identity windows.

## Expert UI (all scene axes)

Palette intensity/saturation; Background sat/hue/smoothing; Spectrum blur/bar-width/thickness scales; Logo size/reactivity/offsets; Text opacity/scale/offset; Particles speed/reactivity; Lighting thickness/glow/flash/speed; Camera roll bias; Audio bass emphasis — all patched into composition JSON and GPU bridge.

## Docs

Wiring matrix updated in `docs/COMPOSITION_STUDIO_WIRING.md`.
