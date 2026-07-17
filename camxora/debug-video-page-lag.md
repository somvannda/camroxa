# [OPEN] Debug Session: video-page-lag

## Symptoms
- Entering the Video page feels stuck or very slow.
- Preview can show GPU/live compositor badges while the workspace still reports `Preview Initializing`.
- Spectrum, background, logo, and particles do not currently feel as strong or as correct as expected.

## Scope
- Project: `camxora`
- Area: Video workspace preview boot path, audio/bootstrap path, spectrum spec ownership, preview runtime performance

## Hypotheses
1. The Video page lag is dominated by synchronous or heavy bootstrap work in preview asset/audio setup, especially base64 file loading and MP3 decode/feature-bus initialization.
2. The preview surface lifecycle is getting stuck or repeatedly remounted, causing `webgpuStatus` to remain `initializing` or flip during runtime while the compositor still renders.
3. The live preview still spends too much CPU per frame in pre-GPU work: audio analysis, DOM background/logo/text composition, and spectrum shaping before submission.
4. Spectrum quality feels worse because the source of truth is split between runtime analysis/shaping code and preset recipe code, not because A19/A20 failed as a whole.
5. The current preset/spec architecture is code-defined and partially duplicated, so the visualizer can be technically faster in some paths while still looking less correct due to recipe/profile mismatches.

## Evidence Plan
- Instrument preview surface initialization start/resolve/error and lifecycle transitions.
- Instrument audio feature-bus bootstrap and asset loading timings.
- Instrument per-report runtime timings already emitted by preview telemetry and correlate with the page-enter symptom.
- Inspect current spectrum recipe ownership and compare preset/template source of truth against runtime style shaping.

## Current Status
- Investigation in progress.

## Evidence Collected
- `usePreviewSurfaceLifecycle` initializes WebGPU in roughly `500-620 ms`, but the effect enters a `start -> cleanup -> start` pattern before success. That looks like duplicate mount/init churn, not a permanently failing GPU init.
- Preview frame telemetry from the older `preview-slow-performance` session does not show a renderer that is fundamentally too slow in steady state. The frequent bad samples are hitch-style spikes, not a constant GPU bottleneck.
- The audio bootstrap path was measurably duplicating expensive work:
  - MP3 source base64 read: roughly `200-265 ms` per call
  - MP3 array-buffer base64 read: roughly `180-375 ms` per call
  - reactive timeline build: roughly `10.1 s` for one run and `20.4 s` for the duplicate overlapping run
- Background/logo bootstrap also performs synchronous-looking file reads and image decode on page entry:
  - background source base64 read: about `224 ms`
  - logo source base64 read: about `194 ms`
  - image-ready/decode path: about `650-765 ms`
- Spectrum configuration is not owned by one declarative JSON spec today. The live preset recipes are code-defined in `src/renderer/src/features/video/domains/spectrum/spectrumStyleRegistry.ts`, normalized through `spectrumLayerModel.ts`, while older settings/preset seed logic still exists via `src/renderer/src/features/settings/pythonVideoSettings.ts`.

## First Mitigation Applied
- Stopped rebuilding the full preview audio feature bus when only `audioMotionSmoothing` or `previewVolume` changes.
- Added shared in-memory caches for:
  - resolved preview audio sources
  - preview audio array buffers
  - preview reactive timelines
- Added a direct `applyPreviewAudioMotionSmoothing(...)` path so smoothing updates now mutate the live analyser instead of tearing down and rebuilding the runtime.

## Second Mitigation Applied
- Reworked local-image bootstrap in `src/renderer/src/features/video/useRendererVideoPreview.ts`.
  - Local preview assets now resolve through a cached `data:` source path instead of repeating `readFileAsBase64(...)` work every time the preview mounts.
  - This preserves the reliable renderer-side image loading behavior for background/logo assets without reintroducing repeated bootstrap reads.
- Hardened the preview lifecycle contract in `src/renderer/src/features/video/preview/previewLifecycleState.ts`.
  - If the built scene already reports `viewport.webgpuReady === true`, the lifecycle now resolves to `running` or `fallback-active` instead of continuing to surface a transient `initializing` status.
  - This prevents the operator-facing diagnostics from lagging behind a live compositor-ready scene during transient render boundaries.

## Third Mitigation Applied
- Added a persistent Electron-side preview audio analysis cache keyed by source path plus file metadata.
  - Main process now stores per-track timeline payloads under the app `userData` cache root via:
    - `video:get-audio-analysis-cache`
    - `video:set-audio-analysis-cache`
- Added renderer-side timeline serialization and restore support in:
  - `src/renderer/src/features/video/preview/audioReactiveTimeline.ts`
  - `src/renderer/src/features/video/preview/previewAudioAnalysisCache.ts`
- Updated `src/renderer/src/features/video/preview/audioFeatureBus.ts` so preview bootstrap now:
  1. checks the in-memory cache
  2. checks the persistent Electron cache
  3. only then decodes the MP3 and rebuilds the reactive timeline
- Result:
  - first analysis still costs real time
  - subsequent page opens and replay boots for the same unchanged MP3 can skip the decode/analyze pass entirely

## Verification
- `npx vitest run src/renderer/src/features/video/preview/usePreviewTransportCoordinator.test.tsx --reporter=verbose`
- `npx vitest run src/renderer/src/features/video/useRendererVideoPreview.test.ts src/renderer/src/features/video/preview/previewLifecycleState.test.ts src/renderer/src/features/video/preview/usePreviewTransportCoordinator.test.tsx --reporter=verbose`
- `npx vitest run src/renderer/src/features/video/preview/audioReactiveTimeline.test.ts src/renderer/src/features/video/preview/previewAudioAnalysisCache.test.ts src/renderer/src/features/video/preview/usePreviewTransportCoordinator.test.tsx --reporter=verbose`
- `npm run check`

## Next Most Likely Work
1. Reproduce with the current patch and compare the debug logs to confirm the duplicate `10-20 s` timeline builds are gone.
2. Reproduce with the current patch and confirm the page-enter cost is now dominated by only the first uncached analysis for a newly selected MP3.
3. Move the heavy first-pass analysis off the renderer thread if the uncached first-open cost still feels too high.
4. Unify spectrum preset/spec ownership before starting `M7.A21`, because current recipe duplication makes “looks wrong” harder to fix cleanly.
