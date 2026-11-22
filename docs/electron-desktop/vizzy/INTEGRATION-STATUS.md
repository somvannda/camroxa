# Vizzy — Integration Status (P7, third milestone)

> **Document ID:** CAMXORA-ED-VZ-INT-01
> **Version:** 1.3.0
> **Status:** Verified: editor hosted, native open/save, native export, template save/preview/render, offscreen batch rendering with queue → Music → Progress
> **Last updated:** 2026-11-19
> **Scope:** Host the real Rea/Vizzy editor in Electron, prove native project I/O, render the
> open project to a real video file with progress, cancel and a Renders panel, save the
> current preview as a pipeline video template, and render queued batches offscreen without
> the `/vizzy` route. Upload is **not** part of this milestone.

---

## 1. What works

| Capability | Evidence |
|---|---|
| The real Rea editor boots inside a `WebContentsView` in the Vizzy route | `tests/e2e/vizzy.mjs` — `#topbar`/`#status` exist but are `display:none` in the embedded view; `#rail`, `#inspector`, `#timeline` render |
| Stage renders through WebGL2 | stage canvas `534×300`, `getContext("webgl2")` non-null on the live canvas and on a fresh one |
| Cross-origin isolation | `crossOriginIsolated === true`, `fftTier === "threads"` (SharedArrayBuffer path engaged) |
| Assets, workers, WASM, fonts load over `camxora-vizzy://` | editor boot + threaded FFT + CanvasKit/three bundle load with no CSP violations in the first 10 s |
| Dedicated preload, no shell bridge | `window.camxoraVizzy` present, `window.camxora` absent inside the view |
| Shell strip | project name, saved/unsaved dot, item count, dimensions; compact groups: New / Open / Save project, Export / Save as template, Templates / Renders, Close (tooltips state each purpose) |
| Embedded frame | editor topbar and status line hidden; Camxora navy surfaces, Inter stack, purple accent, rounded controls and blue/purple timeline tints; the left rail is a horizontal tab bar under the shell strip; the stage sits in a bordered, rounded frame with an 8 px gap inside the shell |
| New project | shell **New** → confirmation → `vizzy:new-project` resets the live project (layers, nodes, effects, automations, analyzers, assets) without leaving the page |
| Notifications | on `/vizzy` one compact toast stays inside the 48 px shell strip instead of being clipped by the native editor view |
| Native Save (shell + editor `Ctrl+S`) | atomic write to `%APPDATA%/Camxora Desktop/projects/<slug>.camxora-vizzy.json`; `Ctrl+S` inside the editor bumps the same file's mtime |
| Native Open | native dialog (defaults to `projects/`), snapshot applied to the live editor, strip updates |
| Save → Open → Save round-trip | semantically identical JSON (only `savedAt` and three analyser counters differ — §6) |
| Route leave | view hides; the editor process and the live project stay alive, so unsaved changes/undo survive; Close or window close stops it |
| Crash isolation | `forcefullyCrashRenderer()` → shell stays alive, strip shows the crash, editor auto-reloads in ~2 s |
| Native export (MP4) | shell Export → the editor's own `runExport()` → real H.264/AAC MP4 in `<userData>/renders/`; `tests/e2e/vizzy-export.mjs` (480×270, 2 s, 60 frames, ~2.4–4.7 s, ~400–450 KB) |
| Export progress + cancel | `vizzy:export:progress` events per frame; cancel aborts the exporter and deletes the partial file (asserted: `renders/` stays empty) |
| Export settings | mirror of the editor dialog: encoder, full resolution list, 24/30/60 fps, H.264/VP9/VP8, bitrate/CRF/preset/profile/audio bitrate, start/end and estimate; defaults 60 fps + height-based bitrate, 1920×1080/H.264 when the project reports nothing; end/length comes from the live composition duration after audio decode; the framebuffer is pinned during export so shell resizes cannot corrupt it |
| Renders panel | lists `renders/` (name, size, date), inline `<video>` over `camxora-media://`, Reveal, Delete with confirmation; delete outside `renders/` refused |
| Export validation | ffprobe reports codec/size/duration back to the shell; the E2E re-probes the file independently |
| Save as video template | strip action → `vizzy:template-options` reads the live preview → the host auto-detects every binding (including all palette nodes) → `vizzy:save-template` writes the whole snapshot + `pipeline.json` + `thumbnail.png` atomically; no per-node selection; a kind/aspect mismatch blocks the save; `tests/e2e/vizzy-templates.mjs` |
| Templates panel | rail listing thumbnail, name, kind, output size and date; Preview loads the saved project via `vizzy:open-project-json`; Delete is confirmed and emits `video-templates:changed`; empty state points at Save preview |
| Preview parity (project) | the editor's project after Preview is semantically identical to the saved `template.json` (runtime-only counters ignored) |
| Render one saved template | Templates rail Render → native audio pick → `vizzy:render-template` → plan from `buildPipelineRenderPlan()` → saved project loaded → run audio streamed over `camxora-media://` into the editor's loader → existing exporter → `renders/<template-slug>-<timestamp>.mp4`; measured 1920×1080/30, 2 s WAV: 60 frames, h264+aac, 1.97 s, ~2.0 MB, 10.1-11.1 s wall clock. `pipeline.json.export` carries the Export rail's resolution/fps/bitrate/CRF/preset/profile/audio bitrate/encoder into every pipeline render; start/end still follow the live audio |
| 91-template library | Templates rail **Library** → editor's own Creations browser; `tests/e2e/vizzy-library.mjs` asserts 91 rows, manifest 200, a loaded thumbnail 200 and one template load (nebula-staff, 5 items) |
| Offscreen batch render | `electron/vizzy-host/render-window.ts`: hidden `BrowserWindow` (sandboxed, `vizzy-render` partition, no Node, throttling off) loads the same editor bundle, applies a template project JSON, streams the run audio and runs the same exporter. `vizzy.state().attached === false` throughout `tests/e2e/pipeline-batch.mjs` |
| Queue → render → ffprobe | `electron/services/pipeline-orchestrator.ts` + `electron/ipc/pipeline.ts`: `pipeline:enqueue/start/cancel/retry/list/reveal`. Two 2 s songs rendered 320×180 in **4.7–4.9 s** total, ffprobe h264+aac/60 frames each |
| Merge | Batch-level long-form merge (`-c copy`, re-encode fallback) to `<album><MMDD>.mp4` in the run folder, ffprobe-validated; a same-day second merge takes `<album><MMDD> (1).mp4` |
| Cancel / retry | Cancel marks the row `cancelled` and leaves no partial file in the run folder; retry re-enqueues only failed/cancelled rows and produced exactly one new file in the E2E |
| Output location | Offscreen pipeline renders stream straight into the run folder beside the downloaded audio (`<song>.mp4`, `<song>-reel.mp4`), under the configured Suno output directory; editor/manual exports keep using `<userData>/renders/` |
| Music trigger | Auto-video coordinator polls Progress/history and queues the profile's long/reel templates per ready song/branch; Video checkboxes gate each branch, merge is per branch; missing templates/audio report a specific message |
| Progress UI | Compact "Video pipeline" table from the durable SQLite queue only for renders that have no Operational row. Operational rows carry the local render/merge progress in their Video (Render) and Merge cells, use "Render" instead of "Converter", and have a right-click menu: Open run folder, Reveal rendered video, Copy batch ID/album, Retry images, Cancel/Retry video render, Open YouTube URL. The per-row Upload button was removed; manual upload stays in the row detail panel |
| No leaks | project file and editor DOM contain no session email and no token fields; the render window adds no storage shared with the visible editor |

`npm run vizzy:parity` compares `vizzy/src` with the decompiled reference at
`G:\Developments\Rea\editor\src` (override with `REA_EDITOR_SRC`). All 59 shared files match
1:1 except four intentional shell patches (`main.ts`, `renderer/renderer.ts`,
`ui/inspector.ts`, `ui/timeline.ts`) and three host shims under `host/`. Effects, particles,
spectrum, analyzers, shaders, presets and the renderer are not modified by the port.

Screenshots: `desktop-electron/artifacts/vizzy/shell.png` (shell strip),
`desktop-electron/artifacts/vizzy/editor.png` (`capturePage` of the hosted editor),
`export-settings.png` (Export rail), `renders.png` (Renders rail with inline playback),
`save-dialog.png` (Save as video template), `templates-panel.png` (Templates rail),
`rendered-preview.png` + `rendered-editor.png` (a rendered saved template),
`library.png` + `library-shell.png` (the 91-template Creations browser),
`batch-progress.png` + `batch-complete.png` (Video pipeline rows on Progress) —
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
| Saved-template render (1920×1080, 30 fps, 2 s WAV, H.264) | 10.1–11.1 s wall clock, 60 frames, 1.97 s, ~2.0 MB, ffprobe `h264` + `aac` |
| Template save | `capturePage()` thumbnail 343 KB; `template.json` + `pipeline.json` written atomically |

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
src/features/vizzy/use-vizzy-host.ts   attach / ResizeObserver bounds / hide on route leave / state
src/features/vizzy/use-vizzy-export.ts export job state + progress events
src/features/vizzy/use-vizzy-renders.ts renders list / delete / reveal / media URL
src/features/vizzy/vizzy-export-menu.tsx  settings rail + progress + result
src/features/vizzy/vizzy-renders-panel.tsx renders rail with inline <video>
src/features/vizzy/vizzy-template-dialog.tsx  Save as video template modal
src/features/vizzy/vizzy-templates-panel.tsx  Templates rail (preview/render/delete/library)
src/features/vizzy/vizzy-template-model.ts    pure binding/kind validation for the dialog
src/features/vizzy/use-vizzy-templates.ts     saved-template list + change events
electron/vizzy-preload.ts              the only bridge inside the view
electron/vizzy-host/host.ts            VizzyHost: view lifecycle, save/open, audio load, export delegation, renders
electron/vizzy-host/export-session.ts  one export job shared by the visible view and the batch window
electron/vizzy-host/render-window.ts   OffscreenVizzyRenderer: hidden window, partition, ready probe, open/load/export
electron/vizzy-host/protocol.ts        registerHostSchemes() + installVizzyProtocol() (+ per-session install)
electron/vizzy-host/assets.ts          MIME, CSP, streaming + Range responses
electron/vizzy-host/project-store.ts   slug, atomic write, validation, semantic equality
electron/vizzy-host/renders.ts         export settings, render names, containment, chunk writer
electron/vizzy-host/bridge.ts          versioned view↔host message router
electron/services/pipeline-templates.ts  pipeline schema, detection, binding options
electron/services/pipeline-run.ts      render plan (project + bindings + output + duration)
electron/services/pipeline-sources.ts  song title → run-folder audio resolution, unique merge path
electron/services/pipeline-orchestrator.ts  queue → offscreen render → ffprobe → merge, cancel/retry
electron/services/pipeline-queue.ts    durable queue rows (dedupe, retry, cancel-queued, output path)
electron/services/pipeline-batch.ts    sequential runner, failure isolation, per-batch merge
electron/services/pipeline-merge.ts    FFmpeg concat list, copy/re-encode, timeout/cleanup
electron/services/video-templates.ts   template store (atomic write, list, read, delete)
electron/ipc/vizzy.ts                  IPC surface with sender checks
electron/ipc/pipeline.ts               pipeline:list/enqueue/start/cancel/retry/clear/reveal
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
| `vizzy:set-visible` | shell | hide/show the native view while a shell modal is open |
| `vizzy:template-options` | shell | live snapshot → detected bindings + compatible node lists |
| `vizzy:save-template` | shell | atomic `template.json` + `pipeline.json` + `capturePage()` thumbnail |
| `vizzy:preview-template` | shell | load a saved template's project into the editor |
| `vizzy:render-template` | shell | bind run inputs, load project + track, render one MP4 |
| `vizzy:open-library` | shell | run the editor's `editorOpenCreations()` |
| `video-templates:list` / `:read` / `:delete` | shell | saved-template library |
| `video-templates:changed` (event) | main → shell | save/delete invalidation for the rail and Settings |
| `vizzy:export:chunk` (invoke) | view | one encoded chunk at an absolute offset |
| `vizzy:bridge` | view | `vizzy:state`, `vizzy:dirty`, `vizzy:ack`, `vizzy:export-progress`, `vizzy:export-finished`, `vizzy:log` |
| `vizzy:load-audio` (host → view) | main → view | stream a run track into the editor for a template render |
| `vizzy:project:save` / `vizzy:project:open` | view | the patched editor Save, native Open |
| `pipeline:list` | shell | durable queue + batches snapshot |
| `pipeline:enqueue` | shell | resolve templates/audio, create rows, optional autostart |
| `pipeline:start` / `pipeline:cancel` / `pipeline:retry` / `pipeline:clear` | shell | run control; retry re-enqueues failed/cancelled rows only |
| `pipeline:reveal` | shell | reveal a known render/merged output |
| `pipeline:changed` (event) | main → shell | queue invalidation, coalesced to ~150 ms |

Every handler validates the sender's webContents id; the view cannot call shell channels and
the shell cannot call view channels. The offscreen render window is accepted as a second
legitimate view sender, and `vizzy:export:chunk` routes by job id to whichever surface owns
the running job.

### 3.2 Project files

- Location: `<userData>/projects/<slug>.camxora-vizzy.json` (`ensureAppDirs()` already creates it).
- Write: temp file → `fsync` → rename (atomic on NTFS/POSIX); pretty JSON + trailing newline.
- Read: size cap 64 MB, JSON parse, `format === "studio-project"`, `project` object,
  `nodes`/`layers` arrays. Anything else is rejected before it reaches the editor.
- Open outside `projects/` is refused unless `CAMXORA_E2E=1` (the harness needs a fixture path).

### 3.2.1 Saved video templates

```
<userData>/templates/<slug>/
  template.json   the exact studio-project snapshot the user previewed
  pipeline.json   kind, output, duration, bindings, requirements
  thumbnail.png   webContents.capturePage() at save time
```

- `vizzy:save-template` re-reads the live snapshot, captures the thumbnail, validates the
  user's binding selection against `collectBindingOptions()` and writes the three files through
  a temp directory + rename (`saveVideoTemplate()`); an existing id is never overwritten.
- `vizzy:preview-template` loads `template.json` through `vizzy:open-project-json`; the editor
  applies it with `applyProjectSnapshot`, so Preview is the same project, not a rebuild.
- `vizzy:render-template` calls `buildPipelineRenderPlan()`, opens the bound project, streams
  the run audio (`vizzy:load-audio` → `fetch(camxora-media://…)` → `editorLoadAudio`) and runs
  the normal export path. Output: `renders/<template-slug>-<timestamp>.mp4`.
- Delete/save emits `video-templates:changed`; the Templates rail and the Profiles template card
  re-read `video-templates:list`.

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
- **Run audio for templates.** `vizzy:load-audio` hands the editor a `camxora-media://` URL;
  the adapter fetches it inside the view (CSP `connect-src camxora-media:`) and calls the
  editor's own `editorLoadAudio`. The file is streamed from disk and never embedded in the
  project or sent through IPC as a payload.
- **Progress + cancel.** `runExport` is patched to forward its own frame counter and to
  read a host cancel flag in `shouldCancel`. Cancel aborts between frames, the host waits
  up to 5 s for the view to settle, then closes the handle and deletes the partial file
  itself. A 60-minute job ceiling does the same for a wedged encoder. Closing the editor,
  closing the window or a renderer crash cancels the job and removes its partial file.
  A route change only hides the view, so an active export keeps running.
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

## 3.5 Batch render (offscreen)

```
Music "Render videos"                         Progress "Video pipeline"
  → pipeline:enqueue (resolve templates+audio)      ← pipeline:list / pipeline:changed
  → pipeline:start
  → PipelineRunner.run()
      next queued row → buildPipelineRenderPlan
      → OffscreenVizzyRenderer.render()
          hidden BrowserWindow (vizzy-render partition)
          → vizzy:open-project-json (ack) → applyProjectSnapshot
          → vizzy:load-audio (camxora-media:// fetch) → editorLoadAudio
          → vizzy:export-run → editor runExport() → vizzy:export:chunk → renders/<slug>-<ts>.mp4
      → ffprobe → row done
      → batch merge (-c copy, re-encode fallback) → <run folder>/<batch>-merged.mp4 → ffprobe
```

- **Single exporter implementation.** `export-session.ts` owns the file handle, progress,
  cancel grace and cleanup for both surfaces; the visible editor and the batch window cannot
  drift apart.
- **Second sender.** `VizzyHost.isViewSender()` accepts the render window; the bridge is routed
  by sender and export chunks by job id. The page still runs with sandbox + no Node.
- **No shared storage.** The render window uses `partition: "vizzy-render"`, so the editor's
  autosave/localStorage cannot overwrite the user's visible session. Both custom schemes are
  installed on that partition (`installVizzyProtocolForSession`).
- **Lifecycle.** Created on demand, closed when the queue drains; disposing never deletes user
  files. Renderer crash / load failure fails the row with the reason.
- **Cancel.** Stop flag + `session.cancel`; queued rows are cancelled, the partial file is
  deleted, and a cancel during window load never starts an export.
- **Merge** is batch-level (`pipeline_batches`), so a row never pretends to be the merge.
- **Reel** is a separate render of the reel template; a profile without one is reported, not
  silently cropped.

---

## 4. Still stubbed

| Area | Status | Notes |
|---|---|---|
| Pipeline templates (`template.json`/`pipeline.json`) | **working (single template)** | Save from the preview, manage in the Templates rail, preview and render one saved template with a real run track. Batch selection per profile is stored and read from Profiles. |
| Native video export (MP4 + WebM) | **working** | Shell-owned job, editor-owned encoder, chunked to `renders/`, ffprobe-validated. MP4/H.264 is the reference path; WebM uses WebCodecs when the build has it. |
| Renders panel | **working** | List, inline playback, Reveal, Delete with confirmation. No thumbnails yet. |
| Batch render, merge/reel/upload | **partial** | Batch render, cancel/retry and long-form merge are **working** offscreen (no `/vizzy` needed). Reel is a separate render; a missing reel template is reported. **Upload is not built** — Auto-Upload stays disabled. |
| Export of a closed editor / headless render | **working (hidden window)** | The pipeline renders in a hidden `BrowserWindow` on its own partition; the visible editor never has to be attached. It is not a fully headless/offscreen (OSR) renderer, so a compositor/GPU is still required. |
| Media picker / `camxora-media://` inside the editor | **partial** | `pickMedia` still returns `null`, but the host can stream a run track into the editor through `vizzy:load-audio` (used by template renders). Background/logo bindings from `vizzy:render-template` use `camxora-media://` URLs. |
| 91-template library | **served when staged** | Preset/catalogue JSON is vendored. With `CAMXORA_VIZZY_LIBRARY_DIR` (or the packaged `vizzy-library/`), `/creations/*` is served from the staged pack and the editor's Creations browser lists all 91 with thumbnails; without it the browser is empty. |
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
npm --prefix vizzy ci
npm run vizzy:build
node scripts/sync-vizzy.mjs --check     # vendored tree matches UPSTREAM.md
npm run typecheck
npm run lint
npm test                                # 36 files / 278 tests
npm run build                           # includes build:vizzy-preload
node tests/e2e/vizzy.mjs                # ~25 s
node tests/e2e/vizzy-export.mjs         # ~40 s, writes export-settings.png + renders.png
node tests/e2e/vizzy-templates.mjs      # save → preview → render, writes save-dialog.png,
                                        # templates-panel.png, rendered-preview.png
$env:CAMXORA_VIZZY_LIBRARY_DIR="...\desktop-electron\vizzy-library"
node tests/e2e/vizzy-library.mjs        # 91 rows + one load, writes library.png
node tests/e2e/pipeline-batch.mjs       # offscreen batch + merge + cancel/retry (~30 s),
                                        # writes batch-progress.png + batch-complete.png
npm run test:e2e                        # all 15 suites (library needs the env above)
```

---

## 6. Known gaps and risks

| Item | Detail | Impact / next step |
|---|---|---|
| Rea's snapshot stores live analyser counters | `nodes[*].props.currentData`, `cumulativeData`, `cumMult` change every time the playhead moves, and a loaded particle node gains a null `particleTexture` cache slot, so two saves of the "same" project are not byte-identical. | The round-trip and template-preview assertions ignore exactly those runtime keys (`tests/e2e/vizzy.mjs`, `tests/e2e/vizzy-templates.mjs`). No authored state is ignored. Revisit if the snapshot format is ever owned by Camxora. |
| A saved template keeps the project's own name | `template.json` is the exact snapshot, so `project.name` stays whatever the previewed composition was called; the template name lives in `pipeline.json`. | The Templates rail uses `pipeline.name`; the editor strip shows `project.name`. Do not "fix" one from the other — it would break preview parity. |
| Settings template list can be up to 30 s stale | `useVideoTemplatesQuery` has a 30 s `staleTime`; it subscribes to `video-templates:changed` and invalidates, so a save/delete refreshes the Profiles list. | The list also refetches on mount; no action needed. |
| Dirty flag is history-depth based | Rea has no dirty flag. The adapter marks dirty when `editHistory.labels().length` differs from the depth at the last save/open. Undo back to the saved state stays "dirty". | Honest but coarse; a project hash in the adapter would be exact and cheap enough on demand. |
| Project file names are slug-based | Two projects with the same name share one file. | Add an id suffix (or a recent-project index) before the pipeline milestone needs many projects. |
| `detach()` destroys the view | Close or window close stops the editor; a route change only hides it so the live project survives. | The view is kept per window and throttled while hidden; the crash path still recreates it. |
| Export runs inside the attached editor | The job needs the live renderer and analyser state. | Route leave / window close / crash cancels the job and deletes the partial file. Batch renders use the hidden window instead. |
| One export at a time | Each surface keeps a single job; `pipeline:start` refuses a second batch while one runs. | Enough for the pipeline; concurrent renders would need one render window per worker. |
| Batch render needs a compositor | The hidden window is a real window (`show:false`), not an OSR renderer, so WebGL needs a usable GPU/compositor. | Verified on Windows; a fully headless CI would need `--disable-gpu` acceptance or an OSR renderer. |
| Merge has no percentage | ffmpeg concat runs as one process; the batch shows `merging` then `done`. | Add `-progress` parsing if merge time becomes visible to users. |
| Render outputs live in `renders/` | Only the merged long-form file is written to the run folder. | Keeps playback/reveal/delete on the managed surface; revisit if 1.7.1 folder parity is required. |
| Auto-Upload is intentionally absent | No upload/publish IPC exists for the pipeline. | Keep it that way until a dedicated, independently retryable upload stage is designed. |
| Music trigger needs downloaded songs | A song is queued only when the backend recorded a run folder and the download is done; the file is matched by title. | A renamed/ambiguous audio file is reported by name instead of guessed. |
| A template render needs the attached editor | The single-template action (`vizzy:render-template`) still uses the live editor. | Batch work does not; unify on the offscreen host if the rail action becomes batch-like. |
| Cancel has a 5 s grace | The host asks the editor to abort, then closes the handle and deletes the partial file itself. | A wedged encoder cannot leave a file behind; the editor's own UI settles a moment later. |
| Progress is frame-based | The editor reports `done/total` per rendered frame; the encode phase reuses the same counter. | Honest but coarse for the final mux; exact per-stage weights would need exporter changes. |
| Renders are listed without thumbnails | `listRenderFiles` reads name/size/mtime only; no poster frames. | Add a thumbnail pass (ffmpeg screenshot) when the library milestone needs previews. |
| `ffmpeg-core.wasm` is 32 MB inside `vizzy-dist` | Comes from `@ffmpeg/core` via the editor's exporter. | Still needed for the WebM/VPx fallback ladder and long webm exports; keep until the native path covers WebM too. |
| One privileged-scheme list per process | A second `registerSchemesAsPrivileged` call replaced the first, which broke `camxora-media://`. | Fixed with `registerHostSchemes()`, which registers both schemes in one call. If a third scheme appears, add it there — never call `registerSchemesAsPrivileged` twice. |
| `protocol.handle` streams every asset | `Range` is honoured for single ranges (video seeking, wasm streaming). | Multi-range requests fall back to the full body, which is the safe default. |
| The host is Windows-tested only | macOS/Linux packaging paths (`process.resourcesPath`) are implemented but unverified. | Re-run the E2E on each release platform; it is machine-checkable. |
| Native dialogs cannot be driven by Playwright | The E2E exercises `vizzy:open-path` (the same code path the dialog feeds). | The dialog itself is a 3-line wrapper (`openFromDialog`) with no branching. |
| Editor assets outside `public/` | `creations/` is not shipped inside the editor bundle, and `/audio/haende-hoch.mp3` is absent, so the editor boots on the synthetic analyser source. | The staged library is served separately from `CAMXORA_VIZZY_LIBRARY_DIR`; without it the Creations browser is empty. |
| Determinism is not measured yet | The saved-template render reuses the same project/renderer/analyser, but no repeat-render frame comparison exists. | Next milestone: render the same template/inputs twice and compare frames at tolerance. |
| A template render needs the attached editor | `vizzy:render-template` loads the plan into the live editor and runs its exporter. | Same constraint as Export; headless rendering is not built. |

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
| `tests/e2e/vizzy-templates.mjs`, `tests/e2e/vizzy-library.mjs` | save → preview → render harness; 91-template catalogue/load harness |
| `tests/unit/vizzy-project-store.test.ts`, `vizzy-protocol.test.ts`, `vizzy-renders.test.ts`, `vizzy-template-model.test.ts` | project, protocol, render/export and template-model unit tests |
| `tests/fixtures/vizzy/trap-motion.camxora-vizzy.json` | 31 KB round-trip fixture |
| `electron/shared/pipeline.ts` | new — pure binding options, selection, duplicate/incompatible validation, kind inference |
| `electron/services/pipeline-templates.ts` | binding option collection, palette detection (`color`/`fillStyle`), palette apply |
| `electron/services/pipeline-run.ts` | plan bitrate corrected to Mbps |
| `electron/services/video-templates.ts` | template store used by the new IPC (unchanged shape) |
| `electron/vizzy-host/host.ts` | `readSnapshot`, `captureTemplateSource`, `openProjectJson`, `loadAudioTrack`, `openCreationsBrowser`, `setVisible`, template output names |
| `electron/vizzy-host/renders.ts` | `renderFileNameForTemplate()` |
| `electron/ipc/vizzy.ts` | template options/save/preview/render, library, view visibility |
| `electron/ipc/video-templates.ts` | exports `toVideoTemplateInfo()`, emits `video-templates:changed` |
| `electron/vizzy-preload.ts`, `vizzy/patches/*` | `vizzy:load-audio` command + editor fetch/load handler |
| `electron/vizzy-host/assets.ts` | CSP `connect-src` allows `camxora-media:` for the streamed run track |
| `electron/main.ts` | library root from `resolveLibraryRoot()` (honours `CAMXORA_VIZZY_LIBRARY_DIR`) |
| `electron/preload.ts`, `src/lib/bridge.ts`, `electron/shared/types.ts` | template IPC typings + change event |
| `src/features/vizzy/*` | Save dialog, Templates rail, template model, templates hook, page integration |
| `src/features/settings/profiles-tab.tsx` | per-profile long/reel selectors + the full saved-template list |
| `package.json` | e2e includes `vizzy-templates.mjs`, `vizzy-library.mjs` and `pipeline-batch.mjs` |
| `electron/vizzy-host/export-session.ts` | new — shared export job (settings, file, progress, cancel, ffprobe) |
| `electron/vizzy-host/render-window.ts` | new — offscreen render host + dedicated partition |
| `electron/vizzy-host/host.ts` | delegates to the export session; accepts the render window as a view sender; `renderTemplateOffscreen` |
| `electron/vizzy-host/protocol.ts` | `installVizzyProtocolForSession()` for the render partition |
| `electron/services/pipeline-orchestrator.ts` | new — queue → render → ffprobe → merge, cancel/retry |
| `electron/services/pipeline-queue.ts` | merge intent, `output`, retry/cancel/batch helpers |
| `electron/services/pipeline-batch.ts` | per-batch merge, `PipelineCancelledError`, cancelled rows |
| `electron/services/pipeline-sources.ts` | new — run-folder audio resolution, unique merge path |
| `electron/services/database.ts` | migration 3: `pipeline_jobs.output_path`, `pipeline_batches` |
| `electron/ipc/pipeline.ts` | new — pipeline IPC + coalesced `pipeline:changed` |
| `electron/ipc/index.ts`, `electron/main.ts` | register pipeline IPC; install the render partition protocols |
| `electron/preload.ts`, `src/lib/bridge.ts`, `electron/shared/types.ts` | pipeline bridge + types |
| `src/features/progress/use-video-pipeline.ts`, `video-pipeline-table.tsx`, `video-pipeline-format.ts` | new — durable queue UI on Progress |
| `src/features/music/music-pipeline.ts`, `components/automation-card.tsx`, `views/music-page.tsx` | “Render videos” trigger, plan builder, Settings link |
| `tests/e2e/pipeline-batch.mjs` | new — offscreen batch, merge, Progress rows, cancel/retry |
| `tests/unit/pipeline-orchestrator.test.ts`, `pipeline-sources.test.ts`, `music-pipeline.test.ts`, `video-pipeline-format.test.ts` | new — orchestration, audio resolution, plan, formatting |
| `eslint.config.js` | ignores the vendored tree and its build output |
| `electron-builder.yml` | ships `vizzy-dist` as an extra resource |
| `.gitignore` | ignores `vizzy-dist/` |
