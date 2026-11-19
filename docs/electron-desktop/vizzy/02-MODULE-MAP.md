# Vizzy — Module Map and Integration

> **Document ID:** CAMXORA-ED-VZ-02
> **Version:** 1.0.0
> **Status:** Draft
> **Source:** `G:\Developments\Rea\editor` (Rea)
> **Last updated:** 2026-11-19

This document maps the Rea editor into the Electron app and states what is reused, adapted
or replaced. The goal is **zero renderer rewrites** in the first port.

---

## 1. Source strategy

Rea lives outside the Camxora repository. For the first port we **vendor the source**:

```
desktop-electron/
  vizzy/
    UPSTREAM.md          # source path, commit/date, sync instructions
    src/                 # copied from Rea editor/src
    public/              # pruned assets
    index.html
    vite.config.ts
    package.json         # Rea dependencies, pinned
    scripts/             # Rea verification scripts we keep
```

A sync script (`scripts/sync-vizzy.mjs`) copies the Rea tree, applies the small patch set
below, and writes a hash into `UPSTREAM.md`. The patch set is kept as explicit files under
`vizzy/patches/` so a future Rea update is a rebase, not a mystery.

**Why vendor instead of submodule?** Rea has no configured remote and lives in a separate
folder. Vendoring makes the Electron build reproducible and lets us review every change. A
submodule can replace it later if Rea gets a stable remote.

### 1.1 What is reused vs what is new

| Area | Action | Rewrite? |
|---|---|---|
| Vizzy editor core: shell, composition, nodes, inspector, effects, analyzers, automations, timeline, stage, audio, presets, templates, lyrics, import/export, 3D, particles, Butterchurn | Vendor the Rea source, build it, host it | **No** |
| Vizzy renderer (three.js/WebGL, shaders, compositing) | Reuse as-is | **No** |
| Vizzy project format and import/export mapping | Reuse as-is | **No** |
| Vizzy presets/catalogues/91 corpus | Reuse/validate; no editor rewrite | **No** |
| Electron host: window, custom protocol, COOP/COEP, `WebContentsView`, bridge, file pickers, media protocol, native export, account | New integration code | **Yes — new code, not a Vizzy rewrite** |
| Vizzy bridge adapters (`bridge.ts`, `storage.ts`, `media.ts`, `exporter-adapter.ts`, `account.ts`, `links.ts`, theme override, build config) | Small patch set | **No core rewrite** |
| Pipeline template inspector + Renders panel | New UI inside the host | **New feature, not a rewrite** |
| Pipeline automation: template contract, binding, headless render, merge/reel, upload | New Electron service | **Yes — new code, replaces the Python pipeline** |
| Old Camxora Video/Merger pages and old Camxora video templates | Not ported | **Removed** |
| Camxora desktop shell/pages (Login, Dashboard, etc.) | Rebuilt in Electron/React | **Yes — the desktop app is rewritten; Vizzy is not** |

**The one-sentence answer:** the whole Vizzy editor and renderer are ported and reused. We
write the Electron host, the bridge adapters, the pipeline service and the Camxora shell. We
do **not** rewrite Vizzy.

---

## 2. Rea module map

| Rea module | Role | Electron action |
|---|---|---|
| `src/main.ts` | App wiring, panels, menus, commands, dialogs | Reuse; add a bridge adapter and replace account/sign-in hooks |
| `src/styles.css` | Full editor CSS | Reuse; add a scoped Camxora token override after it |
| `index.html` | DOM shell | Reuse; set `base` and CSP meta for the host |
| `src/domain/types.ts` | Vocabulary, undo ops, automation shapes | Reuse unchanged |
| `src/domain/nodes.ts` | 28 node types and controllers | Reuse unchanged |
| `src/domain/effects.ts` | Effect catalog and parameters | Reuse unchanged |
| `src/domain/analyzers.ts` | Analyzer model and defaults | Reuse unchanged |
| `src/domain/presets.ts` | Presets and user preset store | Reuse; swap `localStorage` for the native store adapter |
| `src/domain/import-project.ts` | Vizzy project import | Reuse; media path resolution via bridge |
| `src/domain/project.ts` | Project model | Reuse |
| `src/domain/undo.ts` | History | Reuse |
| `src/domain/formula.ts` | Math automation evaluator | Reuse |
| `src/domain/audio-impact.ts` | Audio impact smoothing | Reuse |
| `src/domain/camera-shake.ts` | Camera shake | Reuse |
| `src/domain/blending.ts` | Blend modes | Reuse |
| `src/domain/custom-path.ts` | Custom motion paths | Reuse |
| `src/domain/spectrum-*.ts` | Spectrum catalogue, layers, paint, path, reaction, shader, canvas | Reuse |
| `src/domain/text-*.ts`, `bmfont-text.ts`, `skia-fonts.ts` | Text/CanvasKit | Reuse |
| `src/domain/lyrics.ts`, `lyrics-shader.ts` | Lyrics | Reuse |
| `src/domain/particle-presets.ts` + JSON | Particle presets | Reuse; lazy-load JSON |
| `src/domain/vizzy-butterchurn.js` | Butterchurn bundle | Reuse |
| `src/audio/fft.ts`, `cqt.ts`, `goertzel.ts`, `spectrum.ts`, `analyzer-bank.ts`, `band-*.ts`, `vizzy-analyzer.ts` | Analysis | Reuse; ensure COOP/COEP for threads |
| `src/audio/fftWorker.ts` | Worker | Reuse; verify worker loads under the custom protocol |
| `src/renderer/renderer.ts` | Stage, render loop, capture | Reuse |
| `src/renderer/post-processing.ts` | Shader passes | Reuse |
| `src/ui/timeline.ts` | Timeline canvas | Reuse |
| `src/ui/inspector.ts` | Inspector | Reuse |
| `src/ui/icons.ts` | Material icons | Reuse |
| `src/export/exporter.ts` | ffmpeg.wasm export | Reuse as fallback; add native adapter |
| `src/export/webcodecs-exporter.ts` | WebCodecs export | Reuse; keep as an option |
| `src/export/reference-encoder.ts` | Reference encoder | Reuse for parity |
| `public/*` | Assets | Prune; ship only what the editor needs |

**Not copied:** `test-*.mjs`, `verify-*.mjs`, `.shots/`, `node_modules/`, the reference
corpus, and any Vizzy-derived asset that is not licensed for redistribution.

---

## 3. Patch set (the only code changes in the first port)

### 3.1 `bridge.ts` (new)

A single adapter with a browser fallback:

```ts
export interface VizzyHost {
  pickMedia(kind: 'image'|'video'|'audio'): Promise<string | null>;
  saveProject(name: string, bytes: ArrayBuffer): Promise<{ path: string } | null>;
  openProject(): Promise<{ name: string; bytes: ArrayBuffer } | null>;
  listProjects(): Promise<ProjectSummary[]>;
  deleteProject(id: string): Promise<void>;
  exportVideo(req: ExportRequest): Promise<{ jobId: string }>;
  onExportProgress(cb: (p: ExportProgress) => void): () => void;
  log(level: string, message: string, detail?: unknown): void;
  appInfo(): Promise<{ version: string; env: string }>;
}
```

- In Electron: `window.camxoraVizzy` is injected by the view's preload.
- In a browser (dev): falls back to `localStorage`, file inputs and ffmpeg.wasm.

### 3.2 `storage.ts` (new)

Replaces direct `localStorage` project persistence:

- `loadProject`, `saveProject`, `listProjects`, `deleteProject`, `autosave`.
- Browser fallback keeps the current keys so the Rea dev flow still works.
- Native paths are handled by main; the renderer sees opaque project ids and names.

### 3.3 `media.ts` (new)

- Resolves an asset to a displayable URL:
  - native: `camxora-media://<token>`
  - browser: blob/object URL.
- `pickMedia` uses the native dialog.
- Caches object URLs and revokes them on unload.

### 3.4 `exporter-adapter.ts` (new)

- `exportVideo` chooses the native bridge when available; otherwise the existing
  `Exporter`.
- Progress/cancel are forwarded.
- The native path sends frames; the adapter decides based on `window.camxoraVizzy`.

### 3.5 `account.ts` (new)

- Replaces Vizzy account/sign-in UI with the Camxora session summary.
- Hides cloud/community features that do not exist in the desktop build.
- "Sign in" opens the Camxora account modal or does nothing when already signed in.

### 3.6 `links.ts` (new)

- All external links (Discord, FAQ, Donate) open via `shell.openExternal` through the
  bridge. No in-app navigation to remote origins.

### 3.7 `theme-override.css` (new)

- Loaded after `styles.css`.
- Only maps Camxora tokens onto Rea variables (surface, text, accent, border, radius).
- No layout changes, no font-size changes, no global resets.

### 3.8 Build config changes

- `base: './'`.
- Output to `../vizzy-dist`.
- `build.sourcemap: true` for diagnostics, excluded from the installer.
- Disable the Rea service worker; the Electron host provides headers.
- Exclude test scripts and reference assets from the bundle.

---

## 4. Host wiring

### 4.1 Main process

```ts
// electron/vizzy-host/server.ts
registerVizzyScheme();          // camxora-vizzy:// with COOP/COEP
createVizzyView(parent, bounds); // WebContentsView
wireBridge(view);                // postMessage <-> ipcMain
```

- The view is attached to a placeholder rectangle supplied by the renderer
  (`vizzy:attach { x, y, width, height }`).
- The renderer sends bounds on resize; main clamps to the window.
- The view is hidden when the route changes; destroyed after save/confirm.

### 4.2 Preload for the Vizzy view

Exposes only `window.camxoraVizzy` with the methods in §3.1. No `ipcRenderer`, no `fs`.

### 4.3 Bridge messages

| Direction | Message | Purpose |
|---|---|---|
| shell→view | `init { tokens, projectSummary }` | Theme + session |
| view→shell | `ready` | View is mounted |
| view→shell | `dirty { dirty }` | Save-state strip |
| view→shell | `save { name, bytes }` | Save request |
| view→shell | `pick-media { kind }` | Native picker |
| view→shell | `export { request }` | Export |
| shell→view | `export-progress { ... }` | Progress |
| view→shell | `error { message, stack }` | Diagnostics |
| shell→view | `open-project { id }` | Recent project |

Binary payloads use `ArrayBuffer` transfer. All messages carry a `v` version.

---

## 5. Asset policy

| Asset | Ship? | Notes |
|---|---|---|
| Rea fonts | Yes | Verify licences |
| Rea icons | Yes | Original Material paths |
| Built-in spectrum catalogue | Yes | JSON |
| Particle presets | Yes | JSON; lazy-load |
| Butterchurn presets | Yes | Check licence |
| Lottie examples | Only licensed ones | Otherwise user-provided |
| Reference projects | No | Keep in test fixtures, not the installer |
| `.shots/` screenshots | No | Test artefacts only |
| Vizzy reference exports | No | Unless a licence explicitly allows redistribution |
| Marketplace templates | Installed on demand | Stored under `templates/` |

The Rea `public/` folder is 276 MB. The installer target is ≤ 220 MB, so pruning is
mandatory. Budget: ≤ 60 MB of Vizzy static assets.

---

## 6. Build pipeline

```bash
# one-time / on Rea update
node desktop-electron/scripts/sync-vizzy.mjs --source "G:/Developments/Rea/editor"

# every build
npm --prefix desktop-electron/vizzy ci
npm --prefix desktop-electron/vizzy run build
npm --prefix desktop-electron run build
```

CI verifies:

- the vendored hash matches `UPSTREAM.md`;
- the patch set applies cleanly;
- the Vizzy bundle builds;
- the hosted page reports `crossOriginIsolated === true`;
- the editor boots and opens a fixture project.

---

## 7. Test hooks

- `window.__vizzyTest` exposes a small, read-only snapshot API for E2E:
  `{ ready, projectId, nodeCount, effectiveStage, dirty, fftTier }`.
- E2E uses `WebContentsView`'s `webContents.executeJavaScript` to read it.
- The test API is compiled only in `CAMXORA_E2E=1` builds.

---

## 8. What we deliberately do not change

- The renderer, shaders, node graph, animation evaluator, analyser math, presets or import
  mapping. Those are the parity surface.
- Rea's DOM structure and CSS class names, except the scoped token override.
- The project JSON schema. Camxora adds a wrapper (`schemaVersion`, `app`, `createdAt`) but
  the inner project stays Rea-compatible.

---

## 9. Future native migration (out of scope for 2.0.0)

If the hosted approach is later replaced, the seam is `VizzyHost` + `storage.ts` +
`media.ts` + `exporter-adapter.ts`. A native renderer would implement the same interfaces
without touching the UI or project model. Do not start that migration before the hosted
version ships and the parity baseline is stable.
