# GPU export encode throughput (NV12 + NVENC fast path)



**Date:** 2026-07-20  

**Status:** implemented (local benchmarked)



## Summary



Phase-2 profiling showed `encodeWriteAvgMs` ≈ 149 ms while `stdinBlockP95Ms` was only ≈ 13 ms and submit barely blocked — the render thread was spending nearly all encode time in Python float NV12 packing, not NVENC. This change replaces NV12 conversion with OpenCV (limited/TV range), moves packing onto the encode writer thread, deepens the pipe queue, and adds low-latency NVENC flags for `fast` / `very_fast` speed modes.



**Phase 2b (same day):** Fast/very_fast pipe switched from interleaved NV12 to planar **yuv420p** (OpenCV I420, NVENC-native), with reusable OpenCV `dst` buffers and a rotating CPU readback pool. Pack under load dropped ~14 ms → ~4 ms; readback ~5.5 → ~2 ms. Sustained 60 s encode loop clears **≥5×** when excluding cold audio analysis; wall-clock with cold init remains analysis-bound.



## Product impact



**Before:** Subprocess Standard/fast GPU export on RTX 3060 measured ~0.21× realtime on the 3 s fixture (~158 ms/frame, encode ~149 ms). In-process UI was already ~4× on longer tracks; subprocess lagged badly.



**After (Phase 2a):** Same 3 s fixture ≈ **0.74–0.81×** realtime with `encodeWriteAvgMs` ≈ **5–6 ms** (submit only; pack overlapped on writer). 60 s tone amortized ≈ **1.60×** including cold audio analysis (~11 s init). Fast exports use TV-range YUV + `-tune ll` / `-zerolatency` / `-bf 0`. Balanced/Master remains quality-conservative (no ll flags, RGBA pipe unchanged).



**After (Phase 2b):** 3 s fixture ≈ **0.75–0.95×** (still init-bound). 60 s tone ≈ **2.53×** wall including cold analysis (~12 s init); **~5.3×** sustained excluding init. UI in-process on long tracks should move from ~4.3× toward **≥5×** (retest required). Footer/status shows `YUV420P` pipe for fast exports.



## Technical impact



- **Root cause:** `rgba_bytes_to_nv12` float32 path (~140 ms/1080p) ran on the render thread inside the profiled encode phase; stdin was not the bottleneck.

- **Phase 2a NV12:** OpenCV `COLOR_RGBA2YUV_I420` → interleaved NV12; ffmpeg `-color_range tv`.

- **Phase 2b yuv420p:** Fast default pipe is planar I420 (`yuv420p`) — skips UV interleave; `PipeFramePacker` reuses OpenCV `dst`; `CAMXORA_EXPORT_PIPE=nv12|rgba|yuv420p` override kept. `opencv-python` has no CUDA build here — CUDA path skipped.

- **Readback:** `AsyncFramebufferReader` optional CPU bytearray pool (`queue_size + 2`) via `Buffer.read_into`; avoid redundant `bytes()` wrap.

- **Pipeline:** `PipelinedEncodeWriter` optional `pack_fn`; YUV exports enqueue raw RGBA and convert on the writer thread. Default queue depth 6 (`CAMXORA_ENCODE_QUEUE`, clamp 2–8).

- **NVENC:** `build_nvenc_export_args()` — fast/very_fast: preset p2/p1, `-tune ll`, `-zerolatency 1`, `-bf 0`, `-rc constqp`; balanced: p5/cq19, no ll.

- **Metrics:** `CAMXORA_ENCODE_METRICS` includes `packAvgMs` / `packP95Ms` / `queueSize` / `packOnWriter`.



## Files touched



- `camxora_python/visualizer/readback.py` — yuv420p default, `PipeFramePacker`, CPU readback pool

- `camxora_python/visualizer/encode_pipeline.py` — pack-on-writer payload typing

- `camxora_python/visualizer/gpu_render.py` — yuv420p pipe wiring, packer + pool

- `camxora_python/scripts/benchmark_gpu_export.py` — trace `CAMXORA_EXPORT_PIPE`

- `camxora_python/tests/test_export_readback.py`, `test_encode_pipeline.py`, `test_export_nvenc_args.py`, `test_benchmark_gpu_export.py`

- `CHANGELOG.md` (desktop Unreleased)



## Migration / deploy



- No DB/migrations. Desktop-only. No installer this pass.

- Optional env: `CAMXORA_ENCODE_QUEUE` (2–8), `CAMXORA_EXPORT_PIPE` (`rgba`|`nv12`|`yuv420p`), existing `CAMXORA_ENCODE_METRICS` / `CAMXORA_EXPORT_PROFILE`.

- Fast exports tagged TV range (OpenCV). Spot-check color vs prior NV12 builds; Master/balanced still RGBA/`pc`.



## Tests



- `pytest tests/test_export_readback.py tests/test_encode_pipeline.py tests/test_export_nvenc_args.py tests/test_benchmark_gpu_export.py` — passed (**32**).

- Smoke: `CAMXORA_ENCODE_METRICS=1 CAMXORA_EXPORT_PROFILE=1 CAMXORA_GPU_SPECTRUM=1 python scripts/benchmark_gpu_export.py`

  - **Before (20260720_085102):** realtime 0.21×, encodeWriteAvgMs 149.0, stdin p95 13.6 ms, submit p95 0.05 ms

  - **After 2a (20260720_093114):** realtime 0.74×, encodeWriteAvgMs 5.4, stdin p95 2.2 ms, submit p95 6.5 ms, pack avg 14.0 ms, readback 5.5 ms

  - **After 2b (20260720_110441):** realtime 0.75×, encodeWriteAvgMs 0.48, stdin p95 5.9 ms, submit p95 1.3 ms, pack avg **3.62 ms**, readback **1.84 ms**

- 60 s tone (`generated_tone_60s.wav`):

  - **2a:** realtime 1.60× (init 10.8 s)

  - **2b (20260720_110542):** realtime **2.53×** (init 12.3 s cold analysis); sustained ≈ **5.3×** excluding init (wall 23.7 − 12.3 = 11.4 s for 60 s)



## Follow-ups



- Gap to 5× **wall** on subprocess: cold audio analysis / GLFW init (~10–12 s) — warm daemon / in-process already closer; UI retest on ~3 min tracks is the gate.

- Pack ~4 ms under load (idle OpenCV dst reuse ~0.3 ms) — further wins need less CPU contention or GL/CUDA YUV (stock `opencv-python` has no CUDA).

- `stdinBlockP95` rose slightly (~6 ms) — watch if NVENC ingest becomes the limiter once pack stays low.

- Re-validate Master visual QA (Master tier defaults to balanced speed → now yuv420p/TV). Override with `CAMXORA_EXPORT_PIPE=rgba` if needed.

- Cancel: `QThread` destroy-while-running addressed in Phase 2d (`wait` + `deleteLater` / lingering detach).

## Incident — Phase 2b NVENC CQ / LL file-size + UI slowdown (same day)

**User report:** After Phase 2b, desktop exports felt slower and MP4s were larger.

**Log evidence:** Midnight Circuit (~173 s) wall **36 s** (`10:53`, ~4.8×) → **48 s** (`11:17`, ~3.6×). Template also changed mid-session (Bass Drive), which can add GL cost independently.

**Root cause (encode side):** Phase 2a/2b NVENC fast path enabled `-tune ll -zerolatency -bf 0` (larger files, less efficient bitstream) and collapsed **balanced** onto **CQ 19 / p5** (old quality tier) instead of CQ 23 / p3.

**Fix:** Restored baseline CQ/presets (`fast`/`balanced` → p3/cq23; `very_fast` → p1/cq27; `quality` → p5/cq19). LL/zerolatency/`-bf 0` are **opt-in** via `CAMXORA_NVENC_LL=1` only. Kept yuv420p pack path for fast (throughput win without bitrate bloat).

## Phase 2d follow-up — QThread quit race (same day)

**User report:** After Bass Drive retest, console showed `QThread: Destroyed while thread 'VideoManualExportWorker' is still running` when closing the app mid-export.

**Root cause:** Export workers were created with `parent=VideoView`. Closing the main window destroys the view (and child QThreads) before the OS thread finishes. A 2s Stop wait was not enough for app quit.

**Fix:** Create manual/pipeline/merge workers with `parent=None`; keep strong refs in `video_pipeline_activity`; `aboutToQuit` calls `shutdown_video_pipeline_threads(wait_ms=8000)` before daemon/subprocess teardown. Stop Export uses the same release helper with an 8s join.

## Phase 2c — Balanced yuv420p + pipe back-pressure (same day)

**Gap:** UI Beattok / Midnight Circuit (~173 s) wall ~**44 s** (~3.9×) vs earlier same-day best ~**36 s** (~4.8×). ~8 s over ~4150 frames ≈ **~2 ms/frame**.

**Findings:**
- `balanced` (user Speed combo; also Master-tier default) still used **RGBA pipe** + ffmpeg `scale=in_range=pc` software convert, while `fast`/`very_fast` already used pack-on-writer **yuv420p** (~3 MiB/frame vs ~8 MiB + swscale).
- Standard tier honors `videoExportSpeedMode`; selecting Balanced therefore skipped the Phase 2b throughput path.
- Secondary: default ffmpeg demux queue + 8 KiB Python stdin buffer can add brief stdin back-pressure under load.

**Changes:**
1. `resolve_pipe_pix_fmt`: `balanced` / `draft` → `yuv420p` (same OpenCV I420 + pack-on-writer as fast). Explicit `quality` stays **RGBA/pc**.
2. ffmpeg: `-thread_queue_size 64` on rawvideo + audio inputs; stdin `bufsize` ≈ one frame.
3. Frame loop: reuse last FFT from the 60 Hz smooth advance (drop duplicate `fft_for_frame` per export frame).

**Expected UI impact:** Balanced exports should match Fast pipe throughput (footer shows `YUV420P`). Retest Beattok / Midnight Circuit aiming ≤~35–36 s (≥5×) when Speed=Balanced or Fast. Spot-check color (TV range) vs prior Balanced RGBA/pc.

**Not changed:** NVENC CQ/presets; LL flags remain `CAMXORA_NVENC_LL=1` only.

### Phase 2c tests / smoke

- `pytest tests/test_export_readback.py tests/test_encode_pipeline.py tests/test_export_nvenc_args.py tests/test_benchmark_gpu_export.py` — **34** passed.

- 3 s A/B (`CAMXORA_ENCODE_METRICS=1 CAMXORA_EXPORT_PROFILE=1 CAMXORA_GPU_SPECTRUM=1`):

  - **yuv420p (2c default):** wall 3.17 s, realtime **0.95×**, encodeWriteAvgMs ≈ 1.0, stdin p95 6.3 ms, pack avg 5.2 ms

  - **RGBA override (old balanced):** wall 3.77 s, realtime **0.80×**, encodeWriteAvgMs ≈ 4.8, stdin p95 **16.0 ms**, no pack

- 60 s tone warm-cache (`generated_tone_60s.wav`, 20260720_113943): wall **13.45 s**, realtime **4.46×** (init 2.08 s); sustained ≈ **5.3×** excluding init.

## Phase 2d — Heavy-template export cost + QThread cancel teardown (same day)

**Gap:** Beattok / Midnight Circuit (~173 s) already ≥5× (Balanced ~30 s / Fast ~28 s). Bass Drive on the same track was ~49 s — complex templates still hurt. Logs often showed `QThread: Destroyed while thread '' is still running` on Stop Export.

**Findings (Bass Drive vs Beattok):**
- Both use `liquid` waveform (CPU path) + dual spectrum glow on the base layer.
- Bass Drive particles: **maxCount 1200 / spawnRate 400** vs Beattok **475 / 100** — primary cost delta.
- Glow: two additive bloom passes under the main waveform pass × layers every frame.

**Changes:**
1. **Speed-gated glow passes** (`export_glow_pass_limit`): Draft/Fast/very_fast → 0 glow; Balanced → 1 soft glow; Master/quality → full dual glow. Preview unchanged.
2. **Speed-gated particle caps** (`export_particle_caps`): Balanced 600/200, Fast 400/120, Draft/very_fast 250/80; Master untouched. Beattok stays under caps (no change).
3. **QThread cancel teardown:** Stop Export `wait(2s)` after cancel; finished handlers `wait` + `deleteLater`; if still running after timeout, detach from parent and keep a strong ref until `finished` (avoids destroy-while-running).

**Expected UI impact:**
- Beattok Balanced/Fast: should stay ~28–32 s (caps/glow skip do not bite light templates on Balanced).
- Bass Drive Balanced: expect meaningful drop from ~49 s toward Beattok range (fewer glow passes + half particle budget). Fast/Draft more aggressive (no glow).
- Master: visual parity preserved (full glow + uncapped particles).
- Stop Export: no `QThread: Destroyed while thread is still running`; UI blocks at most ~2 s on stop join.

**Not changed:** NVENC CQ/presets; LL flags remain opt-in; yuv420p pipe; Beattok encode path.

### Phase 2d tests

- `pytest tests/test_export_speed_quality.py tests/test_export_nvenc_args.py tests/test_export_readback.py tests/test_encode_pipeline.py tests/test_benchmark_gpu_export.py` — **37** passed.

## Phase 2e — UX polish + more performance (same day)

**Tracks:** 2 (UX) + 3 (performance). No installer.

### Track 2a — QThread hard-quit

**Gap:** User still saw `QThread: Destroyed while thread '' is still running` on app close mid-export after Phase 2d.

**Changes:**
1. `RootWindow.closeEvent` cancels+joins tracked export threads (`wait_ms=12_000`) before accepting close.
2. `aboutToQuit` wait raised to 12 s (order unchanged: pipeline threads → visualizer daemon → terminate_job).
3. Named all export-path QThreads (`VideoManualExportWorker`, `VideoPipelineExportWorker`, `VideoPipelineMergeWorker`, `VideoBillingWorker`, `PatchSettingsWorker`, `VideoWorkspaceWorker`, `VideoPatchTemplateWorker`, `VideoTemplateSyncWorker`).
4. Automation pipeline/merge workers use `parent=None` (same as manual UI). Settings patch workers also `parent=None` with a view strong-ref.

### Track 2b — Async Manual Export billing

**Gap:** After folder dialog, sync `consume_video_operation` blocked the UI 1–2 s.

**Changes:** Billing runs on `VideoBillingWorker` (tracked QThread). GPU export starts only on billing success via `_start_next_batch_export`. Failure clears pending batch state + notifies. Stop during billing keeps `_stop_export_pending` and refunds on success callback (never starts GPU). Merge billing still sync (unchanged).

### Track 2c — Default Speed → Fast

**Changes:** First-run / unset `videoExportSpeedMode` seeded to `fast` in `apply_workspace_path_defaults` (does not overwrite Balanced). Export Speed combo lists Fast first. Standard tier / codec defaults already Fast; Master still defaults Speed to Balanced only when unset *and* Master is selected without a stored Speed — seeded Fast applies when workspace defaults run.

### Track 3 — Performance

1. **Balanced glow skip:** `export_glow_pass_limit("balanced")` → `0` (was 1). Master/quality stay at dual glow; particle caps unchanged. Cuts CPU waveform rebuild cost on Bass Drive-class templates at Balanced/Fast.
2. **REQ-2.3 slice 2 subset:** GPU bar path enabled for `thin-lines`, `signal-needles`, `grid-steps`, `pixel-bars` (`SPECIAL_BAR_STYLES_GPU_READY`) with half-width scale / FFT quantization matching CPU. Remaining slice-2 styles (beads, blades, capsules, neon-pulse, …) stay CPU.

### Files touched

- `camxora_python/app/root_window.py`, `app/bootstrap.py`
- `camxora_python/features/video/views/video_view.py`
- `camxora_python/features/video/workers/video_billing_worker.py` (new)
- `camxora_python/features/video/workers/manual_export_worker.py`, `pipeline_export_worker.py`, `pipeline_merge_worker.py`, `video_template_sync_worker.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/video/widgets/export_queue_panel.py`
- `camxora_python/shared/lib/workspace_defaults.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/visualizer/gpu_render.py`, `spectrum_gpu.py`
- `camxora_python/tests/test_export_speed_quality.py`, `test_spectrum_gpu.py`, `test_workspace_defaults.py`
- `CHANGELOG.md`

### Migration / deploy

- Desktop-only. No DB. No installer this pass.
- Retest quit mid-export, Manual Export click feel, Speed default on fresh settings, Bass Drive Balanced timing.

## Phase 2f — Empty QThread quit + low-GPU tier (same day)

**User report:** Closing mid Manual Export still logged `QThread: Destroyed while thread '' is still running` (empty name — not `VideoManualExportWorker`).

**Root cause:** Shell background workers (`ProgressLocalSyncWorker`, `ImageOutputSyncWorker`, `MusicDownloadSyncWorker`, `VideoPipelineOrchestrationWorker`, `PushNotificationWorker`) had **no `objectName`**, were **parented under AppShell / push runtime**, and were **not stopped in `closeEvent`**. Destroying the window killed those QThreads while HTTP/WS work was still running. Export workers were already named + joined.

**Fix:**
1. `app_thread_registry` — track + cancel/join shell QThreads (shared ~10s deadline).
2. `RootWindow.closeEvent` / `aboutToQuit`: stop push + shell coordinators → `shutdown_app_threads` → `shutdown_video_pipeline_threads` (shared ~12s deadline).
3. Sync/push/orchestration workers: `setObjectName`, `parent=None`, strong registry refs until finished.
4. `AppShellWidget.shutdown_background_workers()` stops music/image/progress/pipeline pollers.

**GTX 1050 Ti–class performance (`export_gpu_tier.py`):**
- Detect `low|mid|high` via `nvidia-smi` name/VRAM or `CAMXORA_GPU_TIER` override.
- `low` (<6GB or 1050-class name): tighter Draft/Fast/Balanced particle caps; `quality` speed prefers `yuv420p`.
- Master / high-end caps unchanged. NVENC LL/`-bf 0` remain opt-in only.

### Phase 2f files

- `camxora_python/shared/services/app_thread_registry.py` (new)
- `camxora_python/shared/services/video_pipeline_activity.py` (shared quit deadline)
- `camxora_python/app/root_window.py`, `app/bootstrap.py`, `app/application.py`
- sync/push coordinators + named workers (`data_workers`, bootstrap/shell/push/update)
- `camxora_python/visualizer/export_gpu_tier.py` (new), `gpu_render.py`, `readback.py`
- `camxora_python/tests/test_export_gpu_tier.py`, `test_app_thread_registry.py`, related test updates
- `CHANGELOG.md`

### Phase 2f tests

- `pytest tests/test_export_gpu_tier.py tests/test_app_thread_registry.py tests/test_export_speed_quality.py tests/test_export_readback.py tests/test_pipeline_automation_stale_recovery.py` — **30** passed.

### Retest

1. **Quit mid-export:** start Manual Export → close window within a few seconds → terminal must not show empty-name `QThread: Destroyed…` (nor named export workers).
2. **Simulate low GPU:** `$env:CAMXORA_GPU_TIER='low'` then export Standard+Fast on a heavy template; particles should be more aggressively capped. Unset or set `high` on RTX 3060 for normal caps.

### Phase 2f follow-up (same day) — zombie `VideoManualExportWorker` on quit

**User retest (12:37, `CAMXORA_GPU_TIER=low`):** empty-name `QThread: Destroyed…` **gone**. Mid-export close then logged:

`RuntimeError: libshiboken: Internal C++ object (VideoManualExportWorker) already deleted`

in `any_video_pipeline_threads_running()` while queued success/finished handlers still refreshed the export panel.

**Fix:** harden `any_video_pipeline_threads_running` / `any_app_threads_running` against deleted C++ wrappers; `untrack_video_pipeline_thread` before `deleteLater` in `_release_export_qthread`.

**Timing note (Bass Drive ~173s audio, low tier):** track1 ~26s, track2 ~35s — similar to prior Fast runs; particle caps matter more on particle-heavy templates than Bass Drive.

### Phase 2f follow-up 2 — PushNotificationWorker quit

**User retest (12:45):** export zombie traceback **gone**. Quit mid track4 still logged:

`QThread: Destroyed while thread 'PushNotificationWorker' is still running`

**Root cause:** worker blocked in `websocket.recv()` (65s timeout); `request_stop` only set a flag, so close could tear down before the OS thread exited.

**Fix:** close the active websocket from `request_stop`, poll recv at 1s, keep Python ref until join succeeds.

### Phase 2f follow-up 3 — VideoManualExportWorker quit

**User retest (12:54):** Push warning **gone**. Quit mid track3 then logged:

`QThread: Destroyed while thread 'VideoManualExportWorker' is still running`

**Root cause:** close accepted the window while export was still joining / finished handlers could chain the next batch track during teardown.

**Fix:** `set_app_quitting` + `prepare_app_quit` (clear queue, cancel) before join; drain events; ignore close + retry until joined; terminate as last resort; worker-level cancel flag.
