# Vizzy — Integration Status (P7, second milestone)

> **Document ID:** CAMXORA-ED-VZ-INT-01
> **Version:** 1.1.0
> **Status:** Verified — editor hosted, native open/save and native export working
> **Last updated:** 2026-11-19
> **Scope:** Host the real Rea/Vizzy editor in Electron, prove native project I/O, and
> render the open project to a real video file with progress, cancel and a Renders panel.
> Pipeline templates, batch rendering, merge/reel and the 91-template pack are **not**
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
| Native export (MP4) | shell Export → the editor's own `runExport()` → real H.264/AAC MP4 in `<userData>/renders/`; `tests/e2e/vizzy-export.mjs` (480×270, 2 s, 60 frames, ~2.4–4.7 s, ~400–450 KB) |
| Export progress + cancel | `vizzy:export:progress` events per frame; cancel aborts the exporter and deletes the partial file (asserted: `renders/` stays empty) |
| Export settings | width/height/fps/format/start/end from the strip; defaults 1920×1080/30/H.264 when the project reports nothing |
| Renders panel | lists `renders/` (name, size, date), inline `<video>` over `camxora-media://`, Reveal, Delete with confirmation; delete outside `renders/` refused |
| Export validation | ffprobe reports codec/size/duration back to the shell; the E2E re-probes the file independently |
| No leaks | project file and editor DOM contain no session email and no token fields |

Screenshots: `desktop-electron/artifacts/vizzy/shell.png` (shell strip),
`desktop-electron/artifacts/vizzy/editor.png` (`capturePage` of the hosted editor),
`export-settings.png` (Export rail) and `renders.png` (Renders rail with inline playback) —
all git-ignored, produced by the E2E runs.

### 1.1 Boot facts measured on this machine

| Field | Value |
|---|---|
| Electron | 45.4.1 (Chromium 156) |
| Transport | `camxora-vizzy://vizzy/index.html` (`registerSchemesAsPrivileged` + `protocol.handle`) |
| Isolation | COOP `same-origin`, COEP `require-corp`, CORP `cross-origin` on every response |
| Bundle | `vizzy-dist/` ≈ 45 MB (32 MB of it is `ffmpeg-core.wasm` for the webm/fallback ladder) |
| Vendored source | 241 files, `vizzy/UPSTREAM.md` records the tree hash |
| Stage fps in the harness | 27 fps at 534×300, synthetic audio source |
| Export (fixture, 480×270, 30 fps, 2 s, H.264) | 2.4–4.7 s wall clock, ~400–450 KB, ffprobe `h264` + `aac`, 60 frames, 1.97 s |
| Export CPU floor | the reference wasm encoder runs one frame at a time; 1080p30 is roughly 8–10× slower than 480p30 |

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

The sync script copies, prunes, applies anchored patches and fails loudly when an anchor
moves. Patch anchors:

1. `index.html` — `/src/main.ts` → `/src/host/boot.ts`.
2. `src/main.ts` — at the top of `saveProjectLocally()`, a `CAMXORA-PATCH` block routes Save
   to `window.camxoraVizzy.saveProject(...)` when the bridge exists. The IndexedDB path stays
   as the browser fallback.
3. `src/main.ts` — a `camxoraExportHooks` module variable (progress + cancel) next to
   `let exporting = false;`.
4. `src/main.ts` — `runExport()` reads the host cancel flag in `shouldCancel` and forwards
   `onProgress` to the host. The in-page dialog is otherwise untouched.
5. `src/main.ts` — a `CAMXORA-PATCH` block after the editor globals listens for
   `export-run` / `export-cancel` and calls `runExport()` with a chunk-streaming
   `SaveFileHandle`.

---

## 3. Host wiring

```
src/features/vizzy/vizzy-page.tsx      shell strip + the rectangle the view sits in
src/features/vizzy/use-vizzy-host.ts   attach / ResizeObserver bounds / detach / state
src/features/vizzy/use-vizzy-export.ts export job state + progress events
src/features/vizzy/use-vizzy-renders.ts renders list / delete / reveal / media URL
src/features/vizzy/vizzy-export-menu.tsx  settings rail + progress + result
src/features/vizzy/vizzy-renders-panel.tsx renders rail with inline <video>
electron/vizzy-preload.ts              the only bridge inside the view
electron/vizzy-host/host.ts            VizzyHost: view lifecycle, save/open, export job, renders
electron/vizzy-host/protocol.ts        registerHostSchemes() + installVizzyProtocol()
electron/vizzy-host/assets.ts          MIME, CSP, streaming + Range responses
electron/vizzy-host/project-store.ts   slug, atomic write, validation, semantic equality
electron/vizzy-host/renders.ts         export settings, render names, containment, chunk writer
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
| `vizzy:export` (invoke) | shell | start a native export; resolves with the settled outcome |
| `vizzy:export:cancel` | shell | cancel the active job |
| `vizzy:export:progress` (event) | main → shell | `{ jobId, done, total, percent, stage }` |
| `vizzy:renders:list` / `:delete` / `:reveal` / `:url` | shell | managed `renders/` |
| `vizzy:export:chunk` (invoke) | view | one encoded chunk at an absolute offset |
| `vizzy:bridge` | view | `vizzy:state`, `vizzy:dirty`, `vizzy:ack`, `vizzy:export-progress`, `vizzy:export-finished`, `vizzy:log` |
| `vizzy:project:save` / `vizzy:project:open` | view | the patched editor Save, native Open |

Every handler validates the sender's webContents id; the view cannot call shell channels and
the shell cannot call view channels.

### 3.2 Project files

- Location: `<userData>/projects/<slug>.camxora-vizzy.json` (`ensureAppDirs()` already creates it).
- Write: temp file → `fsync` → rename (atomic on NTFS/POSIX); pretty JSON + trailing newline.
- Read: size cap 64 MB, JSON parse, `format === "studio-project"`, `project` object,
  `nodes`/`layers` arrays. Anything else is rejected before it reaches the editor.
- Open outside `projects/` is refused unless `CAMXORA_E2E=1` (the harness needs a fixture path).

### 3.3 Native export mechanism

The renderer is the editor's own exporter. Nothing re-implements the stage, the analysers
or the encoder.

```
shell Export button
  → window.camxora.vizzy.export(settings)          (shell preload, invoke)
  → vizzy:export                                    (ipc/vizzy.ts, shell-only + zod)
  → VizzyHost.exportVideo()                         (resolves settings against __vizzyTest.readProjectInfo)
      opens <userData>/renders/<slug>-<timestamp>.<mp4|webm> ("w+")
      sends `vizzy:export-run` over the view bridge (settings only, never a path)
  → patched src/main.ts                             (host-adapter bridge, window.camxoraVizzy)
      runExport(settings, hostSaveHandle)
        - mp4  → ReferenceWasmExporter (x264/AAC, streams chunks at absolute offsets)
        - webm → WebCodecsExporter when available, else the wasm ladder
  → window.camxoraVizzy.exportChunk(jobId, position, data)   (view-only invoke)
  → fs handle.write(buffer, 0, length, position)              (pwrite at the chunk offset)
  → editor reports progress per frame + one terminal `vizzy:export-finished`
  → host closes the handle, ffprobe-validates, resolves the shell invoke with
      { path, name, bytes, frames, durationSec, width, height, videoCodec, audioCodec }
```

- **Whole file never crosses the boundary.** The reference encoder flushes encoded bytes at
  absolute offsets; the host writes each chunk with positional `FileHandle.write`. Binary is
  structured-clone (`Uint8Array`), never base64. The only in-memory path is the wasm
  fallback for WebM when WebCodecs is unavailable: the editor slices that blob into 4 MB
  chunks before it reaches IPC.
- **Settings.** `renders.ts` resolves the request against the project: even dimensions in
  `16..7680`, fps `1..120`, bitrate `0..200` Mbps (default by height, 25 at 1080p), crf
  `0..51`, start/end clamped to the project duration. Defaults: **1920×1080 / 30 fps /
  H.264 + AAC in MP4** when the project reports nothing. MP4 always encodes H.264; WebM
  encodes VP9 (VP8 on request).
- **Progress + cancel.** `runExport` is patched to forward its own frame counter and to
  read a host cancel flag in `shouldCancel`. Cancel aborts between frames, the host waits
  up to 5 s for the view to settle, then closes the handle and deletes the partial file
  itself. A 60-minute job ceiling does the same for a wedged encoder. Detaching the route,
  closing the window or a renderer crash cancels the job and removes its partial file.
- **Validation.** `services/ffmpeg.probe()` runs on the closed file (codec, size, duration).
  If ffprobe is unavailable the render is kept and the probe fields are null — the E2E
  probes independently with ffprobe.
- **Files.** `<userData>/renders/<slug>-<timestamp>.<ext>` (`slugifyProjectName` + local
  `YYYYMMDD-HHmmss`, `-2`/`-3` on collision). Only slug, timestamp and extension reach the
  name: no email, no session token, no absolute path is sent to the editor.

### 3.4 Renders panel

- `vizzy:renders:list` returns `{ name, bytes, mtimeMs }` for files whose name matches the
  exporter's pattern; symlinks, subdirectories and foreign files are ignored.
- `vizzy:renders:url` mints a `camxora-media://local/<uuid>` token for inline playback;
  `camxora-media://` already allows `renders/` as a managed root and serves Range requests.
- Delete requires confirmation in the UI and a bare managed name on the IPC side
  (`isRenderFileName` + strict containment). `../` and foreign extensions are refused, so a
  compromised shell cannot delete outside `renders/`.
- **Why a rail, not a floating popover:** the editor is a native `WebContentsView` and
  always paints over shell DOM. Export settings and the renders list open in a right-hand
  rail that shrinks the editor column; the `ResizeObserver` re-places the native view. The
  strip keeps a one-row progress/cancel/result status.

---

## 4. Still stubbed

| Area | Status | Notes |
|---|---|---|
| Pipeline templates (`template.json`/`pipeline.json`) | **not built** | Next milestone. |
| Native video export (MP4 + WebM) | **working** | Shell-owned job, editor-owned encoder, chunked to `renders/`, ffprobe-validated. MP4/H.264 is the reference path; WebM uses WebCodecs when the build has it. |
| Renders panel | **working** | List, inline playback, Reveal, Delete with confirmation. No thumbnails yet. |
| Batch render, merge/reel/upload | **not built** | One export at a time; no queue, no reel, no upload. |
| Export of a closed editor / headless render | **not built** | A job needs the attached, ready editor. Route leave, close or crash cancels the job and deletes the partial file. |
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
npm test                                # 23 files / 194 tests
npm run build                           # includes build:vizzy-preload
node tests/e2e/vizzy.mjs                # ~25 s
node tests/e2e/vizzy-export.mjs         # ~40 s, writes export-settings.png + renders.png
npm run test:e2e                        # all 12 suites, both Vizzy suites included
```

---

## 6. Known gaps and risks

| Item | Detail | Impact / next step |
|---|---|---|
| Rea's snapshot stores live analyser counters | `nodes[*].props.currentData`, `cumulativeData`, `cumMult` change every time the playhead moves, so two saves of the "same" project are not byte-identical. | The round-trip assertion ignores exactly these three keys (`tests/e2e/vizzy.mjs`). No authored state is ignored. Revisit if the snapshot format is ever owned by Camxora. |
| Dirty flag is history-depth based | Rea has no dirty flag. The adapter marks dirty when `editHistory.labels().length` differs from the depth at the last save/open. Undo back to the saved state stays "dirty". | Honest but coarse; a project hash in the adapter would be exact and cheap enough on demand. |
| Project file names are slug-based | Two projects with the same name share one file. | Add an id suffix (or a recent-project index) before the pipeline milestone needs many projects. |
| `detach()` destroys the view | Returning to `/vizzy` reloads the editor (~1.5 s) and re-creates the default project. | Keep a suspended view per window if the reload becomes annoying; the crash path already proves recreate works. |
| Export runs inside the attached editor | The job needs the live renderer and analyser state. | Route leave / window close / crash cancels the job and deletes the partial file. A headless/offscreen renderer is a later milestone. |
| One export at a time | `VizzyHost` keeps a single job; a second request is refused. | Enough for the strip; the batch/reel milestone needs a queue. |
| Cancel has a 5 s grace | The host asks the editor to abort, then closes the handle and deletes the partial file itself. | A wedged encoder cannot leave a file behind; the editor's own UI settles a moment later. |
| Progress is frame-based | The editor reports `done/total` per rendered frame; the encode phase reuses the same counter. | Honest but coarse for the final mux; exact per-stage weights would need exporter changes. |
| Renders are listed without thumbnails | `listRenderFiles` reads name/size/mtime only; no poster frames. | Add a thumbnail pass (ffmpeg screenshot) when the library milestone needs previews. |
| `ffmpeg-core.wasm` is 32 MB inside `vizzy-dist` | Comes from `@ffmpeg/core` via the editor's exporter. | Still needed for the WebM/VPx fallback ladder and long webm exports; keep until the native path covers WebM too. |
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
| `electron/vizzy-host/host.ts` | new — production `VizzyHost`; export job lifecycle, renders listing/delete/reveal |
| `electron/vizzy-host/renders.ts` | new — export settings, render names, containment, `RenderChunkWriter` |
| `electron/vizzy-host/project-store.ts` | new — slug, atomic write, validation, semantic equality |
| `electron/vizzy-preload.ts` | new — the view's only bridge; export chunk/progress/finished channels |
| `electron/ipc/vizzy.ts` | new — IPC surface + sender checks; export, cancel, renders |
| `electron/ipc/index.ts` | registers the Vizzy IPC |
| `electron/main.ts` | scheme registration, protocol install, host creation, dispose, export progress forward |
| `electron/services/media.ts` | exported `mediaSchemePrivileges()` so both schemes register once |
| `electron/preload.ts` | `vizzy` namespace incl. export/cancel/renders |
| `electron/shared/types.ts` | `VizzyState` (+ project size/fps/duration), `VizzyBounds`, `VizzyProbe`, save/open, export/renders |
| `src/lib/bridge.ts` | typed `vizzy` bridge |
| `src/features/vizzy/vizzy-page.tsx`, `use-vizzy-host.ts` | new page + placement hook; export/renders rail |
| `src/features/vizzy/use-vizzy-export.ts`, `use-vizzy-renders.ts` | new — export job state + renders list |
| `src/features/vizzy/vizzy-export-menu.tsx`, `vizzy-export-status.tsx`, `vizzy-renders-panel.tsx`, `vizzy-format.ts` | new — rail UI |
| `src/app.tsx` | `/vizzy` route (route only) |
| `tests/e2e/vizzy.mjs`, `tests/e2e/vizzy-export.mjs` | host harness + export/renders harness |
| `tests/unit/vizzy-project-store.test.ts`, `vizzy-protocol.test.ts`, `vizzy-renders.test.ts` | project, protocol and render/export unit tests |
| `tests/fixtures/vizzy/trap-motion.camxora-vizzy.json` | 31 KB round-trip fixture |
| `package.json` | `vizzy:*`, `build:vizzy-preload`, e2e (incl. `vizzy-export.mjs`) + dev integration |
| `eslint.config.js` | ignores the vendored tree and its build output |
| `electron-builder.yml` | ships `vizzy-dist` as an extra resource |
| `.gitignore` | ignores `vizzy-dist/` |
