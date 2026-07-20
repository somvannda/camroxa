# GPU Export Performance Requirements

> **Document ID:** CAMXORA-GPU-EXPORT-PERF  
> **Version:** 1.0.0  
> **Status:** Approved — implement task-by-task  
> **Scope:** Desktop `camxora_python` only (no VPS/server)  
> **Goal:** CapCut-class export speed while staying **Python-first**  
> **Related:** [`VIDEO_EXPORT_ROADMAP.md`](VIDEO_EXPORT_ROADMAP.md), [`camxora_python/.docs/pages/09_VIDEO_REQUIREMENTS.md`](../camxora_python/.docs/pages/09_VIDEO_REQUIREMENTS.md) §12.2 (analysis cache), [`09_VIDEO_ENTERPRISE_ARCHITECTURE.md`](../camxora_python/.docs/pages/09_VIDEO_ENTERPRISE_ARCHITECTURE.md)  
> **Last updated:** 2026-07-20

---

## 1. Purpose

Camxora GPU export is structurally slower than CapCut and Vizzy.io on the same hardware because:

1. Every export spawns a **cold Python subprocess** and recomputes **full librosa STFT** analysis.
2. Every frame does **GPU → CPU readback** (`fbo_out.read()`) and pipes raw RGBA to ffmpeg.
3. Preview (Qt GL) and export (headless subprocess) are **two warm-up paths** for the same template.

This document defines **all phases** of the performance program as numbered requirements with acceptance criteria. Work through tasks **in order** unless a dependency note says otherwise.

---

## 2. Language & stack policy

| Layer | Language | Notes |
|-------|----------|-------|
| UI, Progress, Pipeline, coordinators | **Python** (PySide6) | Unchanged |
| Renderer, shaders, integrator | **Python + GLSL** | `visualizer/` |
| Analysis cache, daemon, workers | **Python** | New services in `features/video/` |
| ffmpeg fallback encode | **Python subprocess** | Kept as safety net |
| Optional zero-copy encoder (REQ-3.5, in parallel with Phase 2) | **Small C++ DLL** | Optional plugin; not a language migration |

**Rule:** No rewrite of Camxora in another language. Native code is allowed for the optional Windows encode bridge (REQ-3.5); Phase 2 Python work continues in parallel.

---

## 3. Target metrics (benchmark contract)

Use this fixture for every phase sign-off:

| Field | Value |
|-------|-------|
| GPU | NVIDIA GTX 1050 Ti (or document substitute) |
| Song | 3-minute MP3, 44.1 kHz |
| Template | Default marketplace visualizer, 1080p, spectrum + logo + particles |
| Export FPS | 24 |
| Speed mode | `fast` (after REQ-1.7) |

| Metric | Today (~) | Phase 1 | Phase 2 | Phase 3 |
|--------|-----------|---------|---------|---------|
| Init before first frame | 1–3+ min | < 15 s | < 5 s | < 5 s |
| Realtime factor (1080p) | 0.3–1× | 2–4× | 5–10× | 10–20× |
| Video Encode % during render | Often 0% | > 0% when encoding | > 0% sustained | NVENC saturated |
| Second song in batch (warm) | Same as cold | < 30 s init | < 10 s | < 5 s |

Log results in `docs/changelog/` per release.

---

## 4. Architecture north star

```
┌─────────────────────────────────────────────────────────┐
│  Camxora UI — Video, Progress, Pipeline                 │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  ExportCoordinator + ExportGate (NVENC session cap)      │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │                                 │
┌───────▼──────────┐            ┌─────────▼──────────┐
│ PreviewEngine    │            │ EncodePipeline     │
│ (Qt GL, warm)    │───────────►│ pipe → NVENC       │
│ render_frame()   │  Phase 2+  │ optional zero-copy │
└──────────────────┘            └────────────────────┘
        │
┌───────▼──────────┐
│ AnalysisCache    │  SHA1(mp3 + settings) → STFT/beats
└──────────────────┘
```

Subprocess export remains a **fallback** after Phase 2 (crash isolation), not the default path.

---

# Phase 1 — Foundation (target: v0.3.0)

**Theme:** Same architecture, remove waste. **100% Python.**

| ID | Task | Status |
|----|------|--------|
| REQ-1.1 | Audio analysis cache | ☑ |
| REQ-1.2 | Visualizer daemon | ☑ |
| REQ-1.3 | Remove FFmpeg CPU `vflip` | ☑ |
| REQ-1.4 | Disable MSAA on export | ☑ |
| REQ-1.5 | NV12 pipe (smaller payload) | ☑ |
| REQ-1.6 | Async PBO readback | ☑ |
| REQ-1.7 | Export UX: codec badge, progress, defaults | ☑ |
| REQ-1.8 | Export quality tiers (Draft / Standard / Master) | ☑ |

---

## REQ-1.1 — Audio analysis cache

**Problem:** Export subprocess runs full `librosa.load` + STFT + onset + beat track on every job. Preview may have already analyzed the same MP3.

**Requirements:**

1. Persist analysis keyed by `SHA1(file_bytes) + analysis_settings_hash`.
2. Cache location: `%LOCALAPPDATA%/Camxora/cache/audio-analysis/` (or existing app data path via `app_paths.py`).
3. Cached payload: magnitude matrix (or compressed), onset envelope, beat frame set, duration, sample rate, hop length, point count, fps — enough to reconstruct `AudioAnalyzer` without librosa on cache hit.
4. Preview writes cache on first analysis; export reads cache before librosa.
5. Invalidate on MP3 mtime/size change or settings hash mismatch.
6. API: `get_audio_analysis_cache(path) -> CachedAnalysis | None`, `set_audio_analysis_cache(path, data)`.

**Acceptance criteria:**

- [ ] Second export of same MP3 skips librosa (log: `analysis cache hit`).
- [ ] Progress passes "Analyzing audio…" in < 2 s on cache hit.
- [ ] Unit tests: cache hit/miss, invalidation, corrupt cache recovery.
- [ ] Matches `09_VIDEO_REQUIREMENTS.md` §12.2 contract.

**Primary files:**

- `camxora_python/visualizer/audio.py` — load from cache
- `camxora_python/shared/services/` — new `audio_analysis_cache.py`
- `camxora_python/visualizer/preview_widget.py` — write on analyze
- `camxora_python/tests/test_audio_analysis_cache.py` — new

**Depends on:** none  
**Blocks:** REQ-1.2, REQ-2.2

---

## REQ-1.2 — Visualizer daemon

**Problem:** Each export spawns `Camxora.exe --visualizer` (PyInstaller boot + imports + GLFW + shader compile).

**Requirements:**

1. Long-lived worker process started on first export (or app launch setting).
2. Jobs sent over stdin/localhost socket: `{ jobId, mp3, templateB64, background, logo, settings }`.
3. Worker stays warm: GL context, compiled shaders, optional analysis cache in memory.
4. `ExportJob` uses daemon when available; falls back to one-shot subprocess on daemon crash.
5. Graceful shutdown on app exit; single worker default (respect `ExportGate`).

**Acceptance criteria:**

- [ ] Second export in same session avoids PyInstaller cold start (log: `daemon job accepted`).
- [ ] Batch export: track 2+ init < 30 s vs track 1.
- [ ] Cancel/kill job does not kill daemon.
- [ ] Tests: daemon lifecycle mock or integration test.

**Primary files:**

- `camxora_python/visualizer/daemon.py` — new
- `camxora_python/features/video/services/export_job.py`
- `camxora_python/run_entry.py` — `--visualizer-daemon` mode
- `camxora_python/app/application.py` — start/stop daemon

**Depends on:** REQ-1.1 (recommended)  
**Blocks:** REQ-2.1

---

## REQ-1.3 — Remove FFmpeg CPU `vflip`

**Problem:** `_start_ffmpeg` applies `-vf vflip,scale=…` on every frame after CPU readback. Images are already flipped on load (`_load_image_rgba` uses `np.flipud`).

**Requirements:**

1. Remove `vflip` from ffmpeg video filter chain.
2. Verify output orientation matches preview on golden template fixture.
3. If any template/regression shows upside-down output, fix in post shader once (not ffmpeg).

**Acceptance criteria:**

- [ ] ffmpeg command has no `vflip`.
- [ ] Golden template A/B: pixel row order matches preview.
- [ ] No upside-down exports in manual smoke (background, logo, text).

**Primary files:**

- `camxora_python/visualizer/gpu_render.py` — `_start_ffmpeg()`

**Depends on:** none  
**Blocks:** none

---

## REQ-1.4 — Disable MSAA on export

**Problem:** Export hidden window uses 4× MSAA; preview does not. Wastes fill rate on Pascal GPUs.

**Requirements:**

1. `_init_glfw_hidden()` accepts `samples: int` parameter.
2. Export path passes `samples=0`; preview/live paths keep current MSAA if any.
3. Document minor softening vs preview in release notes (acceptable tradeoff).

**Acceptance criteria:**

- [ ] Export GLFW window created with `SAMPLES=0`.
- [ ] Measurable FPS improvement on benchmark fixture (log frames/sec in debug mode).
- [ ] Preview unchanged.

**Primary files:**

- `camxora_python/visualizer/gpu_render.py` — `_init_glfw_hidden()`, `run_gpu_render()`

**Depends on:** none  
**Blocks:** none

---

## REQ-1.5 — NV12 pipe (smaller payload)

**Problem:** RGBA pipe at 1080p ≈ 8.3 MB/frame. NV12 ≈ 3.1 MB/frame.

**Requirements:**

1. Add GPU shader pass (or post pass) to output NV12 layout, or CPU convert in pipelined thread (prefer GPU).
2. ffmpeg rawvideo input: `-pix_fmt nv12` instead of `rgba`.
3. Feature flag or speed tier: NV12 on for `fast`/`very_fast`; RGBA fallback for `balanced` until parity verified.
4. Remove redundant `scale` filter if dimensions already match.

**Acceptance criteria:**

- [ ] 1080p export uses NV12 pipe in `fast` mode.
- [ ] Output MP4 visually matches RGBA path on golden fixture (SSIM or manual review).
- [ ] Benchmark shows reduced wall time vs RGBA at same preset.

**Primary files:**

- `camxora_python/visualizer/gpu_render.py` — encode loop, `_start_ffmpeg()`
- `camxora_python/visualizer/shaders/` — NV12 conversion if needed

**Depends on:** REQ-1.3  
**Blocks:** REQ-1.6

---

## REQ-1.6 — Async PBO readback

**Problem:** `fbo_out.read()` synchronizes GPU every frame; render and readback cannot overlap.

**Requirements:**

1. Double-buffered PBO readback: read frame N while rendering N+1.
2. Integrate with pipelined ffmpeg writer thread (decode from PBO while GPU draws).
3. Fallback to sync `read()` if PBO unsupported.

**Acceptance criteria:**

- [ ] Export loop overlaps read + render (debug timing shows parallel stages).
- [ ] Output identical to sync path on golden fixture.
- [ ] No deadlocks on cancel mid-export.

**Primary files:**

- `camxora_python/visualizer/gpu_render.py` — frame loop
- Optional: `camxora_python/visualizer/readback.py` — new

**Depends on:** REQ-1.5 (recommended)  
**Blocks:** REQ-2.4

---

## REQ-1.7 — Export UX: codec badge, progress, defaults

**Problem:** Users cannot tell if NVENC or CPU x264 is active; progress resets during init; pipeline defaults to slow `balanced` mode.

**Requirements:**

1. **Codec badge** in Progress row detail and Video export footer: `NVENC`, `CPU x264`, or `failed → fallback`.
2. Detect active codec from ffmpeg stderr or explicit log line at encoder start.
3. **Monotonic progress** through init (0.0 → 0.1 → frame loop); never reset to 0 after "Starting encoder".
4. Remove `[DEBUG]` shader messages from export hot path (or gate behind env var).
5. Pipeline default `videoExportSpeedMode`: `fast`.
6. Skip `export_gate.throttle_spawn()` for manual single export (keep for batch).

**Acceptance criteria:**

- [ ] Footer shows `NVENC` on GTX 1050 Ti with bundled ffmpeg.
- [ ] Progress bar never jumps backward at encoder start.
- [ ] Pipeline exports use `fast` unless user overrides.

**Primary files:**

- `camxora_python/features/video/services/export_job.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/visualizer/gpu_render.py` — progress `_send()` values

**Depends on:** none (partially done in v0.2.5 — verify and complete)  
**Blocks:** none

---

## REQ-1.8 — Export quality tiers

**Problem:** One export path serves pipeline batch and manual master export; no Vizzy-style draft speed option.

**Requirements:**

1. Define tiers:

   | Tier | Resolution | FPS | Speed | MSAA | Glow passes | Use |
   |------|------------|-----|-------|------|-------------|-----|
   | **Draft** | 1280×720 or 1024×768 | 24 | `very_fast` | off | reduced | Progress pipeline default |
   | **Standard** | 1920×1080 | 24 | `fast` | off | full | Video tab default |
   | **Master** | user choice | user choice | `balanced` | off | full | Manual export option |

2. Setting keys: `videoExportTier` or derive from existing resolution/speed fields.
3. Progress pipeline uses **Draft** unless profile overrides.
4. UI label in export panel and Settings.

**Acceptance criteria:**

- [ ] Pipeline batch uses Draft tier by default.
- [ ] Draft tier ≥ 2× faster than Standard on benchmark fixture.
- [ ] Template/marketplace JSON unchanged.

**Primary files:**

- `camxora_python/features/video/lib/render_scene_request.py`
- `camxora_python/features/video/widgets/export_queue_panel.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`
- `camxora_python/shared/lib/settings_workspace.py`

**Depends on:** REQ-1.4, REQ-1.7  
**Blocks:** REQ-2.5

---

### Phase 1 exit gate

- [ ] Benchmark realtime factor ≥ **2×** on GTX 1050 Ti fixture (verify on hardware after v0.3.0 build).
- [x] All REQ-1.x acceptance criteria implemented in code.
- [ ] Release **v0.3.0** with changelog + installer.

---

# Phase 2 — Unified export engine (target: v0.4.x)

**Theme:** One warm renderer; preview and export share state. **Python + GLSL.**

| ID | Task | Status |
|----|------|--------|
| REQ-2.1 | FrameIntegrator extraction | ☑ partial (slices; dual paths remain) |
| REQ-2.2 | In-process export from preview GL | ☑ flag-gated (`CAMXORA_INPROCESS_EXPORT=1`) |
| REQ-2.3 | GPU spectrum vertex path | ☑ slice 1–2 bars (beads/waveforms CPU) |
| REQ-2.4 | Pipelined encode writer thread | ☑ |
| REQ-2.5 | ExportCoordinator refactor | ☑ manual path |
| REQ-2.6 | Subprocess fallback + feature flag | ☑ flag + fallback (default still off) |
| REQ-2.7 | Golden frame parity tests | ☑ minimal fixture only |

---

## REQ-2.1 — FrameIntegrator extraction

**Problem:** Motion/audio/spectrum logic duplicated between `preview_widget.py` and `gpu_render.py` (~4500 lines).

**Requirements:**

1. New module `visualizer/frame_integrator.py`:
   - Input: template dict, `AudioAnalyzer` (or cache), `time_sec`, `export_fps`, `dt`.
   - Output: uniforms, particle state, bg/logo offsets, spectrum FFT smoothed, text overlay state.
2. Includes: 60 Hz sub-step loop, `apply_automations()`, kick/bass envelopes, shake — single source.
3. Preview `paintGL` calls integrator; export frame loop calls same integrator.

**Acceptance criteria:**

- [ ] No duplicated shake/envelope blocks in preview vs export.
- [ ] Golden frame at t=1s, t=30s matches within tolerance (preview PNG vs export PNG).

**Primary files:**

- `camxora_python/visualizer/frame_integrator.py` — new
- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/visualizer/gpu_render.py`

**Depends on:** Phase 1 complete  
**Blocks:** REQ-2.2, REQ-2.7

---

## REQ-2.2 — In-process export from preview GL

**Problem:** Export subprocess cannot reuse preview's warm GL context or analysis.

**Requirements:**

1. `SpectrumPreviewWidget` (or dedicated offscreen FBO in same context) renders export frames.
2. Export runs on **QThread**; GL context made current on export thread per Qt rules.
3. Reuse integrator + analysis cache from preview session when same MP3/template.
4. Encode via existing pipe path (Phase 1 NV12/PBO) from export thread.

**Acceptance criteria:**

- [ ] Manual export from Video tab does not spawn subprocess when `CAMXORA_INPROCESS_EXPORT=1`.
- [ ] Second export of same template starts encoding within 5 s.
- [ ] Preview remains responsive or shows "Exporting…" overlay.

**Primary files:**

- `camxora_python/visualizer/preview_widget.py`
- `camxora_python/features/video/workers/manual_export_worker.py`
- `camxora_python/features/video/services/export_coordinator.py` — new or extend

**Depends on:** REQ-2.1, REQ-1.1, REQ-1.6  
**Blocks:** REQ-2.5

---

## REQ-2.3 — GPU spectrum vertex path

**Problem:** Per-frame NumPy vertex build for 1024-point spectrum + glow passes is CPU-heavy.

**Requirements:**

1. Move bar/waveform vertex generation to GPU (compute shader or instanced draw with FFT texture).
2. Upload FFT bins as 1D texture or SSBO each frame (small payload vs full vertex rebuild).
3. Keep spectrum **styles** and template keys unchanged for marketplace parity.
4. CPU fallback path behind flag until all styles ported.

**Slice 1 (2026-07-20):** Export `run_gpu_render` default bar geometry only (`orbit-spikes` / classic vertical). Flag `CAMXORA_GPU_SPECTRUM=1`. Module `visualizer/spectrum_gpu.py`. See `docs/changelog/2026-07-20-gpu-spectrum-bar-slice1.md`.

**Slice 2 (2026-07-20):** GPU path covers thin-lines, signal-needles, grid-steps, pixel-bars, mirror-blades, symmetrical-bars, drift-capsules, floating-blocks, ignition-flare, neon-pulse. Remaining CPU: `pulse-beads` / `dot-matrix` (multi-quad), all waveform styles, preview widget parity.

**Acceptance criteria:**

- [ ] CPU usage during export drops measurably vs Phase 1.
- [ ] All built-in spectrum styles pass golden frame tests.

**Primary files:**

- `camxora_python/visualizer/gpu_render.py`
- `camxora_python/visualizer/_spectrum_fast.py`
- GLSL shader sources

**Depends on:** REQ-2.1  
**Blocks:** none

---

## REQ-2.4 — Pipelined encode writer thread

**Problem:** `enc.stdin.write(raw)` blocks render loop when ffmpeg ingest is slow.

**Requirements:**

1. Bounded queue (2–3 frames) between render thread and writer thread.
2. Back-pressure: drop render if queue full (should not happen with PBO overlap).
3. Clean shutdown on cancel; no zombie ffmpeg.

**Acceptance criteria:**

- [ ] Render thread not blocked on stdin for > 10 ms p95 during benchmark.
- [ ] Cancel mid-export terminates ffmpeg within 2 s.

**Primary files:**

- `camxora_python/visualizer/encode_pipeline.py` — new
- `camxora_python/visualizer/gpu_render.py`

**Depends on:** REQ-1.6  
**Blocks:** REQ-2.2

---

## REQ-2.5 — ExportCoordinator refactor

**Problem:** Export logic scattered across workers, `export_job.py`, pipeline automation.

**Requirements:**

1. Single `ExportCoordinator` API:
   - `start_export(request) -> job_id`
   - `cancel_export(job_id)`
   - `on_progress(callback)` — same `MG_EVENT` shape for UI compatibility
2. Chooses backend: in-process GL → daemon → one-shot subprocess (priority order).
3. Respects `ExportGate` for all backends.

**Acceptance criteria:**

- [ ] Video manual export and pipeline export both route through coordinator.
- [ ] Progress page unchanged contract (`MG_EVENT` fields preserved).

**Primary files:**

- `camxora_python/features/video/services/export_coordinator.py` — new
- `camxora_python/features/video/workers/manual_export_worker.py`
- `camxora_python/features/video/workers/pipeline_export_worker.py`
- `camxora_python/features/video/services/pipeline_automation_service.py`

**Depends on:** REQ-2.2, REQ-1.2  
**Blocks:** Phase 3

---

## REQ-2.6 — Subprocess fallback + feature flag

**Requirements:**

1. Env/settings: `CAMXORA_INPROCESS_EXPORT` (default off in 2.0, on in 2.1 after parity).
2. On GL crash during export: auto-fallback to daemon/subprocess once; surface warning in footer.
3. Log which backend was used per job.

**Acceptance criteria:**

- [ ] Force-kill GL during export → fallback completes or fails gracefully with message.
- [ ] Support can read backend from log line.

**Depends on:** REQ-2.5  
**Blocks:** none

---

## REQ-2.7 — Golden frame parity tests

**Requirements:**

1. Fixtures: 3 templates (minimal, full effects, marketplace sample) × 3 timestamps.
2. CI compares preview PNG vs export PNG (perceptual hash or RMSE threshold).
3. Run on Windows CI or local pre-release script.

**Acceptance criteria:**

- [ ] `pytest camxora_python/tests/test_export_golden_frames.py` passes.
- [ ] Regressions block release until updated baselines reviewed.

**Depends on:** REQ-2.1  
**Blocks:** REQ-2.6 default-on

---

### Phase 2 exit gate

- [ ] Benchmark realtime factor ≥ **5×** on GTX 1050 Ti fixture.
- [ ] In-process export default for manual export.
- [ ] Release **v0.4.0** + changelog.

---

# Phase 3 — Scale & CapCut parity (target: v0.5.x – v1.0)

**Theme:** Production batch speed, 4K, metrics, optional native encode. **Python core; optional tiny native plugin.**

| ID | Task | Status |
|----|------|--------|
| REQ-3.1 | Incremental / streaming analysis | ☐ |
| REQ-3.2 | Segment mux export (long songs) | ☐ |
| REQ-3.3 | Export metrics & diagnostics | ☐ |
| REQ-3.4 | 4K + GPU-only effect catalog rules | ☐ |
| REQ-3.5 | Optional NativeEncodeBridge (Windows) | ☑ scaffold done; NVENC encode (CPU NV12 upload) done; zero-copy follow-up |
| REQ-3.6 | Multi-NVENC worker policy (pro GPUs) | ☐ |

---

## REQ-3.1 — Incremental / streaming analysis

**Requirements:**

1. Export may start after first 10 s of analysis available (Draft tier).
2. Background thread continues STFT while frames 0..N encode.
3. Full parity mode waits for complete analysis (Standard/Master).

**Acceptance criteria:**

- [ ] Draft export begins encoding < 5 s after click on 3-min song (cold cache).
- [ ] No audio/visual desync in output.

**Depends on:** REQ-1.1, REQ-2.2  
**Blocks:** none

---

## REQ-3.2 — Segment mux export

**Requirements:**

1. Split song into segments (e.g. 30 s); render segments sequentially; mux with ffmpeg concat.
2. Resume from failed segment (Progress pipeline).
3. **Not** parallel NVENC on single-session GPUs (GTX 1050 Ti).

**Acceptance criteria:**

- [ ] Failed segment retry does not re-render completed segments.
- [ ] Output MP4 seamless at segment boundaries.

**Depends on:** REQ-2.5  
**Blocks:** none

---

## REQ-3.3 — Export metrics & diagnostics

**Requirements:**

1. Per-job log: realtime factor, codec, backend (in-process/daemon/subprocess), avg ms/frame, cache hit/miss.
2. Optional upload to support bundle (local JSON in run folder).
3. Progress diagnostics panel shows last export stats.

**Acceptance criteria:**

- [ ] Run folder contains `export-metrics.json` after each export.
- [ ] Footer shows realtime factor on completion.

**Depends on:** REQ-2.5  
**Blocks:** none (REQ-3.5 proceeds in parallel; metrics still useful for acceptance)

---

## REQ-3.4 — 4K + GPU-only effect catalog rules

**Requirements:**

1. 4K export preset (3840×2160) with Draft tier strongly recommended.
2. Marketplace effect pack guideline: export hot path must be GPU shader only (no Python per-frame loops).
3. Validator warns pack authors at install time.

**Acceptance criteria:**

- [ ] 4K Draft export completes on 6 GB+ VRAM GPU without OOM.
- [ ] Pack validator flags known CPU-heavy patterns.

**Depends on:** REQ-2.3  
**Blocks:** none

---

## REQ-3.5 — Optional NativeEncodeBridge (Windows)

**Status:** ☑ scaffold done; NVENC encode with CPU NV12 upload done (CUDA-free). GL→D3D zero-copy still follow-up. Continues in parallel with Phase 2.

**Requirements:**

1. Small DLL: D3D11 device + NVENC session; today CPU RGBA→NV12 → `nvEncCreateInputBuffer` (hardware encode). Follow-up: D3D11 shared texture / CUDA array zero-copy.
2. Python ctypes loader; fallback to pipe if DLL missing, disabled, stubbed, or encode fails.
3. Ship in `dist/Camxora/encode/` optional component.
4. Output Annex-B H.264; remux with audio via ffmpeg `-c:v copy`.

**Acceptance criteria:**

- [x] Scaffold: DLL builds (CMake+MSVC), Python loader detects/loads, falls back when missing (`CAMXORA_NATIVE_ENCODE`).
- [x] Real NVENC encode path (CPU NV12 upload) works end-to-end via `NativeEncodeSession` / `try_native_encode_video`.
- [ ] Zero-copy path shows Video Encode > 30% during benchmark (GL→D3D follow-up).
- [ ] Realtime factor ≥ **10×** on GTX 1050 Ti vs Phase 1 baseline (zero-copy / export wiring follow-up).
- [x] Python app runs unchanged on machines without DLL.

**Depends on:** none for scaffold/encode; REQ-3.3 metrics for final zero-copy acceptance  
**Blocks:** none

---

## REQ-3.6 — Multi-NVENC worker policy

**Requirements:**

1. Detect GPU NVENC session limit; allow `videoExportWorkers` > 1 only when hardware supports multiple sessions.
2. Document GTX 1050 Ti = 1 worker max.

**Acceptance criteria:**

- [ ] Two parallel exports on 1050 Ti do not silently fall back to CPU x264.
- [ ] Settings UI caps workers based on detected GPU.

**Depends on:** REQ-2.5  
**Blocks:** none

---

### Phase 3 exit gate

- [ ] Benchmark realtime factor ≥ **10×** (with or without REQ-3.5).
- [ ] Progress pipeline batch: 3-min song Draft < 30 s wall time on GTX 1050 Ti.
- [ ] Release **v0.5.0+** with full changelog.

---

## 5. Master task order (implement one-by-one)

Use this as the sprint checklist:

```
Phase 1
  1. REQ-1.7  Export UX (finish v0.2.5 gaps)
  2. REQ-1.3  Remove vflip
  3. REQ-1.4  MSAA off export
  4. REQ-1.1  Analysis cache
  5. REQ-1.8  Quality tiers
  6. REQ-1.2  Visualizer daemon
  7. REQ-1.5  NV12 pipe
  8. REQ-1.6  Async PBO

Phase 2
  9. REQ-2.1  FrameIntegrator
 10. REQ-2.7  Golden tests (baseline)
 11. REQ-2.4  Pipelined writer
 12. REQ-2.2  In-process export
 13. REQ-2.5  ExportCoordinator
 14. REQ-2.3  GPU spectrum
 15. REQ-2.6  Fallback + default-on

Phase 3
 16. REQ-3.3  Metrics
 17. REQ-3.1  Incremental analysis
 18. REQ-3.2  Segment mux
 19. REQ-3.4  4K + pack rules
 20. REQ-3.6  Multi-NVENC policy
 21. REQ-3.5  NativeEncodeBridge (scaffold now; NVENC in parallel with Phase 2)
```

---

## 6. Release map

| Version | Requirements | Headline |
|---------|--------------|----------|
| **0.2.5** | REQ-1.7 partial | Export progress no longer frozen at init |
| **0.3.0** | REQ-1.1 – REQ-1.8 | Fast init, draft tier, codec visibility |
| **0.4.0** | REQ-2.1 – REQ-2.7 | Warm in-process export |
| **0.5.0** | REQ-3.1 – REQ-3.4 | Batch pipeline at CapCut speed |
| **0.6+** | REQ-3.5 – REQ-3.6 | Zero-copy NativeEncodeBridge + pro GPU workers |

---

## 7. Non-goals

- Cloud render farm / VPS offload (separate project).
- Changing marketplace template JSON schema.
- Replacing FFmpeg entirely.
- Rewriting Camxora in Rust/C++ (except optional REQ-3.5 plugin).
- Parallel NVENC on Pascal without session detection.

---

## 8. Related files (index)

| Path | Role |
|------|------|
| `camxora_python/visualizer/gpu_render.py` | Export frame loop, ffmpeg |
| `camxora_python/visualizer/audio.py` | librosa analyzer |
| `camxora_python/visualizer/preview_widget.py` | Preview GL |
| `camxora_python/features/video/services/export_job.py` | Subprocess wrapper |
| `camxora_python/features/video/export_gate.py` | NVENC session cap |
| `camxora_python/features/video/workers/pipeline_export_worker.py` | Batch export |
| `camxora_python/native/encode_bridge/` | REQ-3.5 optional NativeEncodeBridge (C++ DLL) |
| `camxora_python/features/video/services/native_encode_bridge.py` | ctypes loader for encode bridge |
| `docs/VIDEO_EXPORT_ROADMAP.md` | Tier summary (quick/medium/big) |

---

## 9. Changelog (this document)

| Date | Change |
|------|--------|
| 2026-07-20 | v1.1.1 — REQ-3.5 NVENC encode (CPU NV12 upload) implemented; zero-copy still follow-up |
| 2026-07-20 | v1.1.0 — Phase 2 status refresh; REQ-2.3 slice-2 bars (mirror/drift/ignition); REQ-3.5 not deferred |
| 2026-07-20 | v1.0.4 — REQ-3.5 NativeEncodeBridge scaffold started (not deferred); Phase 2 continues in parallel |
| 2026-07-19 | v1.0.3 — REQ-1.5 NV12 pipe (fast/very_fast), REQ-1.6 async PBO readback — Phase 1 complete |
| 2026-07-19 | v1.0.1 — REQ-1.7, REQ-1.3, REQ-1.4 implemented (codec badge, monotonic progress, fast default, no vflip, export MSAA off) |
