[OPEN] Debug session: particle-motion-stuck

## Symptom
- User reports particles are visible, but motion still appears effectively unchanged or stuck.

## Expected
- Particle presets and motion changes should produce clearly visible directional travel and style-specific behavior in preview.

## Hypotheses
1. The preview is not using the updated particle preset/draft values, so the runtime still receives old low-motion settings.
2. The CPU simulation is generating particles and speeds correctly, but the GPU render path is collapsing travel visually.
3. The reactive trigger path is not activating in the live scene, so burst-driven presets never enter their stronger motion state.
4. Particle positions are updating, but the combination of size, opacity, and drift makes the motion read as static at current scale.
5. The active scene/template is bypassing or overriding the particle runtime, so the code changes are not reaching the visible preview.

## Evidence Log
- Instrumentation active in:
  - `src/renderer/src/features/video/preview/usePreviewSceneState.ts`
  - `src/renderer/src/features/video/preview/previewFrameRunner.ts`
  - `src/renderer/src/features/video/domains/particles/particleGpuRuntime.ts`
- Live evidence from `.dbg/trae-debug-log-particle-motion-stuck.ndjson` shows the visible scene is still assembling particles as:
  - after preset interaction: `particlesVariant: "classic"`, `particlesStyle: "spark"`, `particlesSpawnMode: "reactiveOnly"`, `particlesSpawnArea: "centerRing"`
  - Example lines: 5824-5829, 5904-5929
- This falsifies Hypothesis 1. The preview is receiving the stronger preset values.
- Live frame snapshots show the actual runtime failure:
  - `particleCount: 20`
  - `particleSpawnThreshold: 0.06`
  - `particleStateTriggerEnv: 0.0425`
  - `particleStateReactiveEnv: 0.0083`
  - `currentPlaybackTimeSec: 99.829`
  - Example lines: 5826, 5852, 5904, 5929
- Conclusion: `reactiveOnly` particles were falling into a dead zone where trigger stayed just under threshold, so burst-style presets never meaningfully filled or refreshed.
- New runtime evidence isolated a separate root cause for the "left click makes particles faster" symptom:
  - `.dbg/trae-debug-log-particle-motion-stuck.ndjson:47327-47329`
  - During a transient fallback scene rebuild, preview scene assembly used ratio-only `previewAspectRatio` defaults (`16:9`) while `particleGpuRuntime` received `scale: 60`.
  - The same frame produced runaway particle values: `firstParticleSpeed: 8874.412`, `firstParticleHalfWidth: 118.08`, `firstParticleSpawnX: -3282.9`, `firstParticleSpawnY: 1285.3`.
  - This confirms the particle burst/speed jump was downstream of a bad preview scale, not a true birth-rate issue.
- User follow-up after the scale fix changed the symptom:
  - Particles no longer blow up, but they still do not keep birthing continuously and their travel does not react strongly enough to music.
- Current live logs explain the remaining stall:
  - `.dbg/trae-debug-log-particle-motion-stuck.ndjson:63245,63300`
  - Example live state: `particlesSpawnMode: "reactiveOnly"`, `particleSpawnThreshold: 0.77`, `particleStateReactiveEnv: 0.0494`, `particleStateTriggerEnv: 0.0494`.
  - This leaves the burst gate effectively dead in real playback, and existing particles only receive weak live motion gain because travel is mostly determined at spawn time.

## Fix Attempt
- Updated `src/renderer/src/features/video/domains/particles/particleSimulation.ts` so `reactiveOnly` mode keeps a low sustain spawn layer when audio support remains near threshold, while threshold crossings still drive bigger bursts.
- Updated `energy_sparks` preset threshold in `src/renderer/src/features/video/domains/particles/particleSettings.ts` from `0.06` to `0.03` so the default preset is less likely to stall at low-to-mid drive.
- Added regression coverage in `src/renderer/src/features/video/domains/particles/particleSimulation.test.ts` for below-threshold sustain behavior.
- Updated `src/renderer/src/features/video/preview/usePreviewSceneState.ts` so ratio-only preview references such as `16:9` are normalized to a real preview-space baseline before computing viewport scale.
- Added regression coverage in `src/renderer/src/features/video/preview/usePreviewSceneState.test.tsx` to lock the normalized scale at `0.5` for a `960x540` preview using the `16:9` fallback reference.
- Updated `src/renderer/src/features/video/domains/particles/particleSimulation.ts` so `reactiveOnly` sustain no longer collapses under high thresholds when real audio support is still present, and so newly spawned particle speed now scales with live audio drive.
- Updated `src/renderer/src/features/video/webgpu/webgpuSpectrumRenderer.ts` so particles already on screen pick up stronger real-time travel, lift, swirl, and pulse response from current music drive instead of relying mostly on their initial spawn speed.
- Added regression coverage in `src/renderer/src/features/video/domains/particles/particleSimulation.test.ts` for:
  - continued spawning under high thresholds with ongoing audio support
  - stronger fresh-particle travel under stronger live audio drive
- Validation:
  - `npm run check`
  - `npx vitest run src/renderer/src/features/video/domains/particles/particleSimulation.test.ts src/renderer/src/features/video/domains/particles/particleSettings.test.ts src/renderer/src/features/video/domains/particles/particleGpuRuntime.test.ts`
  - `npx vitest run src/renderer/src/features/video/preview/usePreviewSceneState.test.tsx src/renderer/src/features/video/preview/previewFrameRunner.test.ts src/renderer/src/features/video/domains/particles/particleGpuRuntime.test.ts src/renderer/src/features/video/domains/particles/particleSimulation.test.ts`

## Status
- Waiting for post-fix user verification. Instrumentation remains in place.
