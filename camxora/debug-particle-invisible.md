# Debug Session: particle-invisible [OPEN]

## Symptom
- User reports particles are effectively not visible in preview even after size and preset changes.

## Expected
- Particle presets should produce clearly visible particles in the live WebGPU preview.

## Hypotheses
1. The particle simulation is producing particles, but the renderer is packing or scaling their geometry incorrectly before GPU upload.
2. The particles are drawn, but fragment alpha/emission is too weak against the current blend/background combination, so they disappear visually.
3. The particles are spawned outside the visible region or move off-screen immediately due to coordinate or direction math.
4. The particle instances are generated correctly, but the render pass ordering or pipeline state causes them to be occluded by later draws.
5. The preview diagnostics are showing stale or mismatched particle values compared with the actual GPU instance buffer contents.

## Evidence Collected
- Existing `.dbg/trae-debug-log-particle-motion-stuck.ndjson` shows particle settings propagating into preview scene assembly.
- Existing logs show non-zero `particleCount`, non-zero `particleSize`, and active particle modes during playback.

## Next Step
- Inspect simulation-to-render packing and add targeted instrumentation only if the current logs do not explain where visibility is lost.
