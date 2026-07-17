[OPEN] Debug Session: preview-slow-performance

## Summary
- Symptom: Video preview feels very very slow (low FPS / laggy interaction).
- Scope: Renderer live preview (WebGPU compositor + audio analysis + particles + UI).

## Environment
- OS: Windows
- App: CAMXORA Electron renderer video workspace

## Hypotheses (Falsifiable)
- A: Main-thread CPU bottleneck from per-frame allocations (arrays/objects) in `RendererVideoPreview.tsx` (spectrum values, instances, particles), causing GC and frame spikes.
- B: WebGPU path recreates or re-allocates GPU resources too often (buffers/textures/pipelines) or does excessive buffer writes, stalling the GPU/CPU.
- C: Preview loop causes unnecessary React re-renders or layout thrashing (ResizeObserver / DOM measurement / image decode) during playback.
- D: Particle simulation update cost scales poorly (maxCount/spawnRate) and dominates frame time.
- E: Excessive post-FX/bloom or large render targets cause GPU fill-rate issues (especially at high preview resolution / DPR).

## Instrumentation Plan
- Collect per-frame timing breakdown (analysis, resample, instance build, particle update, renderer render).
- Collect counts (barCount, layerCount, instanceCount, particleCount, canvas size, DPR).
- Collect WebGPU resource churn metrics (buffer/texture creation counts per second).

## Runs
- runId: pre-fix
- runId: post-fix

## Evidence Log Links
- NDJSON: `.dbg/trae-debug-log-preview-slow-performance.ndjson`

## Status
- Current: Awaiting instrumentation + reproduction steps capture.

