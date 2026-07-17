# Debug Session: video-preview-reactivity
- **Status**: [OPEN]
- **Issue**: Video preview loads, but background/logo/particles do not react to music, spectrum/background/logo/particles settings appear to have no effect, and MP3 load still feels slow.
- **Debug Server**: http://127.0.0.1:7777/event
- **Log File**: .dbg/trae-debug-log-video-preview-reactivity.ndjson

## Reproduction Steps
1. Open the Video page with a selected MP3, background, and logo.
2. Wait for preview initialization to complete.
3. Play the track and observe whether spectrum, background, logo, and particles react.
4. Change inspector settings for Spectrum, Background, Logo, or Particles and observe whether the preview changes immediately.

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | Preview draft changes stop before the scene/runtime assembly layer, so inspector edits never reach the renderer inputs. | High | Med | Confirmed, then refined: switching fully to `templateDraft` was incorrect because `VideoTemplateDraft` does not carry raw `template.layers`; the correct live source is raw `template.layers` plus draft-owned style/runtime fields. |
| B | Reactive frame state is still computed, but only spectrum consumes it while background/logo/particle domains receive zeroed or stale drive values. | High | Med | Partially rejected: runtime logs showed non-spectrum motion values were being computed, but particle motion still exhibited visible spikes during UI stalls. |
| C | The preview scene/runtime is reusing stale memoized domain payloads after the recent transport/cache changes, so playback and setting edits do not invalidate dependent GPU inputs. | Med | Med | Partially confirmed through A: stale scene assembly inputs caused at least the spectrum path to miss live draft edits. |
| D | Playback timeline/audio runtime comes up late enough that non-spectrum domains never see a ready reactive signal path, while spectrum falls back to a separate direct signal path. | Med | Med | Not confirmed as root cause for the interaction spike. `resolvePreviewReactiveFrameState` already samples `runtime.audioElement?.currentTime` directly for reactive playback timing. |
| E | UI controls still mutate local draft state, but the domain adapters ignore the relevant draft fields after the A19/A20 seam refactors. | High | Med | Partially confirmed: with the persistent pre-analysis timeline active, `audioMotionSmoothing` was bypassed on the sampled-feature path, so live smoothing controls had little effect on spectrum/background/logo/particles. |
| F | Background/logo/particles are still driven by an older bass/kick/drop contract while spectrum uses the sampled shared reactive signal, so the preview domains no longer feel synchronized. | High | Med | Confirmed by user retest and code inspection: spectrum consumed the sampled reactive frame directly, while non-spectrum domains still derived motion from the older parity shaping path. |

## Log Evidence
- Instrumentation added in:
  - `src/renderer/src/features/video/preview/usePreviewSceneState.ts`
  - `src/renderer/src/features/video/preview/previewFrameRunner.ts`
- Observed from collected logs before the fix:
  - scene assembly snapshots showed draft values changing while the built spectrum scene still reflected stale inputs
  - reactive frame snapshots showed spectrum instances rendering while `scene.transport.currentPlaybackTimeSec` remained `0` in the debug payload
  - particle motion spikes aligned with UI interaction, consistent with oversized RAF delta values after main-thread stalls

## Verification Conclusion
- Landed fixes:
  1. `src/renderer/src/features/video/preview/usePreviewSceneState.ts`
     - spectrum layer assembly now keeps raw `template.layers` while overriding style from `templateDraft`
  2. `src/renderer/src/features/video/preview/previewFrameState.ts`
     - frame `deltaSec` is now clamped to `0.05` max so interaction stalls cannot inject a large simulation step into particles
  3. `src/renderer/src/features/video/preview/previewReactiveFrameState.ts`
     - cached pre-analysis timeline samples now receive live `audioMotionSmoothing` before frame construction, so smoothing controls affect spectrum/background/logo/particles again
     - zero smoothing now bypasses added timeline smoothing entirely for an immediate response mode
  4. `src/renderer/src/features/video/preview/previewReactiveFrameState.ts`
     - background and logo now derive support/trigger drive from the same shared preview audio signal used by spectrum instead of a separate bass/kick-only source path
  5. `src/renderer/src/features/video/domains/particles/particleSimulation.ts`
     - particles now derive sustain/trigger from the shared preview audio signal contract, with particle-specific smoothing and spawn controls layered on top
  6. `src/renderer/src/features/video/domains/particles/particleGpuContract.ts`
     - the shared preview audio signal is threaded into particle GPU preparation instead of reconstructing a separate reactive source
- Test verification completed:
  - `npx vitest run src/renderer/src/features/video/preview/usePreviewSceneState.test.tsx src/renderer/src/features/video/preview/previewFrameState.test.ts --reporter=verbose`
  - `npx vitest run src/renderer/src/features/video/preview/previewReactiveFrameState.test.ts src/renderer/src/features/video/preview/usePreviewSceneState.test.tsx src/renderer/src/features/video/preview/previewFrameState.test.ts --reporter=verbose`
  - `npx vitest run src/renderer/src/features/video/preview/previewReactiveFrameState.test.ts src/renderer/src/features/video/preview/previewReactiveFrameState.sequence.test.ts src/renderer/src/features/video/domains/particles/particleSimulation.test.ts src/renderer/src/features/video/domains/particles/particleGpuRuntime.test.ts src/renderer/src/features/video/preview/previewGpuDomainPreparation.test.ts src/renderer/src/features/video/preview/previewGpuRuntimeCoordinator.test.ts --reporter=verbose`
  - `npx vitest run src/renderer/src/features/video/preview/usePreviewTransportCoordinator.test.tsx src/renderer/src/features/video/VideoWorkspacePage.test.tsx src/renderer/src/features/video/useRendererVideoPreview.test.ts src/renderer/src/features/video/preview/previewLifecycleState.test.ts --reporter=verbose`
  - `npm run check`
- Remaining step:
  - user needs to verify the live app behavior after these fixes before cleanup or further instrumentation changes
