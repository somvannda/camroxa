# Video Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-09-VIDEO  
> **Version:** 1.1.0  
> **Status:** Approved for planning (not implemented)  
> **Phase:** 9  
> **Source of truth:** `camxora/src/renderer/src/features/video/`  
> **GPU engine source:** `python_app/visualizer/` (ModernGL — see integration doc)  
> **Supporting sources:** `camxora/src/shared/effectPacks/`, `camxora/src/main/effectPackRegistry.ts`, `shared/lib/videoPipelineInputs.ts`, `DesktopVideoPipelineCoordinator.tsx`  
> **Target:** `camxora_python/features/video/` + `camxora_python/visualizer/`  
> **Integration spec:** [`09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md)  
> **Implementation plan (active):** [`09_VIDEO_IMPLEMENTATION_PLAN.md`](09_VIDEO_IMPLEMENTATION_PLAN.md) — consolidated build contract for spectrum parity, persistence, server sync, and admin portal  
> **Last updated:** 2026-07-08

---

# 1. Document purpose

Complete A→Z requirements for the **Video workspace page** — template editing, live GPU preview, domain inspectors (spectrum, background, logo, particles, text), pipeline/manual export, and **effect-pack extensibility** designed for a future marketplace.

**This document is planning only.** Do not implement until Phase 9 is explicitly scheduled.

**UI rule (project standard):** Native PySide6 widgets + `shared/themes/deep_blue.py` QSS. Video is a **special shell route**: no page header; the workspace fills the content area between sidebar and status bar.

**Parity rule:** Template JSON schema, domain field names, export scene shape, and effect-pack manifest contracts must match Electron **exactly** so templates, packs, and exports are interchangeable.

**Integration rule:** Product behavior comes from **Electron**; GPU preview and export come from **`python_app/visualizer/`** (ModernGL). `camxora_python` implements Electron-parity UI and a `TemplateNormalizer` bridge — see the [integration spec](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md).

**Enterprise rule:** Layer boundaries, contract-first integration, marketplace extensibility, and production reliability gates are defined in the [enterprise architecture doc](09_VIDEO_ENTERPRISE_ARCHITECTURE.md).

---

# 2. Overview

## 2.1 What Video is

The Video page (`/app/video`) is the **visualizer template editor and export console** for Camxora. Users:

1. Select or create a **video template** (JSON document stored locally + referenced by profiles).
2. Edit visual domains in left-rail tabs while watching a **live audio-reactive preview**.
3. Manage **text overlay layers** from the stage + right rail.
4. Export either **manually** (current preview scene) or **from pipeline** (progress row + branch assets).

## 2.2 What Video is not

- Not the operational recovery table (**Progress**)
- Not the lane timeline (**Workflow**)
- Not music/image generation (**Music** / **Image**)
- Not a marketplace storefront (future); packs install into a **local registry** today

## 2.3 Shell behavior (critical)

| Property | Electron behavior | Python requirement |
|----------|-------------------|-------------------|
| Route key | `video` | `video` only (no separate `videoPy` route) |
| Page header | **Hidden** — no eyebrow/title/description card | `AppShellWidget._navigate`: `is_video = key == "video"` |
| Layout | Full-height, `overflow-hidden`, three columns | `VideoView` fills stack; min height uses full shell content |
| Status bar | Remains visible | Keep shell `QStatusBar` |

## 2.4 Architecture goals (marketplace-ready)

Even though **Marketplace is a future phase**, Video architecture must treat visual styles as **installable, versioned packages** — not hard-coded presets only.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Future Marketplace (Phase N)                 │
│  Admin Portal uploads .zip → catalog API → user Buy/Install      │
└────────────────────────────┬────────────────────────────────────┘
                             │ download / entitlement (future)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Effect Pack Registry (local, per machine)             │
│  {userData}/effect-packs/registry.json + packs/{id}/{version}/   │
└────────────────────────────┬────────────────────────────────────┘
                             │ listCatalog / install / activate
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Video Workspace (this page)                      │
│  Draft editor → preview → save template.effectPacks refs         │
└────────────────────────────┬────────────────────────────────────┘
                             │ export scene JSON
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Export worker / headless renderer                   │
└─────────────────────────────────────────────────────────────────┘
```

**Design constraints for marketplace fit:**

| ID | Constraint |
|----|------------|
| MP-1 | **Domain isolation** — spectrum/background/logo/particles patches merge independently; never overwrite unrelated template keys |
| MP-2 | **Stable pack identity** — `packId` + semver `version` stored in template `effectPacks.{domain}` |
| MP-3 | **Manifest contract** — Zod-equivalent validation in Python (`effectPackContracts`) before install |
| MP-4 | **Registry abstraction** — Video UI talks to `EffectPackService`, not filesystem directly |
| MP-5 | **Catalog provider interface** — `LocalRegistryCatalogProvider` now; `RemoteMarketplaceCatalogProvider` later without UI rewrite |
| MP-6 | **Install sources** — file (ZIP), URL (IPC today), future: marketplace download handler |
| MP-7 | **Preview before save** — applying a pack updates **local draft only** until user clicks Save |
| MP-8 | **Template compatibility** — `appVersionRange` + `domainContractVersion` gate incompatible packs |

---

# 3. Entry points & navigation

| Property | Value |
|----------|-------|
| Path | `/app/video` |
| Sidebar key | `video` |
| Label | Video |
| Title | Video |
| Eyebrow | Workspace (hidden in shell when active) |
| Description | Video workspace with template loading, live GPU preview, domain editors, and export. |

**Router:** Replace `PlaceholderPage` for `video` in `app/router.py` with `VideoView`.

**Removed route:** `videoPy` / Video (Py) — consolidated into single native Python Video page.

---

# 4. Page layout

## 4.1 Three-column grid

Electron grid: `320px | flex | 320px` (336px at 2xl).

| Column | Content |
|--------|---------|
| **Left rail** | Template header (name, Save, Delete, template dropdown) + domain tabs + active inspector + diagnostics `<details>` |
| **Stage (center)** | Preview canvas, transport, asset summary cards, text layer list |
| **Right rail** | Text/Animation inspector **or** Export queue (tabbed) |

## 4.2 Left-rail domain tabs (`VideoTabId`)

| Tab | Inspector | Default |
|-----|-----------|---------|
| `spectrum` | `SpectrumInspector` + embedded `SpectrumLayerEditor` | **Yes** |
| `background` | `BackgroundInspector` (+ atmosphere / corner effects) | |
| `logo` | `LogoInspector` (+ spectrum attach controls) | |
| `particles` | `ParticlesInspector` | |

**Text is not a left-rail tab.** Text overlays are edited via stage list + right rail.

## 4.3 Right-rail tabs (`VideoSidePanelTabId`)

| Tab | Panel |
|-----|-------|
| `text` | `TextInspectorPanel` — Basic / Style / Effects sub-modes |
| `animation` | Same panel, animation-focused |
| `export` | `ExportQueuePanel` — pipeline run picker, branch, manual export, progress |

## 4.4 Stage sections

1. **Preview card** — aspect ratio from `workspace.previewAspectRatio` (default 16:9)
2. **Transport** — skip ±5s, play/pause, stop, scrubber, output resolution select
3. **Asset summary** — Background, Logo, Track, Run Directory with tone badges (ready/warning)
4. **Quick actions** — Background picker, Edit Logo, Edit Layers (→ spectrum tab)
5. **Text Layers** — add, duplicate, delete, reorder, preset dropdown

## 4.5 Fullscreen

Electron has **no OS fullscreen mode** for Video. Python matches: maximize preview within stage column only.

---

# 5. Data requirements

## 5.1 Workspace bootstrap

**Electron:** `desktopApi.video.getWorkspaceState()` polled every 1.5s while export running.

**Python service:** `VideoWorkspaceService.get_state()` returning `VideoWorkspaceState`:

| Field | Type | Purpose |
|-------|------|---------|
| `template` | `dict` | Active template JSON |
| `template_id` | `str` | Active template id |
| `template_name` | `str` | Display name |
| `templates` | `list[{id,name,kind,updated_at}]` | Template picker |
| `output_resolution` | `str` | e.g. `1920x1080` |
| `preview_aspect_ratio` | `{width,height}` | Preview box ratio |
| `background_path` | `str` | Manual preview background |
| `logo_path` | `str` | Workspace logo path |
| `selected_mp3_path` | `str` | Preview audio |
| `mp3_directory` | `str` | MP3 scan root |
| `mp3_list` | `list[str]` | Available tracks |
| `playback` | object | Transport mirror |
| `export` | `VideoExportState` | Running, progress, paths |
| `ui` | object | `preview_title`, notes, source |

**Storage:** Templates and workspace prefs live in **local app data** (Electron main process). Python equivalent: `QStandardPaths.AppLocalDataLocation` + JSON files mirroring Electron layout.

## 5.2 REST API (pipeline context)

| # | Method | Path | Purpose |
|---|--------|------|---------|
| D-1 | GET | `/profiles` | Resolve `video_template_id` / `reel_template_id` per profile |
| D-2 | GET | `/progress?limit=80&active_only=false&from_date&to_date` | Pipeline run rows (last 30 days) |
| D-3 | PATCH | `/settings` | `outputResolution`, `videoRenderBackgroundPath` |

## 5.3 Pipeline input resolution

**Run key:** `{batch_id}:{profile_id}:{role}`

**Branch:** `long` (16:9) or `reel` (9:16)

**Resolved fields** (`resolve_video_pipeline_inputs`):

| Field | Source |
|-------|--------|
| `ready` | `meta.long_ready` or `meta.reel_ready` |
| `run_dir` | progress row |
| `background_path` | `background_16x9_path` or `background_9x16_path` |
| `thumbnail_path` | `thumbnail_16x9_path` or `thumbnail_9x16_path` |
| `recommended_template_id` | profile template id for branch |

## 5.4 Background path precedence (preview)

```
current_background =
  background_path_draft
  || workspace.background_path
  || resolved_pipeline_inputs.background_path
  || ''
```

Labels: Manual preview / Pipeline branch / No background attached.

---

# 6. Draft model

## 6.1 Types

- **`VideoTemplateDraft`** = scalar domain settings + `text_overlays[]` + `effect_packs` map
- **`TemplateSettingsDraft`** — alias used in workspace code
- **Spectrum layers** — `layers: list[dict]` tracked **separately** from scalar spectrum settings until Save

## 6.2 Local persistence

**Key:** `camxora.video.workspace-draft.{templateId}` (Electron: localStorage; Python: `QSettings` or JSON in app data)

**Snapshot:**
```json
{
  "templateName": "My Template",
  "draft": { "...domain fields..." },
  "layers": [ "...spectrum layer records..." ]
}
```

**Hydration rules:**
- On template switch, load snapshot if present; else build from persisted workspace template
- Skip re-hydration if same `template_id` already loaded (preserve unsaved edits)
- Legacy snapshots with top-level spectrum fields merged via `apply_legacy_spectrum_fields`

## 6.3 Dirty detection

Per-domain JSON compare + spectrum layer diff + template name diff → footer/tab badges.

| Domain | Dirty when |
|--------|------------|
| spectrum | scalar settings OR layers differ from saved |
| background | background + atmosphere slice differs |
| logo | logo slice differs |
| particles | particles slice differs |
| text | `text_overlays` array differs |
| name | `template_name_draft` ≠ workspace name |

## 6.4 Save patch

`build_video_workspace_template_save_patch()` merges:

- All domain template patches
- `effectPacks.{domain}` refs
- Cloned `layers[]`
- `templateName`

Persist via `patch_template(patch)` — merge into saved JSON on disk.

---

# 7. Domain: Spectrum

## 7.1 Purpose

Audio-reactive visualizer rings/bars/waves rendered in GPU preview and export. Core identity feature; primary marketplace domain (sellable “spectrum styles”).

## 7.2 Template JSON mapping

| Draft field | Template path |
|-------------|---------------|
| `spectrum_enabled` | `spectrumEnabled` |
| `style` | `style` (normalized preset key) |
| `audio_input_gain` … `flying_glow_wing_release` | `audioSettings.*` |
| `spectrum_attach_to_logo` | `previewBindings.spectrumAttachToLogo` |
| `spectrum_logo_gap` | `previewBindings.spectrumLogoGap` |
| `anchor`, `position_x`, `position_y` | `position.anchor`, `position.x`, `position.y` |
| Layer stack | `layers[]` (array of layer records) |

**Legacy aliases read on load:** `sensitivity`, `heightBoost`, `kickDrop`, `smoothing`, `wingMotionSpeed`, `wingRelease`.

## 7.3 Style presets (`SPECTRUM_PRESET_OPTIONS`)

| Key | Label (approx) |
|-----|----------------|
| `straight-bars` | Straight bars |
| `flying-glow` | Flying glow |
| `orbital-bars` | Orbital bars |
| `dot-matrix` | Dot matrix |
| `wave-ribbon` | Wave ribbon |
| `liquid-mass` | Liquid mass |
| `halo-stack` | Halo stack |

**Apply preset:** replaces `style` + full `layers[]` recipe locally (no disk save until Save).

## 7.4 Spectrum layers

Each `layers[i]` record:

| Field | UI control |
|-------|------------|
| `id`, `name` | Layer selector |
| `enabled` | Toggle (disabled layers excluded from preview) |
| `gravity` | bottom / top / left / right |
| `blend_mode` | normal / add / screen |
| `curved`, `mirrored`, `fillCircle`, `solidBand` | Toggles |
| `barWidth`, `thickness`, `radiusOffset`, `opacity`, `glow`, `blur` | Sliders |
| `color` | Solid or gradient (`spectrumColorEngine`) |

**Layer ops:** Add (from basis), Duplicate, Delete (minimum 2 layers), select by index.

## 7.5 Audio reactivity controls

Inspector dials (UI 0–20 mapped to internal ranges):

- **Primary:** Input Gain, Kick Impact, Bass Emphasis
- **Advanced:** Band Contrast, Transient Focus, Treble Shimmer, Peak Hold Blend, Motion Smoothing
- **Flying Glow only:** Wing Speed, Wing Release

## 7.6 Position & attachment

- **Anchor + X/Y sliders** ±1000; Reset Center
- **Canvas drag** (spectrum tab only): pointer drag on preview updates anchor, x, y, attach flag live
- **Attach to logo:** when enabled + logo enabled, gap controlled from Logo tab; layer `radiusOffset` becomes logo-relative

**Recommended gap formula:**
```python
base = 18 if shape == "circle" else 28
bias = size_step * (1.6 if circle else 2.6)
gap = base + bias
```

## 7.7 GPU preview contract

Preview reads `pick_preview_gpu_runtime_draft().spectrum`:

- All audio tuning + `spectrumEnabled`
- Logo attachment fields when coupled
- Processed layer list → WebGPU instance buffer / Python GPU equivalent

**Python note:** Plan for Qt Quick / OpenGL / Vulkan / WGPU renderer implementing `spectrumGpuContract` parity — separate sub-phase.

## 7.8 Spectrum effect packs

- Template ref: `effectPacks.spectrum: { packId, version } | null`
- Manifest `payload.templatePatch` may include: `style`, `layers`, `audioSettings`, `position`, `previewBindings`, `spectrumEnabled`
- **Apply:** merge into local draft + replace `layers[]`
- **Clear:** restore spectrum from **saved** template snapshot (not just null ref)

---

# 8. Domain: Background

## 8.1 Settings (`backgroundSettings.*`)

| Draft field | Template key | Notes |
|-------------|--------------|-------|
| `background_enabled` | `enabled` | |
| `background_fit_mode` | `fitMode` | `cover` \| `contain` \| `original` |
| `background_user_scale` | `userScale` | 0.1–4 |
| `background_brightness` | `brightness` | |
| `background_reactivity` | `reactivity` | 0–20 |
| `background_smoothing` | `smoothing` | |
| `background_motion_mode` | `motionMode` | none / zoom / vibrate / both |
| `background_motion_zoom_strength` | `motionZoomStrength` | |
| `background_motion_vibrate_strength` | `motionVibrateStrength` | |
| `background_motion_speed` | `motionSpeed` | |

**Transform reset:** sets `userScale = 1` only (`userOffsetX/Y` exist in schema but no UI today).

## 8.2 Atmosphere (bundled in background slice)

Under `template.effects`:

| Effect | Fields |
|--------|--------|
| **Vignette** | enabled, strength, feather, opacity, color |
| **Smoke** | enabled, strength, blur, noise, speed, opacity, color |

Inspector section: **Corner Effects**.

## 8.3 Manual vs pipeline

- **Manual:** file picker → update draft + persist `background_path` + PATCH settings `videoRenderBackgroundPath`
- **Pipeline:** preview/export uses branch-specific generated background from progress row

## 8.4 Background effect packs

Patch schema: `{ backgroundSettings, effects: { vignette, smoke } }`  
Apply merges background+atmosphere only.

---

# 9. Domain: Logo

## 9.1 Settings (`logoSettings.*`)

| Draft field | Template key | Notes |
|-------------|--------------|-------|
| `logo_enabled` | `enabled` | |
| `logo_spin_enabled` | `spinEnabled` | |
| `logo_spin_direction` | spin dir | `cw` / `ccw` |
| `logo_spin_speed` | speed | 0–720 deg/s |
| `logo_path` | workspace + `logoPath` / `previewLogo` on save | |
| `logo_shape` | `circleMask` | circle → true, square → false |
| `logo_size_step` | UI 1–10 → `size = step * 100` px | |
| `logo_opacity`, reactivity, smoothing | respective keys | |
| Motion fields | same pattern as background | zoom/vibrate |

## 9.2 Logo ↔ spectrum coupling

Logo tab controls:

- Toggle **Attach spectrum to logo** (`spectrumAttachToLogo`)
- Slider **Spectrum outer gap** 0–96px (0.5 step)
- Shape/size changes recalculate recommended gap when attach is on

## 9.3 Logo effect packs

Patch: `{ logoSettings, logoPath?, previewLogo? }` — merge logo slice only.

---

# 10. Domain: Particles

## 10.1 Settings (`particlesSettings.*`)

24+ fields including:

| Category | Examples |
|----------|----------|
| Count / size | particle count, min/max size |
| Motion | drift, orbit, turbulence |
| Appearance | variant (classic/bokeh/soap/dust), style (dot/glow/ring/spark/bokeh) |
| Spawn | area, mode, trigger (kick/bass/both) |
| Audio | motion mode, reactivity, smoothing |

## 10.2 Motion presets (inspector buttons)

`embers`, `dust_field`, `dreamy_bokeh`, `soap_orbit`, `energy_sparks`, `flash_sparks` — each applies full preset patch object.

## 10.3 Particles effect packs

Patch: `{ particlesSettings: {...} }` — replaces particles slice.

## 10.4 GPU

`particleGpuRuntime` drives instanced particles from audio envelope — parity required for preview/export.

---

# 11. Domain: Text overlays

## 11.1 Overlay model (`TemplateTextOverlayDraft`)

| Field | Template key |
|-------|--------------|
| `enabled` | `enabled` |
| `text` | `text` |
| `start_sec`, `duration_sec` | timing |
| `anchor` | e.g. `center`, `top-center`, `bottom-left` |
| `x`, `y` | position offset |
| `font_size` | saved as `sizePx` |
| `color`, `stroke_color`, `stroke_width`, `shadow` | styling |
| `animation` | `fade`, `pop`, `slide_right`, etc. |

Default overlay: disabled, empty, 3s, center, 46px, white + black stroke.

## 11.2 User flows

**Stage list:** Add, preset, Duplicate, Delete, Up/Down reorder, select → switches right rail to Text tab.

**Style presets:** `neon_brush_stack` (3 layers), `neon_outline`, `soft_glow`, `dark_stroke`.

**Right rail modes:** Basic (text, timing, position), Style (font, colors, stroke), Effects (animation, shadow) + case transforms + anchor alignment.

## 11.3 Selection

`selected_text_overlay_key` (string index) → preview highlights active layer.

---

# 12. Preview & audio pipeline

## 12.1 Component responsibilities

| Layer | Responsibility |
|-------|----------------|
| `PreviewProvider` | MP3 load, audio analysis cache, transport sync |
| `RendererVideoPreviewSurface` | GPU canvas + DOM/Qt overlays + spectrum drag |
| Domain runtimes | spectrum, particles, atmosphere, background, logo presentation |

## 12.2 Audio analysis

MP3 → analysis frames:

- `bassFast`, `bassSlow`, `kick`, `drop`, `level`, frequency bins
- Per-style smoothing profiles (attack/release, curve, accent strength)
- Drives spectrum bar heights, background/logo/particle reactivity

**Cache:** `get/set_audio_analysis_cache` — Python must persist analysis keyed by file hash + settings.

## 12.3 Preview inputs

- `template` (persisted) + `template_draft` (live, immediate reactivity)
- `background_path`, `logo_path`, `selected_mp3_path`
- `preview_volume`: **1.35** (fixed in Electron stage)
- `playback_command` nonce from transport controls

## 12.4 Recovery

- `preview_runtime_nonce` — force remount after WebGPU/device loss
- Diagnostics panel surfaces lifecycle: loading, ready, error, device loss

---

# 13. Export & commands

## 13.1 Save template

Requires non-empty name. Calls `patch_template` with full save patch.

## 13.2 Manual export

Builds `ManualRenderSceneRequest` from live draft:

- `draft_source: 'live'`
- Includes current layers, domains, asset paths
- Starts export job → poll `export` state

## 13.3 Pipeline export

Requires `resolved_pipeline_inputs.ready`:

```
start_pipeline_export(
  run_dir, background_path, branch, batch_id, role
)
```

Uses **saved template** from workspace (not live unsaved draft unless user saved first).

## 13.4 Export UI

Progress %, ETA, completed/total, open output folder, stop export.

MP3 list, pipeline run selector, branch toggle (Long 16:9 / Reel 9:16).

## 13.5 Shell companions (not in page view)

| Component | Role |
|-----------|------|
| `DesktopVideoPipelineCoordinator` | Background pipeline export sync |
| `ShellVideoWorkspaceSync` | Cross-page workspace events |
| `VideoExportHostPage` | Headless export renderer route |

Python: implement coordinators at app shell level like Music download coordinator.

---

# 14. Effect pack system (detailed)

## 14.1 Manifest contract (v1)

**Domains:** `spectrum`, `background`, `logo`, `particles`  
**Domain contract versions:** all `1` today

**Required manifest fields:**

| Field | Rule |
|-------|------|
| `manifestVersion` | `1` |
| `packId` | slug `[a-z0-9][a-z0-9._-]*` |
| `name`, `vendor`, `version` | display + semver string |
| `domain` | one of four domains |
| `domainContractVersion` | must match app expectation |
| `appVersionRange` | semver range, default `*` |
| `payload.templatePatch` | domain-specific strict schema |
| `preview` | optional title, summary, accentColor (for marketplace cards) |

## 14.2 Local registry (Electron parity)

```
{AppData}/effect-packs/
  registry.json
  packs/{packId}/{version}/manifest.json + assets
```

**Registry record per packId:**

- `enabled: bool`
- `activeVersion: str`
- `previousVersion: str | null`
- `versions: { [version]: { path, installedAt, source } }`

## 14.3 Catalog operations (implement as `EffectPackService`)

| Operation | Electron IPC | Python method |
|-----------|--------------|---------------|
| List catalog | `effect-packs:list-catalog` | `list_catalog()` |
| Install ZIP | `effect-packs:install-from-file` | `install_from_file(path)` |
| Install URL | `effect-packs:install-from-url` | `install_from_url(url)` (future marketplace) |
| Set enabled | `effect-packs:set-enabled` | `set_enabled(pack_id, enabled)` |
| Activate version | `effect-packs:activate-version` | `activate_version(pack_id, version)` |
| Remove version | `effect-packs:remove-version` | `remove_version(pack_id, version)` |

## 14.4 Catalog item status

`ready` | `available` | `disabled` | `incompatible` | `broken` | `missing`

Selection UI shows human-readable status via `resolve_effect_pack_selection_status`.

## 14.5 Workspace apply flow

1. User selects pack `packId::version` from dropdown
2. `build_template_effect_pack_apply_patch` merges domain patch into **local draft**
3. Preview updates immediately
4. User clicks **Save** → `effectPacks.{domain}` ref persisted in template JSON

**Clear behavior:**

- Spectrum: restore saved template spectrum state
- Other domains: null ref only

## 14.6 UI requirement (Electron gap to fix in Python)

Electron has `EffectPackSelectorCard` fully built but **not mounted** in inspectors (props prefixed `_` in shell). **Python should wire effect pack selector into each domain inspector from day one.**

Card actions: Select, status badge, Install ZIP, Reload, Clear, Enable/Disable, Activate, Remove.

## 14.7 Future marketplace mapping

| Future capability | Hook in this architecture |
|-------------------|---------------------------|
| Admin uploads ZIP to portal | Portal stores artifact URL + manifest metadata |
| Marketplace lists packs | `RemoteMarketplaceCatalogProvider.list()` merges with local registry |
| User purchase | entitlement record → `install_from_url` or signed download |
| Install | reuses existing install pipeline + validation |
| Appears in Video dropdown | same `list_catalog()` merge: local + entitled remote |
| Update pack version | new version install + optional template migration job |
| Vendor metadata | manifest `vendor`, `tags`, `preview` for store cards |

**Do not implement marketplace in Phase 9.** Do implement interfaces so adding `RemoteMarketplaceCatalogProvider` does not require rewriting Video UI.

---

# 15. Python module architecture (planned)

```
camxora_python/features/video/
  views/video_view.py              # Shell entry, no page header
  views/video_workspace_shell.py   # 3-column layout
  widgets/                         # Rails, stage, inspectors (standard Qt)
  lib/
    template_draft.py              # build_template_draft, domain slices
    template_save.py               # save patch builder
    draft_store.py                 # local snapshot persistence
    pipeline_inputs.py             # port videoPipelineInputs.ts
    domains/
      spectrum/ background/ logo/ particles/ text/ atmosphere/
  services/
    video_workspace_service.py     # template CRUD, workspace state
    video_export_service.py        # manual + pipeline export jobs
    effect_pack_service.py         # registry + catalog provider interface
    preview/
      preview_provider.py          # audio + transport
      gpu/                         # renderer implementations (sub-phase)
  workers/
    video_workspace_worker.py
    export_worker.py
```

**Cross-cutting:**

- `shared/models/video.py` — DTOs matching Electron types
- Shell coordinators in `app/` mirroring Electron

---

# 16. UI mapping (PySide6)

| Electron | Python |
|----------|--------|
| `CompactTabs` | `QTabBar` / checkable `QPushButton` row in `account_card` |
| Inspector sliders | `QSlider` + value label |
| Template dropdown | `QComboBox` |
| Preview canvas | `QOpenGLWidget` + ModernGL (`visualizer/preview_widget.py`, ported from python_app) |
| Export queue | `account_card` + progress bar + `QTableWidget` or list |
| Diagnostics | collapsible `QGroupBox` |

**No custom design system beyond deep_blue QSS.**

---

# 17. Electron reference files

| Area | Path |
|------|------|
| Page entry | `features/video/VideoWorkspacePage.tsx` |
| Coordinator | `features/video/workspace/useVideoWorkspaceCoordinator.ts` |
| Shell | `features/video/workspace/VideoWorkspaceShell.tsx` |
| Draft | `features/video/workspace/useVideoWorkspaceDraft.ts` |
| Domains | `features/video/domains/**` |
| Effect packs | `src/shared/effectPacks/effectPackContracts.ts` |
| Registry | `src/main/effectPackRegistry.ts` |
| Pipeline | `shared/lib/videoPipelineInputs.ts` |
| Preview | `features/video/RendererVideoPreview.tsx` |
| Export | `features/video/workspace/ExportQueuePanel.tsx` |

---

# 18. Phased implementation plan (recommended)

| Sub-phase | Scope | Marketplace relevance |
|-----------|-------|----------------------|
| **9a** | Shell route, 3-column layout, workspace state load, template CRUD, draft store, Save | — |
| **9b** | Domain inspectors (scalar settings only), no GPU preview | — |
| **9c** | Effect pack service + registry + inspector selectors | **Core extensibility** |
| **9d** | GPU preview (spectrum first) | Pack preview value |
| **9e** | Background, logo, particles, text preview layers | |
| **9f** | Manual export | |
| **9g** | Pipeline export + shell coordinator | |
| **9h** | Diagnostics, recovery, performance | |
| **Future N** | Marketplace catalog provider + entitlements | Plugs into 9c service |

---

# 19. Definition of Done (Phase 9 — when implemented)

- [ ] `/app/video` renders full workspace; shell hides page header
- [ ] Template list, switch, save, delete match Electron flows
- [ ] Local draft persistence + dirty badges per domain
- [ ] All four left-rail inspectors functional with field parity
- [ ] Text layer list + right-rail inspector + presets
- [ ] Live GPU preview with audio reactivity (spectrum minimum)
- [ ] Background/logo/particles/text visible in preview
- [ ] Spectrum layers editor (add/duplicate/delete/sliders)
- [ ] Spectrum canvas position drag on spectrum tab
- [ ] Effect pack install (ZIP), catalog list, apply, clear, enable, activate, remove
- [ ] Effect pack selector visible in **each** domain inspector
- [ ] Manual export produces video from live draft
- [ ] Pipeline export from progress row + branch
- [ ] Export progress polling + stop + open folder
- [ ] Template JSON byte-compatible with Electron templates
- [ ] Effect pack manifest validation matches `effectPackContracts`
- [ ] `EffectPackCatalogProvider` interface documented for marketplace
- [ ] Tests for draft builders, pipeline inputs, pack merge, save patch

---

# 20. Open questions / decisions before build

| # | Question | Status / decision |
|---|----------|-------------------|
| Q-1 | GPU backend for Python preview? | **Resolved:** ModernGL via ported `python_app/visualizer/` (preview + export share `gpu_render.py`) |
| Q-2 | Template storage path parity? | Mirror Electron `{userData}/video/` layout exactly |
| Q-3 | Headless export host? | **Resolved:** Subprocess CLI (`visualizer/main.py`) + `ExportGate`; optional hidden window only if needed for GL init |
| Q-4 | Wire Electron's unmounted effect pack UI? | Yes — treat as bug fix baseline for Python |
| Q-5 | Marketplace API shape? | Defer; use `Protocol` for catalog provider now |
| Q-6 | Electron vs python_app schema? | **Resolved:** Electron canonical on disk; `TemplateNormalizer` at renderer boundary |

---

# 21. Related documents

- **[`09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md`](09_VIDEO_ELECTRON_PYTHON_APP_INTEGRATION.md)** — Electron ↔ python_app ↔ camxora_python architecture (required reading for Phase 9)
- **[`09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md`](09_VIDEO_DOMAIN_SCHEMA_APPENDIX.md)** — field-by-field domain schema + golden fixture index
- **[`09_VIDEO_ENTERPRISE_ARCHITECTURE.md`](09_VIDEO_ENTERPRISE_ARCHITECTURE.md)** — enterprise pillars, boundaries, reliability, security, quality gates
- [`00_PAGE_BY_PAGE_STRATEGY.md`](00_PAGE_BY_PAGE_STRATEGY.md)
- [`07_MUSIC_REQUIREMENTS.md`](07_MUSIC_REQUIREMENTS.md) — workspace page pattern reference
- [`08_IMAGE_REQUIREMENTS.md`](08_IMAGE_REQUIREMENTS.md)
- Electron: `camxora/docs/video-preview-gpu-reactivity-parity-plan.md`
- python_app: `visualizer/gpu_render.py`, `visualizer/contracts.py`, `features/video_export/export_gate.py`
