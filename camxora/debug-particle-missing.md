# Debug Session: particle-missing

Status: [OPEN]

## Symptom
- Particles no longer appear after the recent "one-way forward" spark motion change.

## Scope
- WebGPU preview particle rendering
- Recent spark-only forward travel changes

## Hypotheses
1. Spark direction is now valid in simulation, but the WGSL vertex path produces degenerate geometry so particles render off-screen or at zero visible area.
2. The new `safeDir = baseDir` branch for spark style causes a bad orientation/extent combination that collapses the quad or points it out of frame.
3. Spark particles still spawn, but their center/alpha/fade math now pushes them fully transparent or too far outside the viewport immediately.
4. The bug is not in spawn/simulation at all; the selected preset/style is hitting a shader-only regression isolated to style index `spark`.

## Evidence Plan
- Add instrumentation in particle GPU preparation and WebGPU shader uniform packing path.
- Reproduce in preview and capture pre-fix logs.
- Confirm whether particles are spawning, what style index they carry, and whether render-time travel/alpha inputs are sane.
