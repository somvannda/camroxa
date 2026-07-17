[OPEN] Debug Session: export-speed-regression

## Symptom
- Manual WebGPU export is slower after switching from `capturePage()` to GPU readback.

## Expected
- Manual export should be faster than the previous screenshot-based path.

## Current Scope
- Electron main-process manual export orchestration
- Hidden export host IPC
- Renderer WebGPU readback path
- ffmpeg stdin streaming

## Falsifiable Hypotheses
1. GPU readback is blocking too early or too often because `mapAsync()` is being awaited before the submitted frame is actually ready.
2. The hidden export host is waiting extra frames before capture, so the new path adds more seek/render latency than it saves.
3. IPC transfer of large `Uint8Array` frame payloads from renderer to main is slower than `capturePage()` on this machine.
4. The readback path is copying padded rows or reallocating buffers in a way that creates per-frame memory churn.
5. ffmpeg stdin backpressure is stalling the capture loop, and the slower path is not GPU capture itself but encoder write throughput.

## Evidence Plan
- Add timing instrumentation around:
  - host seek/sync wait
  - capture request dispatch
  - renderer readback time
  - IPC return time
  - ffmpeg stdin write time
- Compare per-frame timings against export progress behavior.

## Status
- Session initialized.
- Instrumentation added around seek/sync, GPU readback, host capture, IPC, and ffmpeg writes.
- Pre-fix evidence collected:
  - Seek synchronization is effectively `0ms`.
  - GPU readback settles in roughly `6-16ms` after warmup.
  - ffmpeg stdin writes are roughly `6-25ms`.
  - Hidden host capture response is roughly `1.9-2.0s` per frame.
- Root-cause candidate:
  - The hidden export host waited on two `requestAnimationFrame()` ticks before returning a frame.
  - In a hidden window that RAF path is throttled, so it dominates total frame time.
- Minimal fix applied:
  - Removed the double-RAF wait from `VideoExportHostPage.tsx`.
- Post-fix evidence collected:
  - Seek sync remains `0-1ms`.
  - GPU readback is usually `6-12ms` after warmup.
  - Renderer -> main IPC handoff works and returns in under `~50ms` after the host responds.
  - Hidden host capture response is still `~930-1000ms` per frame.
- Confirmed root cause:
  - The hidden export renderer is still background/occlusion throttled while the export host window stays hidden.
  - This is now the dominant bottleneck.
- Minimal fix applied:
  - Added Chromium switches in Electron main to disable background timer throttling, renderer backgrounding, and occluded-window throttling.
- Additional evidence collected:
  - The Chromium throttle switches did not materially improve host frame cadence.
  - The hidden host still returns frames at roughly `~0.93-1.00s` per frame.
  - The preview runtime is driven by `requestAnimationFrame` via `startPreviewAnimationLoop()` in `previewAnimationLoop.ts` and `usePreviewRuntime.ts`.
- Confirmed architectural limit:
  - Manual export is currently piggybacking on the interactive preview runtime.
  - Because that runtime depends on `requestAnimationFrame`, a hidden export page cannot achieve the requested speed target.
- Evidence-based next fix:
  - Build a dedicated export render loop that does not use `requestAnimationFrame`.
  - For each export frame: seek -> settle playback state -> render once on demand -> GPU readback -> stream to ffmpeg.
