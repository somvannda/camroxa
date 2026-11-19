# Vizzy — Integration Status (P7, first milestone)

> **Document ID:** CAMXORA-ED-VZ-INT-01
> **Version:** 1.0.0
> **Status:** Verified — editor hosted, native open/save working
> **Last updated:** 2026-11-19
> **Scope:** Host the real Rea/Vizzy editor in Electron and prove native project I/O.
> Pipeline templates, batch rendering, native export and the 91-template pack are **not**
> part of this milestone.

---

## 1. What works

| Capability | Evidence |
|---|---|
| The real Rea editor boots inside a `WebContentsView` in the Vizzy route | `tests/e2e/vizzy.mjs` — `#topbar`, `#rail`, `#inspector`, `#timeline`, menus `File/Edit/Project/View/Help` |
| Stage renders through WebGL2 | stage canvas `534×300`, `getContext("webgl2")` non-null on the live canvas and on a fresh one |
| Cross-origin isolation | `crossOriginIsolated === true`, `fftTier === "threads"` (SharedArrayBuffer path engaged) |
| Assets, workers, WASM, fonts load over `camxora-vizzy://` | editor boot + threaded FFT + CanvasKit/three bundle load with no CSP violations in the first 10 s |
| Dedicated preload, no shell bridge | `window.camxoraVizzy` present, `window.camxora` absent inside the view |
| Shell strip | project name, saved/unsaved dot, item count, FFT tier, isolation badge, Save / Open / Close |
| Native Save (shell + editor `Ctrl+S`) | atomic write to `%APPDATA%/Camxora Desktop/projects/<slug>.camxora-vizzy.json`; `Ctrl+S` inside the editor bumps the same file's mtime |
| Native Open | native dialog (defaults to `projects/`), snapshot applied to the live editor, strip updates |
| Save → Open → Save round-trip | semantically identical JSON (only `savedAt` and three analyser counters differ — §6) |
| Route leave | view detaches, no `camxora-vizzy://` webContents remains |
| Crash isolation | `forcefullyCrashRenderer()` → shell stays alive, strip shows the crash, editor auto-reloads in ~2 s |
| No leaks | project file and editor DOM contain no session email and no token fields |

Screenshots: `desktop-electron/artifacts/vizzy/shell.png` (shell strip) and
`desktop-electron/artifacts/vizzy/editor.png` (`capturePage` of the hosted editor) — both
git-ignored, produced by the E2E run.

### 1.1 Boot facts measured on this machine

| Field | Value |
|---|---|
| Electron | 45.4.1 (Chromium 156) |
| Transport | `camxora-vizzy://vizzy/index.html` (`registerSchemesAsPrivileged` + `protocol.handle`) |
| Isolation | COOP `same-origin`, COEP `require-corp`, CORP `cross-origin` on every response |
| Bundle | `vizzy-dist/` ≈ 45 MB (32 MB of it is `ffmpeg-core.wasm` for the export path) |
| Vendored source | 241 files, `vizzy/UPSTREAM.md` records the tree hash |
| Stage fps in the harness | 27 fps at 534×300, synthetic audio source |

---

## 2. How it is built

```powershell
cd desktop-electron

# one-time / on a Rea update: vendor + patch the editor
npm run vizzy:sync          # node scripts/sync-vizzy.mjs [--source "G:/Developments/Rea/editor"]

# install + build the editor bundle (→ desktop-electron/vizzy-dist)
npm run vizzy:install       # npm ci in vizzy/
npm run vizzy:build         # vite build, base "./", outDir ../vizzy-dist

# the app itself
npm run build               # typecheck + renderer + main + shell preload + vizzy preload
npm run test:e2e            # includes tests/e2e/vizzy.mjs
```

`npm run vizzy` does sync + install + build in one step.
`npm run vizzy:sync -- --check` (or `node scripts/sync-vizzy.mjs --check`) fails when the
vendored tree no longer matches `vizzy/UPSTREAM.md`.

`npm run dev` builds the Vizzy preload first, but the page still needs a built
`vizzy-dist/`, so run `npm run vizzy:build` once after changing the vendored source.

### 2.1 Vendored layout

```
desktop-electron/
  vizzy/
    UPSTREAM.md              source path, sync date, file count, tree sha256
    patches/                 the patch set (source of truth):
      boot.ts                  entry: editor first, host adapter second
      host-adapter.ts          window.__vizzyTest, dirty, open/save state
      bridge.ts                window.camxoraVizzy types
    src/**                   Rea source (patched copies live in src/host/)
    public/**                pruned: fonts, img, lottie, media, models, particles,
                             presets, vendor, export + favicon (≈10 MB).
                             `creations/` (265 MB) is deliberately absent.
    index.html               entry repointed to /src/host/boot.ts
    vite.config.ts           generated: base "./", outDir ../vizzy-dist
    package.json             generated from Rea's, deps pinned by package-lock.json
  vizzy-dist/                build output (git-ignored)
  scripts/sync-vizzy.mjs     the only writer of vizzy/
```

The sync script copies, prunes, applies two anchored patches and fails loudly when an anchor
moves. Patch anchors:

1. `index.html` — `/src/main.ts` → `/src/host/boot.ts`.
2. `src/main.ts` — at the top of `saveProjectLocally()`, a `CAMXORA-PATCH` block routes Save
   to `window.camxoraVizzy.saveProject(...)` when the bridge exists. The IndexedDB path stays
   as the browser fallback.

---

## 3. Host wiring

```
src/features/vizzy/vizzy-page.tsx      shell strip + the rectangle the view sits in
src/features/vizzy/use-vizzy-host.ts   attach / ResizeObserver bounds / detach / state
electron/vizzy-preload.ts              the only bridge inside the view
electron/vizzy-host/host.ts            VizzyHost: view lifecycle, save/open, crash policy
electron/vizzy-host/protocol.ts        registerHostSchemes() + installVizzyProtocol()
electron/vizzy-host/assets.ts          MIME, CSP, streaming + Range responses
electron/vizzy-host/project-store.ts   slug, atomic write, validation, semantic equality
electron/vizzy-host/bridge.ts          versioned view↔host message router
electron/ipc/vizzy.ts                  IPC surface with sender checks
```

### 3.1 IPC surface

| Channel | Sender | Purpose |
|---|---|---|
| `vizzy:attach` / `vizzy:set-bounds` / `vizzy:detach` | shell | place, move and stop the view |
| `vizzy:state` (invoke) | shell | current strip state |
| `vizzy:state` (event) | main → shell | state pushed after every editor report |
| `vizzy:probe` | shell | live `__vizzyTest` snapshot + WebGL2 check |
| `vizzy:save` / `vizzy:open` / `vizzy:open-path` / `vizzy:reload` | shell | strip actions |
| `vizzy:bridge` | view | `vizzy:state`, `vizzy:dirty`, `vizzy:ack`, `vizzy:log` |
| `vizzy:project:save` / `vizzy:project:open` | view | the patched editor Save, native Open |

Every handler validates the sender's webContents id; the view cannot call shell channels and
the shell cannot call view channels.

### 3.2 Project files

- Location: `<userData>/projects/<slug>.camxora-vizzy.json` (`ensureAppDirs()` already creates it).
- Write: temp file → `fsync` → rename (atomic on NTFS/POSIX); pretty JSON + trailing newline.
- Read: size cap 64 MB, JSON parse, `format === "studio-project"`, `project` object,
  `nodes`/`layers` arrays. Anything else is rejected before it reaches the editor.
- Open outside `projects/` is refused unless `CAMXORA_E2E=1` (the harness needs a fixture path).

---

## 4. Still stubbed

| Area | Status | Notes |
|---|---|---|
| Pipeline templates (`template.json`/`pipeline.json`) | **not built** | Next milestone. |
| Renders panel, batch render, merge/reel/upload | **not built** | Placeholder-free: nothing claims to work. |
| Native FFmpeg export | **stubbed** | The bridge throws "pipeline milestone" for `vizzy:export`. The editor's in-page exporters still exist inside the bundle but are not wired to a native output path. |
| Media picker / `camxora-media://` inside the editor | **stubbed** | `pickMedia` returns `null`. Local drag-drop still works inside the editor for files the user drops; project assets that reference `camxora-media://` are not produced yet. |
| 91-template library, 5 presets, 32 catalogue, 18 particle, 6 Butterchurn | **shipped as-is** | Preset/catalogue JSON is vendored and loads. The 265 MB `creations/` corpus is **not** shipped, so the Projects → Creations browser shows "No creations captured yet." |
| Recent-projects list / autosave / recovery | **not built** | The strip has Save/Open/Close only. Rea's own IndexedDB autosave still runs as a browser-local cache. |
| Save As (new file) | **partial** | `Ctrl+Shift+S` renames the project and overwrites `<new-slug>.camxora-vizzy.json`; there is no "choose a path" dialog. |
| Account/sign-in inside the editor | **unchanged from Rea** | Rea's own "Sign in" dialog is inert ("Accounts are not part of this build"); Camxora's session is not surfaced in the editor. |
| Theme override | **not applied** | The editor ships its own palette. A scoped Camxora token override is a later design task (`04-CUSTOMIZATION.md`). |
| Dev HMR for the editor | **not wired** | The page always loads the built bundle. |
| Service worker / offline cache | **disabled by design** | The protocol handler supplies COOP/COEP; Rea's `coi-sw.js` is not vendored. |

---

## 5. Rebuild / verify checklist

```powershell
cd desktop-electron
npm ci
node scripts/sync-vizzy.mjs --check     # vendored tree matches UPSTREAM.md
npm run typecheck
npm run lint
npm test                                # 20 files / 156 tests
npm run build                           # includes build:vizzy-preload
node tests/e2e/vizzy.mjs                # ~25 s
npm run test:e2e                        # all suites, vizzy included
```

---

## 6. Known gaps and risks

| Item | Detail | Impact / next step |
|---|---|---|
| Rea's snapshot stores live analyser counters | `nodes[*].props.currentData`, `cumulativeData`, `cumMult` change every time the playhead moves, so two saves of the "same" project are not byte-identical. | The round-trip assertion ignores exactly these three keys (`tests/e2e/vizzy.mjs`). No authored state is ignored. Revisit if the snapshot format is ever owned by Camxora. |
| Dirty flag is history-depth based | Rea has no dirty flag. The adapter marks dirty when `editHistory.labels().length` differs from the depth at the last save/open. Undo back to the saved state stays "dirty". | Honest but coarse; a project hash in the adapter would be exact and cheap enough on demand. |
| Project file names are slug-based | Two projects with the same name share one file. | Add an id suffix (or a recent-project index) before the pipeline milestone needs many projects. |
| `detach()` destroys the view | Returning to `/vizzy` reloads the editor (~1.5 s) and re-creates the default project. | Keep a suspended view per window if the reload becomes annoying; the crash path already proves recreate works. |
| `ffmpeg-core.wasm` is 32 MB inside `vizzy-dist` | Comes from `@ffmpeg/core` via the editor's exporter. | Fits the ≤60 MB asset budget; exclude it when native export replaces the wasm path. |
| One privileged-scheme list per process | A second `registerSchemesAsPrivileged` call replaced the first, which broke `camxora-media://`. | Fixed with `registerHostSchemes()`, which registers both schemes in one call. If a third scheme appears, add it there — never call `registerSchemesAsPrivileged` twice. |
| `protocol.handle` streams every asset | `Range` is honoured for single ranges (video seeking, wasm streaming). | Multi-range requests fall back to the full body, which is the safe default. |
| The host is Windows-tested only | macOS/Linux packaging paths (`process.resourcesPath`) are implemented but unverified. | Re-run the E2E on each release platform; it is machine-checkable. |
| Native dialogs cannot be driven by Playwright | The E2E exercises `vizzy:open-path` (the same code path the dialog feeds). | The dialog itself is a 3-line wrapper (`openFromDialog`) with no branching. |
| Editor assets outside `public/` | `creations/` is not shipped, and `/audio/haende-hoch.mp3` is absent, so the editor boots on the synthetic analyser source and the Creations browser is empty. | Expected for this milestone; the 91-template pack lands with the pipeline work. |

---

## 7. Files added or changed

| Path | Change |
|---|---|
| `scripts/sync-vizzy.mjs` | new — vendor + patch driver, `--check` mode |
| `vizzy/**` | new — vendored editor, patch set, `UPSTREAM.md` |
| `electron/vizzy-host/assets.ts` | streaming responses, `Range` parsing, extra MIME types, CSP for workers/blobs |
| `electron/vizzy-host/protocol.ts` | `registerHostSchemes()`, `installVizzyProtocol()` guard, streaming handler |
| `electron/vizzy-host/bridge.ts` | `vizzy:state`, `vizzy:ack`, `vizzy:open-project-json` messages |
| `electron/vizzy-host/host.ts` | new — production `VizzyHost` |
| `electron/vizzy-host/project-store.ts` | new — slug, atomic write, validation, semantic equality |
| `electron/vizzy-preload.ts` | new — the view's only bridge |
| `electron/ipc/vizzy.ts` | new — IPC surface + sender checks |
| `electron/ipc/index.ts` | registers the Vizzy IPC |
| `electron/main.ts` | scheme registration, protocol install, host creation, dispose |
| `electron/services/media.ts` | exported `mediaSchemePrivileges()` so both schemes register once |
| `electron/preload.ts` | `vizzy` namespace |
| `electron/shared/types.ts` | `VizzyState`, `VizzyBounds`, `VizzyProbe`, save/open results |
| `src/lib/bridge.ts` | typed `vizzy` bridge |
| `src/features/vizzy/vizzy-page.tsx`, `use-vizzy-host.ts` | new page + placement hook |
| `src/app.tsx` | `/vizzy` route (route only) |
| `tests/e2e/vizzy.mjs` | new harness |
| `tests/unit/vizzy-project-store.test.ts`, `vizzy-protocol.test.ts` | new unit tests |
| `tests/fixtures/vizzy/trap-motion.camxora-vizzy.json` | 31 KB round-trip fixture |
| `package.json` | `vizzy:*`, `build:vizzy-preload`, e2e + dev integration |
| `eslint.config.js` | ignores the vendored tree and its build output |
| `electron-builder.yml` | ships `vizzy-dist` as an extra resource |
| `.gitignore` | ignores `vizzy-dist/` |
