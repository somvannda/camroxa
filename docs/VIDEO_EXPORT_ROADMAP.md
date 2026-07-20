# Video Export Roadmap — Quick Wins, Medium Term, Big Refactor

> **Implementation checklist:** For numbered requirements, acceptance criteria, and task order, use **[`GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md`](GPU_EXPORT_PERFORMANCE_REQUIREMENTS.md)** (master doc — work through REQ-x.x one by one).

This document explains what each export improvement tier does, **what it does not touch**, and how it affects the Video page, marketplace, and every visual domain (spectrum, background, logo, particles, text, effects).

**All of this is desktop-local** (`camxora_python`). Nothing here requires VPS/server deploy unless you later add cloud render farms.

---

## Current architecture (today)

```
Video page UI (inspectors, marketplace picks, draft edits)
        │
        ▼
TemplateNormalizer + template_runtime.normalize_renderer_template()
        │
   ┌────┴────┐
   ▼         ▼
Preview     Export
60 Hz       24–60 FPS subprocess
Qt GL       gpu_render.run_gpu_render() → FFmpeg
preview_    export_job.py
widget.py
```

**Shared:** template JSON schema, shaders (`gpu_render._compile()`), spectrum bar builder, particle quads, `template_runtime.py`, effect pack patches, marketplace template install.

**Not shared:** frame clock (60 Hz vs export FPS), interactive UX (drag overlay, playback), FFmpeg pipe, batch workers.

---

## Tier 1 — Quick wins (in progress / done)

**Goal:** Fix wrong motion timing and offer a fast draft resolution **without changing features or marketplace contracts.**

| Change | Files | Impact on features |
|--------|-------|------------------|
| **Shake dt-scaling** — camera + background vibrate use `_smooth_env(..., dt=encode_dt)` so 24 FPS export matches preview response time | `visualizer/gpu_render.py` | Spectrum, logo, particles, text **unchanged**. Background vibrate + camera shake **less sticky** on export. |
| **Draft resolution 1024×768** — new option in export dropdown | `shared/lib/output_resolutions.py`, stage panel | Same template/marketplace content; smaller output file. User picks resolution per workspace. |
| *(optional next)* NVENC GOP tuning for motion | `gpu_render._start_ffmpeg()` | Encode quality only; no template/schema change. |

### Marketplace & video page — quick wins

| Area | Affected? | Notes |
|------|-----------|-------|
| Marketplace **video templates** | No schema change | Templates still install `template.json` → `VideoLocalStore`. Export reads same JSON. |
| Marketplace **effect packs** | No | Packs still patch draft domains (spectrum/background/logo/particles/album/title). |
| Inspectors (all domains) | No | Sliders, presets, layer editor unchanged. |
| Preview | No | Still 60 Hz; quick wins target export loop only. |
| Pipeline automation | No | Same workers; benefits from smoother export automatically. |
| Billing / export queue | No | Same API calls and credits. |
| Reel vs long branch | No | Reel still 1080×1920 when branch=reel. |

**User-visible result:** Preview still looks the same. Exported MP4s should feel **less sluggish** on vibrate/shake; choosing **1024×768** exports ~2.6× faster (Vizzy-style tradeoff).

---

## Tier 2 — Medium term

**Goal:** Faster wall-clock export and closer preview↔export parity for **motion**, still keeping one template model and marketplace format.

| Change | Status | Feature impact |
|--------|--------|----------------|
| **60 Hz sub-step integration** | Partial (FrameIntegrator slices) | Motion domains track preview more closely |
| **Async GPU readback (PBO double-buffer)** | Done | Speed only |
| **Pipelined FFmpeg writer thread** | Done | Speed + smoother progress |
| **yuv420p / NV12 pack-on-writer** | Done (Phase 2b/2c) | Encode throughput |
| **Export-time glow/particle speed caps** | Done (2d–2f + GPU tier) | Draft/Fast/Balanced lighter on 1050 Ti–class |
| **GPU spectrum bars** | Slice 1–2 (most bars); waveforms CPU | Lower CPU during export |
| **In-process warm export** | Done behind `CAMXORA_INPROCESS_EXPORT=1` | Manual export skips cold spawn |
| **Export-time motion blur** | Pending | Optional polish |
| **Disable MSAA on export** | Done (Phase 1) | Faster export |
| **Encoder profiles** | Done | Quality/speed |

### Still pending (roadmap Tier 2 leftovers + Phase 2 exit)

- Full FrameIntegrator (no duplicate preview/export motion blocks)
- Golden parity expanded + in-process **default-on**
- Waveform GPU path + beads/dot-matrix
- Official GTX 1050 Ti ≥5× sign-off + **v0.4.0**

### Marketplace & video page — medium term

| Area | Affected? | Notes |
|------|-----------|-------|
| Template JSON / pack manifests | **No** | Still `template_runtime.normalize_renderer_template()`. |
| New optional settings | **Maybe** | e.g. `exportMotionBlur: true` — backward compatible default off. |
| Preview widget | **Minimal** | Could share sub-step helper; inspectors unchanged. |
| Pipeline merge | **No** | Still FFmpeg concat after export. |
| Effect pack authors | **No** | Same `templatePatch` structure in zips. |

**Risk:** Low. Medium term stays inside `visualizer/gpu_render.py` + workers; domain registries and marketplace install paths untouched.

---

## Tier 3 — Big refactor (unified render engine) + NativeEncodeBridge

**Goal:** One authoritative frame integrator for preview **and** export, **zero-copy NVENC via C++ DLL (in parallel — not deferred)**, better maintainability for future marketplace packs and new spectrum styles.

This is **not a server project**. It replaces how the desktop app **turns template JSON + assets + time → pixels**.

### What the big refactor builds

```
                    ┌─────────────────────────────┐
                    │   FrameIntegrator (new)      │
                    │   integrate(time_sec, dt)    │
                    │   - audio features @ 60Hz    │
                    │   - spectrum FFT smooth        │
                    │   - bg / logo / particles    │
                    │   - shake, automations       │
                    │   - text overlays            │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      PreviewSurface          ExportSurface         PNG sequence
      (Qt GL, 60Hz)           (GLFW + pipe)         (parallel workers)
              │                    │                    │
              └────────────────────┴────────────────────┘
                                   ▼
                            Optional NVENC zero-copy
                            (skip CPU RGBA readback)
```

### Components

| Component | Purpose |
|-----------|---------|
| **`FrameIntegrator`** | Single module: given template dict + analyzer + time, returns layer uniforms, particle state, bg offset, logo transform. **Eliminates preview/export drift.** |
| **`RenderBackend` interface** | `QtBackend` (preview), `GlfwOffscreenBackend` (export), future headless server render |
| **`EncodePipeline`** | Sync pipe (today) → threaded pipe (medium) → zero-copy NVENC (long) |
| **Two-pass export (optional)** | Render `{run}/frames/%06d.png` in parallel → FFmpeg encode pass with resume |

### Impact by video domain

| Domain | Big refactor impact |
|--------|---------------------|
| **Spectrum** | Same `layers[]`, styles, colors, glow. **Implementation** moves into integrator; new styles added once, work in preview + export automatically. Marketplace spectrum packs unchanged. |
| **Background** | Same `backgroundSettings` (grade, motion, fit, offset). Pan/zoom/vibrate math centralized; pipeline batch backgrounds still passed as `--background` path. |
| **Logo** | Same `logoSettings` (size, spin, reactivity, circle mask). WYSIWYG improves because shake/spin share integrator with preview. |
| **Particles** | Same `particlesSettings`. Sub-step spawn/travel in integrator; pack presets still apply via draft patch. |
| **Album / Title text** | Same `albumText` / `titleText` → `inject_text_domains_into_template()`. Drag overlay stays preview-only; committed positions in template export correctly. |
| **Effects** | Vignette, smoke, camera shake — one code path. Preview currently **does not** update camera shake state; refactor can fix WYSIWYG for shake. |
| **Automations** | `apply_automations()` stays; called from integrator per sub-step. |
| **Audio** | `AudioAnalyzer` unchanged; integrator may precompute feature cache memmap for long songs (speed). |

### Impact on Video page UI

| UI area | Change |
|---------|--------|
| Left rail inspectors | **No redesign** — still patch draft → normalizer → preview |
| Stage panel preview | **Internal** — calls `FrameIntegrator` instead of inline `paintGL` math |
| Export queue / workers | **Internal** — same buttons; faster/more reliable backend |
| Resolution / FPS / speed dropdowns | **Same** settings keys |
| Text drag overlay | **Unchanged** — preview-only interaction |
| Diagnostics panel | May show integrator timing instead of raw GL stats |

### Impact on Marketplace

| Marketplace type | Impact |
|------------------|--------|
| **Video templates** (full scene zip) | **No format change.** `template.json` + manifest still installed to `VideoLocalStore`. Refactor reads same normalized template. **Benefit:** marketplace templates look identical in preview and export. |
| **Effect packs** (domain patches) | **No manifest change.** `effect_pack_draft_state.py` still merges `templatePatch`. **Benefit:** pack authors test once; export parity guaranteed. |
| **Platform API catalog** | **No change** unless you add new metadata (e.g. recommended export FPS) later — optional, backward compatible. |
| **Install / reinstall flow** | **Unchanged** — `MarketplaceCoordinator` → `insert_marketplace_template()` |

### Impact on pipeline automation

| Feature | Impact |
|---------|--------|
| Batch export workers | Same queue; faster per job if zero-copy / pipelining |
| Pipeline export (batch AI background) | Same `build_pipeline_render_scene_request()`; background path from progress meta unchanged |
| Auto-merge / reel | **No change** — `pipeline_merge.py` still concat MP4s |
| Progress page export status | **No change** |
| Billing (`video_billing.py`) | **No change** |

### What the big refactor does **not** do

- Does **not** replace FFmpeg with a cloud service (unless you add that separately).
- Does **not** change marketplace zip structure or admin upload flows.
- Does **not** remove reel/long branches or merge shuffle.
- Does **not** require re-saving user templates (normalization stays backward compatible).
- Does **not** automatically fix old CPU renderer path in `main.py` (`--renderer cpu`) — that legacy path may be deprecated.

### Migration strategy (when/if you do big refactor)

1. Extract `FrameIntegrator` from `gpu_render.run_gpu_render` + `preview_widget.paintGL` shared sections.
2. Wire preview to integrator behind feature flag (`CAMXORA_UNIFIED_RENDER=1`).
3. Wire export subprocess to same integrator; A/B compare MP4 checksums on golden templates.
4. Add pipelined encode, then optional zero-copy on Windows NVENC.
5. Deprecate duplicate shake/math blocks in `gpu_render.py` (~4500 lines today).

**Estimated effort:** 3–6 weeks for unified integrator + pipelining; +2–4 weeks for zero-copy and two-pass export.

---

## Can you skip to big refactor?

Yes, but you still must implement **timing correctness inside** the new integrator (what quick wins fix today). Skipping quick wins means sticky export until the big refactor ships.

Recommended path:

1. **Quick wins now** — shake dt + 1024×768 (days)
2. **Medium** — 60 Hz sub-steps + async readback (weeks)
3. **Big refactor** — when adding new spectrum styles or marketplace packs becomes painful due to dual code paths

---

## Related files

| Path | Role |
|------|------|
| `camxora_python/features/video/views/video_view.py` | Video page controller |
| `camxora_python/features/video/services/template_normalizer.py` | Draft → renderer dict |
| `camxora_python/visualizer/template_runtime.py` | Template schema normalization |
| `camxora_python/visualizer/preview_widget.py` | 60 Hz preview |
| `camxora_python/visualizer/gpu_render.py` | Export render + FFmpeg |
| `camxora_python/features/marketplace/coordinator.py` | Template marketplace install |
| `camxora_python/features/video/lib/effect_pack_draft_state.py` | Effect pack → draft |
| `camxora_python/features/video/services/export_job.py` | Export subprocess |
| `camxora_python/features/video/lib/pipeline_merge.py` | Post-export merge |

---

## Changelog

- **2026-07-20** — Status refresh: Tier 2 mostly landed; REQ-2.3 slice-2 bars; NativeEncodeBridge C++ started in parallel (not deferred).
- **2026-07-19** — Quick win: shake dt-scaling in export; draft resolution 1024×768 added.
