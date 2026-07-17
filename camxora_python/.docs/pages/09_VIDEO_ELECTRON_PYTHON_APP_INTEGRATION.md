# Video — Electron ↔ python_app Integration Requirements

> **Document ID:** CAMXORA-PAGE-09-VIDEO-INTEGRATION  
> **Version:** 1.1.0  
> **Status:** Approved for planning (not implemented)  
> **Parent:** [`09_VIDEO_REQUIREMENTS.md`](09_VIDEO_REQUIREMENTS.md)  
> **Enterprise architecture:** [`09_VIDEO_ENTERPRISE_ARCHITECTURE.md`](09_VIDEO_ENTERPRISE_ARCHITECTURE.md)  
> **Last updated:** 2026-07-08

---

# 1. Document purpose

This document defines **how three codebases work together** to deliver the Camxora Video page in `camxora_python`:

| Layer | Codebase | Role |
|-------|----------|------|
| **Product & data** | `camxora/` (Electron) | Source of truth for UI behavior, template JSON schema, draft model, effect packs, REST/pipeline export contracts |
| **GPU engine** | `python_app/` | Proven ModernGL preview + export subsystem (not the UI or template schema) |
| **Delivery target** | `camxora_python/` | PySide6 shell that **implements Electron parity** and **embeds the python_app GPU engine** behind a normalized boundary |

**Read this document together with** [`09_VIDEO_REQUIREMENTS.md`](09_VIDEO_REQUIREMENTS.md). The parent doc covers page UX, domains, and acceptance criteria; **this doc covers cross-repo architecture, data contracts, and port boundaries**.

---

# 2. Three-layer model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         camxora (Electron) — AUTHORITY                       │
│  UI/UX · draft state · domain inspectors · effect packs · save/API · IPC    │
│  Template JSON schema · renderSceneRequest · pipeline inputs · registry      │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ parity contracts (must match exactly)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      camxora_python — INTEGRATION SHELL                      │
│  PySide6 VideoView · coordinators · PlatformApi · EffectPackService         │
│  TemplateNormalizer (Electron JSON → renderer dict)                          │
│  PreviewBridge · ExportCoordinator · ExportGate                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ RenderRequest / PreviewConfig DTOs
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    python_app/visualizer — GPU SUBSYSTEM                     │
│  ModernGL shaders · spectrum/background/logo/particles/text · audio FFT      │
│  gpu_render.py · QOpenGLWidget preview · subprocess export (main.py CLI)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Golden rules

| ID | Rule |
|----|------|
| **G-1** | **Electron wins on product behavior.** If Electron and python_app disagree on field names, defaults, or save shape, Electron is canonical. |
| **G-2** | **python_app wins on GPU implementation.** Do not port Electron WebGPU shaders; port/adapt `python_app/visualizer/`. |
| **G-3** | **Single template on disk.** Saved templates must be byte-compatible with Electron `{userData}/video/*.json`. |
| **G-4** | **Draft before save.** Preview and manual export always use **live draft** merged from domain slices; never silently mutate saved template. |
| **G-5** | **Renderer isolation.** UI code never imports ModernGL directly; only `visualizer/` and thin bridge widgets do. |
| **G-6** | **Effect packs are Electron-shaped.** python_app has no pack system; all pack install/merge/activate logic comes from Electron contracts. |

---

# 3. Responsibility matrix

## 3.1 What Electron provides (copy behavior + contracts)

| Area | Electron source | camxora_python must… |
|------|-----------------|----------------------|
| Page layout | `VideoWorkspaceShell.tsx` | 3-column shell, left domain tabs, center stage, right export/text tabs |
| Workspace state | `useVideoWorkspaceCoordinator.ts` | Load templates, MP3, logo, background paths, aspect ratio, output resolution |
| Draft model | `useVideoWorkspaceDraft.ts`, `videoTemplateDraft.ts` | Local draft per domain, dirty flags, merge on save |
| Domain slices | `features/video/domains/**` | Same fields, labels, defaults, enable toggles, layer editors |
| Text layers | `TextLayersPanel`, animation tab | Layer list, presets, per-layer inspector |
| Effect packs | `effectPackContracts.ts`, `effectPackRegistry.ts` | ZIP install, registry.json, catalog provider, apply-to-draft |
| Save patch | `buildVideoTemplateSavePatch` | PATCH body shape sent to platform/local store |
| Render scene | `renderSceneRequest.ts` | Build identical `RenderSceneRequest` for manual + pipeline export |
| Pipeline export | `videoPipelineInputs.ts`, `DesktopVideoPipelineCoordinator.tsx` | Branch assets, batch context, progress row handoff |
| Export queue UI | `ExportQueuePanel.tsx` | Workers, speed mode, merge option, stop, open folder |
| Preview behavior | `RendererVideoPreview.tsx` | Aspect box, popout, play/pause, scrub, reactive to draft |
| Shell routing | App router | `/app/video` hides page header |

## 3.2 What python_app provides (port GPU subsystem)

| Area | python_app source | camxora_python must… |
|------|-------------------|----------------------|
| Live preview widget | `views/components/_core.py` (`SpectrumPreview`) | Port as `visualizer/preview_widget.py` (QOpenGLWidget + ModernGL) |
| GPU renderer | `visualizer/gpu_render.py` | Port unchanged where possible; adapt template loader only |
| Export CLI | `visualizer/main.py` | Subprocess entry; accept Electron-normalized template JSON |
| DTO boundary | `visualizer/contracts.py` | Keep `RenderRequest`, `PreviewConfig`, `RenderProgress`, `RenderResult` |
| Template loader | `visualizer/config.py` (`load_template_any`) | **Replace** with Electron-schema normalizer (see §5) |
| Export concurrency | `features/video_export/export_gate.py` | Port `ExportGate` verbatim into `features/video/export_gate.py` |
| Page controller pattern | `features/video_export/video_page_controller.py` | Adapt to Electron coordinator responsibilities (not copy layout) |
| Aspect ratio box | `views/components/aspect_ratio_box.py` | Port for center stage framing |
| Background drag-edit | `video_view.py` drag handlers | Port interaction model onto Electron canvas-position fields |
| Audio analysis | `visualizer/audio.py` | Port for preview FFT + export frame sync |

## 3.3 What python_app does NOT provide (do not borrow)

| Item | Reason |
|------|--------|
| Center-column export panel layout | Electron puts export in **right rail**; python_app embeds export in center |
| Hard-coded spectrum presets only | Electron uses **effect packs** + template refs |
| Older template fields (`sensitivity`, etc.) | Superseded by Electron domain schema (`inputGain`, etc.) |
| PyQt6-specific styling | camxora_python uses PySide6 + `deep_blue.py` |
| Standalone app routing / login | camxora_python uses existing `PlatformApi` + shell |
| Marketplace / pack registry | Build from Electron `effectPackRegistry.ts` |

## 3.4 What camxora_python builds new

| Component | Purpose |
|-----------|---------|
| `features/video/views/video_view.py` | Electron-parity shell |
| `features/video/coordinators/video_workspace_coordinator.py` | Merges Electron draft logic + python_app preview/export hooks |
| `features/video/services/template_normalizer.py` | Electron template JSON → renderer dict |
| `features/video/services/effect_pack_service.py` | Registry + catalog provider (Electron contracts) |
| `features/video/services/render_scene_builder.py` | Port of `renderSceneRequest.ts` logic |
| `visualizer/` | Copied/adapted from `python_app/visualizer/` |
| `features/video/workers/export_worker.py` | QThread + subprocess + ExportGate |
| Tests | Draft merge, normalizer, pack merge, render scene parity |

---

# 4. End-to-end data flows

## 4.1 Workspace boot

```
User navigates /app/video
        │
        ▼
VideoWorkspaceCoordinator.load()
        │
        ├─► PlatformApi.getVideoWorkspaceState()     ← Electron API parity
        │       returns: templateId, paths, aspect, resolution, templates list
        │
        ├─► Load saved template JSON from userData/video/{id}.json
        │
        ├─► buildVideoTemplateDraft(savedTemplate)   ← Electron draft builder port
        │
        ├─► EffectPackService.resolveActivePacks(draft.effectPacks)
        │       merges pack overlays into draft slices (preview-only until save)
        │
        └─► PreviewBridge.setPreviewConfig(
                PreviewConfig(
                    template=TemplateNormalizer.to_renderer_dict(draft),
                    background_path=...,
                    logo_path=...,
                    width/height from aspect box
                ))
```

## 4.2 Edit loop (single domain)

```
Inspector field change (e.g. spectrum.inputGain)
        │
        ▼
draftStore.patchDomain('spectrum', { inputGain: value })
        │
        ├─► mark domain dirty
        ├─► persist local draft snapshot (optional debounced JSON in workspace cache)
        │
        └─► PreviewBridge.update(template=normalized draft)
                │
                ▼
            SpectrumPreview (ModernGL) re-renders frame with live audio FFT
```

**Requirement:** Inspector changes must reflect in preview within one frame tick (~16ms target) for scalar fields; layer list changes may debounce 50ms.

## 4.3 Effect pack apply

```
User selects pack in domain inspector
        │
        ▼
EffectPackService.getPackManifest(packId, version)
        │
        ├─► validate manifest (effectPackContracts equivalent)
        ├─► draftStore.patchDomain(domain, packDefaultOverrides)
        ├─► draftStore.setEffectPackRef(domain, { packId, version, enabled: true })
        │
        └─► PreviewBridge.update(normalized draft)   ← MP-7: draft only, not saved
```

Save persists `effectPacks` refs + merged domain values into template JSON.

## 4.4 Save flow

```
User clicks Save
        │
        ▼
buildVideoTemplateSavePatch(draft, savedTemplate)
        │
        ├─► PlatformApi.patchVideoTemplate(templateId, patch)
        ├─► write {userData}/video/{id}.json
        ├─► clear dirty flags
        └─► refresh workspace cache
```

Saved JSON must round-trip: Electron app opens same file without migration.

## 4.5 Manual export

```
User clicks Export (manual mode)
        │
        ▼
RenderSceneBuilder.buildManualRequest(workspace, draft)
        │   produces RenderSceneRequest (Electron shape)
        │
        ▼
ExportCoordinator.enqueue(request)
        │
        ├─► ExportGate.acquire()          ← global worker cap
        ├─► Serialize template: Electron JSON (not python_app legacy)
        ├─► Spawn: python -m visualizer.main <mp3> <tmp.json> --templateB64 ... 
        │       OR in-process export API (same gpu_render path)
        │
        ├─► Stream RenderProgress → ExportQueuePanel
        └─► On complete: RenderResult → open folder / show path
```

**Critical:** Manual export uses **`draftSource: 'live'`** in render context (Electron parity).

## 4.6 Pipeline export

```
Progress row / Workflow branch triggers video step
        │
        ▼
Shell DesktopVideoPipelineCoordinator equivalent
        │
        ├─► buildVideoPipelineInputs(row, branch)   ← port videoPipelineInputs.ts
        ├─► resolve assets (MP3, background, logo paths)
        ├─► RenderSceneBuilder.buildPipelineRequest(...)
        │       context: { branch, batchId, role, draftSource: 'saved'|'live' }
        │
        └─► ExportCoordinator.enqueue (same gate + subprocess as manual)
```

Pipeline export may run **multiple concurrent jobs** across channels; `ExportGate` enforces **global** `videoExportWorkers` limit (not per-channel multiplication).

---

# 5. Template JSON contract

## 5.1 Authority

**Canonical schema:** Electron `VideoTemplate` / `VideoTemplateDraft` types and saved `{userData}/video/*.json` files.

python_app's `load_template_any()` accepts legacy shapes — **do not expose legacy shape to UI or disk**. Use a normalization layer at the renderer boundary only.

## 5.2 Normalization layer

```
┌──────────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│ Electron draft   │────►│ TemplateNormalizer      │────►│ Renderer dict    │
│ (saved + local)  │     │ to_renderer_dict()      │     │ (ModernGL input) │
└──────────────────┘     └─────────────────────────┘     └──────────────────┘
                                    │
                                    │ inverse only for legacy import tool
                                    ▼
                         from_legacy_python_app_template()  [optional, dev-only]
```

### 5.2.1 Field mapping examples (legacy → Electron)

| python_app (legacy) | Electron (canonical) | Notes |
|---------------------|----------------------|-------|
| `sensitivity` | `inputGain` | Renamed; normalizer maps if old file detected |
| `barWidth` | `barWidth` | Same |
| `smoothing` | `smoothing` | Same |
| flat `background` path string | `backgroundSettings.path` + domain object | Electron uses nested domain |
| `logoSettings` partial | `logoSettings` full contract | Match Electron defaults |
| N/A | `effectPacks.spectrum` | Electron-only; renderer ignores unknown keys safely |
| N/A | `textLayers[]` | Electron schema; renderer consumes normalized list |

### 5.2.2 Normalizer requirements

| ID | Requirement |
|----|-------------|
| **N-1** | `to_renderer_dict(draft: VideoTemplateDraft) -> dict` — stable keys consumed by gpu_render |
| **N-2** | Unknown Electron keys pass through without stripping (forward compatibility) |
| **N-3** | Missing optional keys filled from Electron default constants (port from TS) |
| **N-4** | Unit tests: golden fixtures from Electron `__fixtures__/videoTemplates/` |
| **N-5** | Renderer never reads draft store directly — always through normalizer |

## 5.3 Domain merge semantics

Electron merges domain patches independently. Python port must mirror:

```python
# Conceptual — match buildVideoTemplateDraft / patchDomain in TS
draft = merge_domain(draft, "spectrum", spectrum_patch)   # does not clobber background
draft = merge_domain(draft, "background", background_patch)
```

**MP-1:** Pack apply + inspector edit both use domain-scoped merge, never full-template replace unless explicit template switch.

---

# 6. Preview subsystem (ModernGL + Qt)

## 6.1 Architecture

```
VideoView (center column)
    └── AspectRatioBox
            └── SpectrumPreviewWidget (QOpenGLWidget)
                    │
                    initializeGL() → moderngl.create_context()
                    paintGL()      → gpu_render.render_frame(state, audio_fft)
                    resizeGL()     → update framebuffer size
                    │
Audio thread / timer → AudioAnalyzer.push_samples() → FFT bins → preview
```

## 6.2 Shared code path with export

| Stage | Preview | Export |
|-------|---------|--------|
| Template input | Normalized draft dict | Same dict (+ saved snapshot for pipeline) |
| GL context | Qt widget surface | Headless/offscreen ModernGL context |
| Audio | Live playback MP3 | Full-file analysis (`audio.py`) |
| Output | On-screen texture | Raw frames → ffmpeg (NVENC/x264) |
| FPS | Display refresh (~60) | `--fps` from output settings (default 60) |

**Requirement P-1:** Spectrum shader code is **one source** in `visualizer/gpu_render.py` (or imported modules); preview and export call the same `render_frame()` entry.

## 6.3 Preview ↔ Electron parity

| Behavior | Electron | python_app / camxora_python |
|----------|----------|----------------------------|
| Aspect ratio | `previewAspectRatio` | `AspectRatioBox` |
| Popout window | Separate BrowserWindow | `QDialog` + second `SpectrumPreviewWidget` |
| Play/pause/scrub | Audio element sync | `QMediaPlayer` or equivalent; seek triggers frame rebuild |
| Canvas drag (spectrum position) | Pointer events on overlay | Port python_app drag → update `spectrumCanvasPosition` in draft |
| Background drag | Same | Port to `backgroundSettings` position fields |
| Logo drag | Same | Port to `logoSettings` position fields |

## 6.4 Preview config DTO

Keep python_app contract:

```python
@dataclass(frozen=True)
class PreviewConfig:
    width: int
    height: int
    template: dict = field(default_factory=dict)
    background_path: str = ""
    logo_path: str = ""
```

Coordinator maps Electron workspace paths into `PreviewConfig` on every draft update.

---

# 7. Export subsystem

## 7.1 Process model

```
┌─────────────────┐
│ ExportCoordinator│
└────────┬────────┘
         │ enqueue(RenderSceneRequest)
         ▼
┌─────────────────┐     acquire      ┌──────────────────────┐
│ ExportWorker     │────────────────►│ ExportGate (global)  │
│ (QThread pool)   │◄────────────────│ max = videoExportWorkers│
└────────┬────────┘     release      └──────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ Subprocess: visualizer/main.py                               │
│   --templateB64 <electron-json>                              │
│   --background / --logo overrides from resolved assets       │
│   --speedMode balanced|fast|very_fast                        │
│   --width/--height/--fps from output settings                │
│   MG_EVENT progress lines → parsed by worker                 │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
    ffmpeg encode → output path from RenderSceneRequest.output
```

## 7.2 ExportGate (mandatory port)

Port `python_app/features/video_export/export_gate.py` **verbatim** unless a bug fix is required.

| Control | Purpose |
|---------|---------|
| `acquire` / `release` | Cap concurrent GPU/NVENC sessions |
| `throttle_spawn` | Stagger subprocess cold starts (disk cache warmup) |
| `set_limit` | Reflect user preference `videoExportWorkers` |

**Requirement E-1:** Auto-video pipeline multi-channel runs share **one** gate — matches python_app fix for NVENC session exhaustion.

## 7.3 Render scene request (Electron port)

Port `renderSceneRequest.ts` to `render_scene_builder.py`:

```python
@dataclass
class RenderSceneRequest:
    mode: str                          # VideoExportMode
    template: dict
    draft: dict                        # VideoTemplateDraft as dict
    assets: VideoResolvedRenderAssets
    output: VideoRenderOutputSettings
    context: RenderSceneContext        # templateId, branch, batchId, role, draftSource
```

Manual vs pipeline builders must match Electron function names and field selection logic.

## 7.4 Progress protocol

Subprocess emits lines prefixed with `MG_EVENT ` (python_app convention):

```json
{"type": "progress", "frame": 120, "total": 3600, "percent": 3.3}
{"type": "complete", "output": "C:/path/out.mp4"}
{"type": "error", "message": "..."}
```

Export worker parses JSON and emits Qt signals for UI table updates.

---

# 8. Effect packs & marketplace path

## 8.1 Division of responsibility

| Concern | Owner |
|---------|-------|
| Manifest schema (`effectPackContracts`) | Electron → port to Python dataclasses + validation |
| Registry filesystem layout | Electron `{userData}/effect-packs/` |
| Install from ZIP / URL | Electron IPC today → Python `EffectPackService.install_from_zip()` |
| Catalog listing | `EffectPackCatalogProvider` protocol |
| UI selectors in inspectors | Electron (currently partially unwired — Python implements fully per Q-4) |
| GPU shader assets inside pack | Stored in pack folder; **renderer loads by pack manifest paths** |

## 8.2 Pack → template → renderer chain

```
effect-packs/packs/{packId}/{version}/manifest.json
        │
        ▼
EffectPackService.loadPackAssets(packId, version)
        │
        ▼
draft.effectPacks[domain] = { packId, version, enabled: true }
        │
        ▼
TemplateNormalizer merges pack domain defaults + user overrides
        │
        ▼
gpu_render loads shaders/textures referenced by manifest (future: hot-reload)
```

**Today:** Spectrum packs may ship JSON overrides only. **Future marketplace:** same manifest contract; only catalog provider switches from local registry to remote API.

## 8.3 Marketplace hook (no UI in Phase 9)

```python
class EffectPackCatalogProvider(Protocol):
    def list_catalog(self) -> list[CatalogEntry]: ...
    def get_download_url(self, pack_id: str, version: str) -> str: ...

class LocalRegistryCatalogProvider: ...      # Phase 9c
class RemoteMarketplaceCatalogProvider: ...  # Phase N — same interface
```

Video UI depends on protocol only (**MP-5**).

---

# 9. Platform API & storage layout

## 9.1 API parity

Video workspace uses the same backend routes as Electron (via existing `PlatformApi`):

| Operation | Electron | Python |
|-----------|----------|--------|
| List templates | GET video workspace | Same client method |
| Save template | PATCH template | Same patch builder |
| Upload assets | multipart / paths | Same |
| Export job status | polling / events | Same |

Exact method names live in `shared/services/platform_api.py` when implemented (Phase 9a).

## 9.2 Filesystem layout (mirror Electron)

```
{userData}/
  video/
    {templateId}.json          ← saved template (Electron schema)
    drafts/
      {templateId}.json        ← optional local draft recovery
  effect-packs/
    registry.json
    packs/{packId}/{version}/
      manifest.json
      assets/...
```

**Requirement FS-1:** Template paths must be interchangeable between Electron and camxora_python on the same machine.

---

# 10. Module layout (camxora_python target)

```
camxora_python/
├── features/video/
│   ├── views/
│   │   ├── video_view.py                 # shell (Electron layout)
│   │   ├── video_stage.py                # center: aspect box + preview
│   │   ├── export_queue_panel.py         # right rail export tab
│   │   └── inspectors/                   # spectrum, background, logo, particles, text
│   ├── coordinators/
│   │   └── video_workspace_coordinator.py
│   ├── services/
│   │   ├── template_normalizer.py        # Electron → renderer
│   │   ├── effect_pack_service.py
│   │   ├── render_scene_builder.py       # port renderSceneRequest.ts
│   │   └── draft_store.py                # port useVideoWorkspaceDraft
│   ├── workers/
│   │   └── export_worker.py
│   └── export_gate.py                    # port from python_app
│
├── visualizer/                           # port from python_app/visualizer/
│   ├── contracts.py
│   ├── gpu_render.py
│   ├── audio.py
│   ├── config.py                         # thin: calls TemplateNormalizer
│   ├── main.py                           # CLI subprocess
│   └── preview_widget.py                 # port SpectrumPreview
│
└── tests/features/video/
    ├── test_template_normalizer.py
    ├── test_draft_merge.py
    ├── test_render_scene_builder.py
    └── test_effect_pack_merge.py
```

---

# 11. Source file mapping reference

| Concern | Electron (`camxora/`) | python_app | camxora_python (target) |
|---------|----------------------|------------|-------------------------|
| Page shell | `VideoWorkspaceShell.tsx` | `views/video_view.py` ❌ layout | `features/video/views/video_view.py` |
| Coordinator | `useVideoWorkspaceCoordinator.ts` | `video_page_controller.py` ⚠️ partial | `coordinators/video_workspace_coordinator.py` |
| Draft | `useVideoWorkspaceDraft.ts` | — | `services/draft_store.py` |
| Render scene | `renderSceneRequest.ts` | — | `services/render_scene_builder.py` |
| Pipeline inputs | `videoPipelineInputs.ts` | — | `services/video_pipeline_inputs.py` |
| Effect packs | `effectPackContracts.ts`, registry | — | `services/effect_pack_service.py` |
| Preview | `RendererVideoPreview.tsx` (WebGPU) | `SpectrumPreview` ✅ | `visualizer/preview_widget.py` |
| GPU render | — | `gpu_render.py` ✅ | `visualizer/gpu_render.py` |
| Export CLI | IPC → python | `visualizer/main.py` ✅ | `visualizer/main.py` |
| Export gate | — | `export_gate.py` ✅ | `features/video/export_gate.py` |
| DTOs | TS desktop types | `contracts.py` ✅ | `visualizer/contracts.py` |
| Template schema | `videoTemplateDraft.ts` | `config.py` ❌ legacy | `services/template_normalizer.py` |

Legend: ✅ port/adapt · ⚠️ pattern only · ❌ do not copy as-is

---

# 12. Threading & lifecycle

| Component | Thread |
|-----------|--------|
| UI / inspectors | Main Qt thread |
| Preview GL | Main thread (QOpenGLWidget) — no GL calls from workers |
| Audio FFT for preview | Dedicated timer or audio callback → thread-safe ring buffer → GL frame |
| Export subprocess | `QThread` worker; blocking IO isolated |
| ExportGate | Process-global; shared across workers |
| Draft auto-save | `QTimer` debounce on main thread |
| Pipeline coordinator | Main thread; enqueues export jobs |

**Requirement TL-1:** On template switch, stop preview audio, wait for export gate if needed, then reload PreviewConfig.

**Requirement TL-2:** On app exit, cancel running exports gracefully (terminate subprocess, release gate).

---

# 13. Phased integration plan

Dependencies between Electron parity work and python_app GPU port:

```
9a Shell + workspace API + draft store (Electron only, no GPU)
        │
        ▼
9b Domain inspectors (Electron fields, mock preview placeholder)
        │
        ├──────────────────┐
        ▼                  ▼
9c Effect pack service   9d TemplateNormalizer + visualizer/ port (spectrum)
        │                  │
        └────────┬─────────┘
                 ▼
9e Preview widget live (background, logo, particles, text layers)
                 │
                 ▼
9f Export worker + ExportGate + subprocess (manual export)
                 │
                 ▼
9g Pipeline export + shell coordinator
                 │
                 ▼
9h Diagnostics, recovery, performance tuning
```

| Sub-phase | Electron work | python_app port |
|-----------|---------------|-----------------|
| **9a** | Full | None |
| **9b** | Full | None |
| **9c** | Full | None |
| **9d** | Normalizer constants | `gpu_render`, `audio`, `preview_widget`, `contracts` |
| **9e** | Canvas drag parity | Layer compositing in gpu_render |
| **9f** | `renderSceneRequest` | `main.py`, `ExportGate`, `export_worker` |
| **9g** | Pipeline coordinator | Same export path |
| **9h** | Diagnostics UI | GPU memory / frame timing hooks |

---

# 14. Testing strategy

| Layer | Tests |
|-------|-------|
| Draft merge | Golden domain patches vs Electron TS test vectors (exported JSON fixtures) |
| TemplateNormalizer | Legacy python_app sample → expected Electron renderer dict |
| Render scene builder | Same input workspace → same JSON as Electron `toVideoSerializableRenderSceneRequest` |
| Effect pack merge | Manifest apply does not clobber unrelated domains |
| ExportGate | Concurrency never exceeds limit under stress |
| Preview | Smoke: widget mounts, GL init, one frame render (headless CI optional) |
| Integration | Manual: open Electron-saved template in Python preview — visual match within tolerance |

---

# 15. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Schema drift Electron ↔ renderer | Normalizer + golden fixtures; CI cross-check |
| NVENC session limits | ExportGate (proven in python_app) |
| GL context loss on resize | Follow python_app `SpectrumPreview` rebuild path |
| Effect pack shaders missing | Manifest validation before apply; fallback to default shader |
| WebGPU ≠ ModernGL visual diff | Accept minor rendering variance; document known deltas |
| Large template JSON in subprocess | `--templateB64` or temp file; match Electron IPC approach |

---

# 16. Resolved decisions (supersedes open questions)

| # | Decision | Source |
|---|----------|--------|
| D-1 | **GPU backend:** ModernGL via ported `python_app/visualizer/` | User confirmed |
| D-2 | **Schema authority:** Electron template JSON | This document §5 |
| D-3 | **Preview surface:** `QOpenGLWidget` + shared `gpu_render` | python_app pattern |
| D-4 | **Export host:** Subprocess CLI (`visualizer/main.py`) with MG_EVENT protocol | python_app pattern |
| D-5 | **Effect pack UI:** Implement Electron selectors (fix unwired baseline) | 09_VIDEO_REQUIREMENTS Q-4 |
| D-6 | **No `videoPy` route:** Single `/app/video` | Prior cleanup |

---

# 17. Acceptance criteria (integration-specific)

Add to Phase 9 Definition of Done:

- [ ] `TemplateNormalizer` passes Electron golden fixtures — see [`tests/fixtures/video/`](../../tests/fixtures/video/) + [`09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md`](09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md)
- [ ] Preview uses ModernGL from `visualizer/gpu_render.py` (not WebGPU, not CPU-only fallback as primary)
- [ ] Manual export subprocess accepts Electron-normalized template via `--templateB64`
- [ ] `ExportGate` limits global concurrent exports to `videoExportWorkers`
- [ ] `RenderSceneBuilder` output matches Electron serializable request shape
- [ ] Template saved by camxora_python opens in Electron without migration
- [ ] Effect pack installed by Electron appears in Python catalog provider (shared registry path)
- [ ] Pipeline export from Progress row uses same subprocess path as manual export

---

# 18. Related documents

- [`09_VIDEO_REQUIREMENTS.md`](09_VIDEO_REQUIREMENTS.md) — page UX, domains, full DoD
- [`09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md`](09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md) — field-by-field schema + normalizer algorithm
- [`09_VIDEO_ENTERPRISE_ARCHITECTURE.md`](09_VIDEO_ENTERPRISE_ARCHITECTURE.md) — enterprise pillars, boundaries, quality gates
- [`../../tests/fixtures/video/`](../../tests/fixtures/video/) — golden JSON fixtures (4 sets)
- [`00_PAGE_BY_PAGE_STRATEGY.md`](00_PAGE_BY_PAGE_STRATEGY.md)
- Electron: `camxora/docs/video-preview-gpu-reactivity-parity-plan.md`
- python_app: `visualizer/contracts.py`, `visualizer/gpu_render.py`, `features/video_export/export_gate.py`
