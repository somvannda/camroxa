# 7. Vizzy

> **Feature prefix:** `VZ-`
> **Route:** `/app/vizzy`
> **Phase:** P7
> **Sources of truth:**
> - `G:\Developments\Rea\editor` (the Rea editor)
> - `G:\Developments\Rea\docs\UI-PARITY.md`
> - `G:\Developments\Rea\docs\vizzy-ui-spec.md`
> - `G:\Developments\Rea\docs\TIMELINE-ROADMAP.md`
> - `G:\Developments\Rea\docs\PANELS-AUDIT.md`
> - `G:\Developments\Rea\docs\requirements-status.md`

---

## 1. Purpose

Ship the full Vizzy-style composition editor inside Camxora as the **Vizzy** page. The
editor is the existing Rea implementation; we host it, bridge native services, and keep its
behaviour. We do **not** rewrite the renderer, the node graph, the shaders or the timeline.

**Port source:** `G:\Developments\Rea\editor` (our readable TypeScript implementation).
We do **not** copy Vizzy's shipped minified bundle, source maps, shaders or artwork. The Rea
editor is the behavioural clone; it is the thing we port.

**2.0.0 scope:** the editor, project I/O, media, manual image/video export, **pipeline
template authoring** and the **Renders** panel. The pipeline is live: Auto-Video/Merge/Reel/
Upload are part of 2.0.0.

**What replaces what:**

| 1.7.1 surface | 2.0.0 |
|---|---|
| Video page — preview/editing/template picking | **Replaced by Vizzy** |
| Video page — automatic per-run render, merge, reel, upload | **Vizzy pipeline** |
| Video/Reel templates | **Vizzy pipeline templates** (`template.json` + `pipeline.json`) |
| Manual video export | **Vizzy native export** |
| Export queue | **Vizzy Renders panel + Progress** |

**Port order:** host the whole editor first (open/save/media/export), then customise
(branding, marketplace templates, Camxora project library, native export). See
[`../vizzy/04-CUSTOMIZATION.md`](../vizzy/04-CUSTOMIZATION.md).

---

## 2. Hosting model

| Decision | Value |
|---|---|
| Runtime | The Rea editor built as its own Vite bundle |
| Container | A dedicated `WebContentsView` inside the Vizzy route |
| Isolation | Separate process; a crash reloads the view, not the shell |
| Host protocol | `postMessage` bridge + main-process IPC for files/export |
| Cross-origin isolation | COOP/COEP headers from the custom protocol or a tokenised loopback server |
| Theme | Rea CSS untouched; a scoped override stylesheet applies Camxora tokens |
| Data | Native project files + recent-projects SQLite; `localStorage` remains a cache |

---

## 3. Layout (reference)

```
┌──────────────────────────────────────────────────────────────────────┐
│ VIZZY  File  Edit  Project  View  Help   Release  Account  Export    │
├───────────────┬──────────────────────────────┬───────────────────────┤
│ Left panel    │ Canvas panel                 │ Inspector             │
│ Composition   │ Preview                      │ Objects / <name>      │
│ Analyzers     │ 360 480 720 1080  Bounce     │ Preset                │
│ Effects       │                              │ Sections …            │
│ Automations   │                              │                       │
│ Media         │                              │                       │
│ Projects      │                              │                       │
│ Lyrics        │                              │                       │
├───────────────┴──────────────────────────────┴───────────────────────┤
│ Timeline: undo/redo · zoom · loop · audio · time · transport · tracks │
└──────────────────────────────────────────────────────────────────────┘
```

The editor is a resizable four-pane layout. The shell collapses its sidebar and hides its
page header while Vizzy is active. The shell strip above the view carries the project state,
a **Renders** toggle (pipeline queue), and Close.

---

## 4. Feature inventory

The complete, ID-level inventory is in
[`../vizzy/01-FEATURE-INVENTORY.md`](../vizzy/01-FEATURE-INVENTORY.md). The summary:

### 4.1 Editor shell and menus

| ID | Feature | Pri |
|---|---|---|
| VZ-01 | Top bar: brand, File/Edit/Project/View/Help, release chip, project name, save state, warnings, account, Export | P0 |
| VZ-02 | File: Export, New Project, Save, Save As New, Close Editor | P0 |
| VZ-03 | Edit: Cut/Copy/Paste (disabled states match reference) | P0 |
| VZ-04 | Project: explore creations, rename, thumbnail, creator note, custom resolution, background, organise tracks, save preview as image | P0 |
| VZ-05 | View: command palette, change layout, window dragging, theme | P0 |
| VZ-06 | Help: project info, system info, Discord, FAQ, intro tutorial, export project JSON, export log, changelog | P1 |
| VZ-07 | Command palette: 37 commands, grouped, keyboard-first | P0 |
| VZ-08 | Editor warnings: import skips, approximations, failed media fetches | P0 |
| VZ-09 | Status bar: one-line message strip | P0 |
| VZ-10 | Changelog modal | P1 |

### 4.2 Composition tree

| ID | Feature | Pri |
|---|---|---|
| VZ-11 | Layers and items, top-first tree, type chips, indentation | P0 |
| VZ-12 | Add layer, add item, add effect, rename, delete, reorder | P0 |
| VZ-13 | Visibility, shy, render-to-buffer, audio, clear | P0 |
| VZ-14 | Multi-select, drag items between layers, drag to analyzer | P0 |
| VZ-15 | Context menus: add, rename, delete, move to layer, reorder | P0 |
| VZ-16 | Layer headers in the timeline mirror the tree | P0 |

### 4.3 Nodes and items

28 node kinds: layer, media, particles, spectrum, primitives (cube/square/plane), point
light, progress bar, logo, ground, noise, Skia text, animated text, lyrics, audio wave,
basic spectrum bars, particle lines, 3D model, line bed, spherical field, instanced particle
system, particle system, confetti, shader item, Skottie/Lottie, video, WASM video, video 2,
Butterchurn, particle timeline.

| ID | Feature | Pri |
|---|---|---|
| VZ-17 | Create every node kind from the left rail / add dialog | P0 |
| VZ-18 | Per-node controllers via `createControllerSetups` | P0 |
| VZ-19 | Per-node defaults, limits and tooltips | P0 |
| VZ-20 | Media/video/audio/text/lyrics/shader/particle special cases | P0 |
| VZ-21 | 3D scene nodes (primitives, ground, point light, model, spherical field) | P0 |
| VZ-22 | Butterchurn / audio-visualizer node | P1 |
| VZ-23 | Skottie/Lottie playback | P1 |

### 4.4 Inspector

| ID | Feature | Pri |
|---|---|---|
| VZ-24 | `Objects / <name>` title, selection, delete | P0 |
| VZ-25 | Collapsible sections in reference order | P0 |
| VZ-26 | Controls: select, slider, range, boolean, text, color, file, image grid, analyzer, custom path | P0 |
| VZ-27 | Keyframe add/remove/navigate per animatable property | P0 |
| VZ-28 | Constraints, disabled rows, tooltips | P0 |
| VZ-29 | Composition properties when nothing is selected | P0 |
| VZ-30 | Rename object/layer/effect/analyzer/automation | P0 |

### 4.5 Analyzers

| ID | Feature | Pri |
|---|---|---|
| VZ-31 | Create/rename/delete; default analyzer cannot be deleted | P0 |
| VZ-32 | 21 controllers in reference order (provider, multiplier, count, duration, offset, alignment, range, smoothing, window, parameter, skew, CQT, tilt, weighting, scale, factor, downsample) | P0 |
| VZ-33 | Bind items/automations; connection list; "not being used" state | P0 |
| VZ-34 | WASM analyser + JS fallback with parity | P0 |
| VZ-35 | Frequency scales: linear, log, mel, critical bands, ERB, sinh, nth root | P0 |
| VZ-36 | Weighting A/B/C/D/M; per-band tilt; per-bin tilt | P0 |
| VZ-37 | 64-analyzer batch cap, fixed 131,072-sample window | P0 |

### 4.6 Effects

| ID | Feature | Pri |
|---|---|---|
| VZ-38 | Effect catalog (~40 effects: color tint, invert, pixelate, chromatic aberration, box blur, render, two-pass blur, blur triangle, VHS, time stop, CAS, liquify, gradient map, chroma shift, premultiply alpha, distance field, advanced outline/shadow, glitch, VHS2, outline, drop shadow, streak glow, morphing fractal, displacement, image mask, spooky, impact ripple, render layer, repeating ripple, RGB displace, scale, channel blur, god rays, chroma key, edge detection, FXAA, glow, bloom, alpha, …) | P0 |
| VZ-39 | Add effect to layer/item; enable/disable; remove; back | P0 |
| VZ-40 | Per-effect parameters and shader controls | P0 |
| VZ-41 | Effect reorder, rename, context menu | P0 |
| VZ-42 | Layer-scoped vs item-scoped effects | P0 |
| VZ-43 | SkSL/shader source editing where the reference exposes it | P1 |
| VZ-44 | Effect preview/thumbnail | P1 |

### 4.7 Automations

| ID | Feature | Pri |
|---|---|---|
| VZ-45 | Keyframes: linear/eased/hold | P0 |
| VZ-46 | Math: formula `t, p, a, m, d, u1–u5, g1–g5, rx, ry` | P0 |
| VZ-47 | Audio impact: min/max/sensitivity/smoothing/floor/ceiling/cumulative/delta | P0 |
| VZ-48 | Color automation variant | P0 |
| VZ-49 | Groups/folders: add, rename, remove, toggle, drag | P0 |
| VZ-50 | Connections: property, effect params, other automations | P0 |
| VZ-51 | Comparator + threshold | P0 |
| VZ-52 | Enable/disable, delete, undo | P0 |

### 4.8 Presets and templates

| ID | Feature | Pri |
|---|---|---|
| VZ-53 | Built-in presets (5) + catalogue + community + user | P0 |
| VZ-54 | Apply preset as one undo step | P0 |
| VZ-55 | Save current spectrum as preset; overwrite; edit image; delete | P0 |
| VZ-56 | Import/export preset JSON | P0 |
| VZ-57 | Preset context menus and order | P0 |
| VZ-58 | Templates modal/panel; apply; import | P0 |
| VZ-59 | Marketplace-installed templates appear without restart | P1 |

### 4.9 Media and projects

| ID | Feature | Pri |
|---|---|---|
| VZ-60 | Upload/drag images, video, audio; asset store; cache by id | P0 |
| VZ-61 | Project new/open/save/save as/close/recent | P0 |
| VZ-62 | Import Vizzy project export JSON; map nodes, transforms, spectrum, shaders, lyrics, media | P0 |
| VZ-63 | Export project JSON | P0 |
| VZ-64 | Project thumbnail, creator note, description | P0 |
| VZ-65 | Projects panel: list/search/open/delete | P0 |
| VZ-66 | Autosave/recovery | P0 |

### 4.10 Lyrics

| ID | Feature | Pri |
|---|---|---|
| VZ-67 | Import lyrics (text, LRC, items) | P0 |
| VZ-68 | Split/join lines, timing, preview | P0 |
| VZ-69 | Lyrics renderer (shader/canvas) | P0 |
| VZ-70 | Export lyrics | P1 |

### 4.11 Timeline

| ID | Feature | Pri |
|---|---|---|
| VZ-71 | Zoom, pan, fit, frame selection, follow playhead | P0 |
| VZ-72 | Ruler, playhead, timecode, seconds/frames | P0 |
| VZ-73 | Loop region (shift-drag, edges, clear) | P0 |
| VZ-74 | Beats/tempo grid | P0 |
| VZ-75 | Audio waveform band + track name + choose audio | P0 |
| VZ-76 | Layers first, clips, trim grips, move/resize, multi-select, group drag | P0 |
| VZ-77 | Snapping to playhead/ends/markers/loop/beats/edges | P0 |
| VZ-78 | Markers add/rename/delete/drag | P0 |
| VZ-79 | Tools: select, hand, razor, slip; split, ripple delete | P0 |
| VZ-80 | Keyframe lane, marquee, 2D drag | P0 |
| VZ-81 | Source in/out for video | P1 |
| VZ-82 | Clip comments | P1 |
| VZ-83 | Accessibility: hidden clip list, focus, arrows, Home/End, reduced motion | P0 |
| VZ-84 | Performance: cached static frame, playhead-only redraw | P0 |

### 4.12 Stage, audio, render and export

| ID | Feature | Pri |
|---|---|---|
| VZ-85 | Stage 360/480/720/1080, bounce, open external | P0 |
| VZ-86 | Drag/drop onto canvas | P0 |
| VZ-87 | Audio settings: volume, mute, bass boost/frequency, rate, compressor, attenuator, gain | P0 |
| VZ-88 | Offline audio processing feeding the analyser | P0 |
| VZ-89 | Render settings: resolution, fps, tempo, duration, background, globals g1–g5, spectrum color | P0 |
| VZ-90 | Export image (current frame) | P0 |
| VZ-91 | Export video H.264/AAC MP4, VP9/Opus WebM, VP8/Vorbis WebM | P0 |
| VZ-92 | Export progress, cancel, error, output path | P0 |
| VZ-93 | WebCodecs export path | P1 |
| VZ-94 | Native FFmpeg export bridge | P0 (release path) |
| VZ-95 | Export with audio muxed at the project duration | P0 |
| VZ-96 | Export resolution independent of preview | P0 |

### 4.13 Project info and diagnostics

| ID | Feature | Pri |
|---|---|---|
| VZ-97 | Project information dialog | P1 |
| VZ-98 | System information dialog | P1 |
| VZ-99 | Export current/last log | P1 |
| VZ-100 | Intro tutorial / FAQ content | P2 |
| VZ-101 | Pipeline binding inspector (audio/background/logo/title/artist/album/palette) | P0 |
| VZ-102 | Save/validate a pipeline template (`template.json` + `pipeline.json`) | P0 |
| VZ-103 | Renders panel: queue, progress, cancel, retry, open output | P0 |
| VZ-104 | Pipeline template validation detail (missing binding / unsupported feature) | P0 |
| VZ-105 | "Render this project" from the editor | P0 |
| VZ-106 | Pipeline template picker for profile assignment | P0 |
| VZ-107 | Template library: create/duplicate/rename/delete/import/export | P0 |
| VZ-108 | Default template per profile/kind | P0 |
| VZ-109 | Template protection/lock and thumbnail/version | P1 |
| VZ-110 | Vizzy content parity report: every built-in preset/catalogue/template enumerated and verified | P0 |
| VZ-111 | All 91 templates available and validated (open/preview/save/export) | P0 |
| VZ-112 | 91-template delivery pack + licensing record | P0 |
| VZ-113 | **Save as video template** captures the current preview exactly | P0 |

### 4.14 Vizzy content parity

Everything already in Vizzy must work as-is. This is a release gate, not a cleanup item.

| Content | Count | Required |
|---|---|---|
| Built-in spectrum presets | 5 | Apply, render, save, reload |
| Spectrum catalogue | 32 | Load, apply, render, thumbnails |
| Particle presets | 18 | Apply, movement/reaction distinct, Default restores |
| Butterchurn presets | 6 | Load, render |
| Community presets | empty array | Loads safely |
| User presets | user-defined | Create/save/update/delete/import/export |
| Templates modal/panel | shipped set | List, apply, import/export |
| Preset thumbnails/images | shipped set | Resolve; no broken images |
| Node kinds/effects used by presets | all | Render without console errors |
| Template library | **91** (90 + Moai Money) | All available; open, preview, save, reopen, export |
| Template delivery | first-run pack or bundle | All 91 available; licensing recorded |

**Old Camxora video templates are not migrated in 2.0.0.** They are not selectable and are
not converted; users who need them stay on 1.7.x or re-author in Vizzy later.

---

## 5. Acceptance

| ID | Scenario | Assert |
|---|---|---|
| VZ-T1 | Open a reference project | Layers, items, effects, analyzers, automations and media resolve |
| VZ-T2 | Edit and save | Reopen produces the same composition |
| VZ-T3 | Apply preset | One undo step; visuals match the preset snapshot |
| VZ-T4 | Add effect | Effect renders; parameters persist |
| VZ-T5 | Audio impact | A loud frame moves the bound property; a silent frame does not |
| VZ-T6 | Timeline | Move/trim/split/ripple; undo restores |
| VZ-T7 | Export image | PNG at the requested resolution |
| VZ-T8 | Export video | Playable MP4 with audio; duration and fps correct |
| VZ-T9 | Crash isolation | Killing the Vizzy view leaves the shell alive and offers reload |
| VZ-T10 | 10-project round-trip | All ten open, save, reopen and export |
| VZ-T11 | Responsive | Usable at 1280×800; stage scales |
| VZ-T12 | Accessibility | Keyboard focus and clip navigation work |
| VZ-T13 | Pipeline template | Save a template, bind a run, render it from the Renders panel |
| VZ-T14 | Renders panel | Queue/progress/cancel/retry/open output work |
| VZ-T15 | Content parity | 5 built-in presets, 32 catalogue presets, 18 particle presets, 6 Butterchurn presets and the template panel all apply/render/save |
| VZ-T16 | Template library | Create/duplicate/rename/delete/import/export/protect round-trip |
| VZ-T17 | 91-template library | Every template opens, previews, saves, reopens and exports |
| VZ-T18 | Preview → template → pipeline | Saving the preview as a video template and rendering it matches the preview |

---

## 6. Dependencies

- Rea source and build pipeline.
- COOP/COEP hosting spike.
- Native file dialogs, media protocol, project store.
- FFmpeg native export bridge.
- Marketplace template store (P6).
- Pipeline service: [`../09-PIPELINE-AUTOMATION.md`](../09-PIPELINE-AUTOMATION.md).
- Camxora design tokens for the scoped override theme.

---

## 7. Definition of Done

- [ ] VZ-01 … VZ-113 implemented or explicitly deferred; all `P0` verified.
- [ ] Full editor runs in the hosted view with no regression against the Rea baseline.
- [ ] All 91 templates are available, round-trip and export.
- [ ] Every built-in preset/catalogue/particle/Butterchurn/template works as-is.
- [ ] Any of the 91 can be saved as a video template and rendered by the pipeline.
- [ ] Old Camxora video templates are not offered.
- [ ] A Vizzy crash cannot take down the shell.
- [ ] Native export produces a valid file with audio.
- [ ] VZ-T1 … VZ-T18 pass.
- [ ] Design review approves the scoped theme.
