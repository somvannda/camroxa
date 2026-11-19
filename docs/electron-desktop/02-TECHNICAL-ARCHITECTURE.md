# Technical Architecture — Camxora Desktop (Electron)

> **Document ID:** CAMXORA-ED-02
> **Version:** 1.0.0
> **Status:** Draft for approval
> **Owner:** Desktop engineering
> **Last updated:** 2026-11-19

---

## 1. Stack

> **Release target:** Camxora Desktop **2.0.0**. All phases ship into 2.0.0; only internal
> build metadata increments. See [`08-RELEASE-2.0.0.md`](08-RELEASE-2.0.0.md).

| Layer | Choice | Notes |
|---|---|---|
| Runtime | **Electron 37+** (Chromium + Node 22) | Match the Chromium version used by `camxora.com` where possible |
| UI | **React 19 + TypeScript 5** | Function components, strict TS |
| Build | **Vite 7** | Fast HMR, separate bundles for shell and Vizzy |
| Styling | **Tailwind CSS 3.4 + CSS variables** | Tokens in [`06-DESIGN-SYSTEM.md`](06-DESIGN-SYSTEM.md) |
| Primitives | **Radix UI** (dialog, menu, popover, select, tabs, tooltip) | Accessible by default |
| Icons | **Lucide** | One set, 16/18 px, 1.5 stroke |
| Routing | **React Router 7** (memory/hash) | Electron has no server-side routes |
| Data | **TanStack Query 5** | Caching, polling, retries, stale states |
| Local UI state | **Zustand** | Session, layout, preferences, transient UI |
| Forms | **React Hook Form + Zod** | Same schemas validate IPC payloads in main |
| Tables | **TanStack Table 8** (headless) | Dense desktop tables, sticky headers |
| Charts | **Custom SVG/canvas** | No chart dependency for the dashboard; precise control |
| API types | **openapi-typescript** from `platform_api/openapi.json` | Generated, checked in, regenerated in CI |
| Local store | **better-sqlite3** + JSON manifests | Metadata in SQLite; blobs on disk |
| Media | **FFmpeg/ffprobe** static binaries | Spawned from main; progress over IPC |
| Packaging | **electron-builder** | NSIS (Windows), DMG (macOS), AppImage/deb (Linux) |
| Updates | **electron-updater** | Signed, staged, mandatory-gate aware |
| Tests | **Vitest** (unit), **Playwright + Electron** (E2E), **axe** (a11y) | See QA doc |

**Why not Next.js in Electron?** The desktop is a long-lived single-window app. A Vite SPA
with a memory router starts faster and avoids shipping a Node server inside the app. We
reuse design tokens and presentational components from `camxora.com`, not its server
components.

---

## 2. Process model

```
┌─────────────────────────────────────────────────────────────────────┐
│ Electron main (Node)                                                │
│  • window lifecycle, single instance, deep links                    │
│  • API client + auth/session + token refresh (OS-encrypted)         │
│  • IPC router (Zod-validated)                                       │
│  • files, media protocol, FFmpeg jobs, SQLite, templates            │
│  • background coordinators (downloads, pipeline, sync, updates)     │
│  • updater, notifications, diagnostics, crash logging               │
└───────────────┬─────────────────────────────────────────────────────┘
                │ contextBridge (preload)
                │ window.camxora.*  (typed, narrow)
┌───────────────▼─────────────────────────────────────────────────────┐
│ Renderer shell (React)                                              │
│  • auth gate, shell chrome, routes, pages                           │
│  • TanStack Query reads through window.camxora.api                  │
│  • no Node, no tokens, no direct filesystem                         │
└───────────────┬─────────────────────────────────────────────────────┘
                │ WebContentsView (separate process)
┌───────────────▼─────────────────────────────────────────────────────┐
│ Vizzy host (Rea bundle)                                             │
│  • existing editor: DOM, three.js/WebGL, WebAudio, ffmpeg.wasm      │
│  • bridge: postMessage ↔ main IPC for open/save/export/media        │
│  • is isolated: a crash reloads the view, not the shell             │
└───────────────┬─────────────────────────────────────────────────────┘
                │ offscreen render host (pipeline)
┌───────────────▼─────────────────────────────────────────────────────┐
│ Vizzy pipeline renderer (Rea bundle, headless)                      │
│  • loads a pipeline template + run bindings                         │
│  • deterministic project-time audio analysis                        │
│  • renders frames at export resolution → ArrayBuffer → FFmpeg       │
│  • batch workers, progress/cancel/retry, validation                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Pipeline process model

The pipeline is **not** a separate renderer. It is the same Rea renderer in a headless
Electron render host, driven by the main-process pipeline service:

- main resolves the job (template, audio, background, logo, text, output);
- the render host loads the Vizzy project and applies the bindings;
- frames are rendered at export resolution and returned as `ArrayBuffer`;
- main writes/encodes with FFmpeg, validates with `ffprobe`, then merges/reels/uploads.

The contract, determinism rules, job model and budgets are in
[`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).

### 2.1 Why a separate Vizzy view

Rea is a vanilla TypeScript app that owns `document.body`, global CSS and a canvas. Mounting
it inside the React shell would cause CSS/DOM conflicts and a shared crash domain. A
`WebContentsView` (or a dedicated `BrowserWindow` child) gives:

- the exact Rea runtime (COOP/COEP, SharedArrayBuffer, WebGL) without React interference;
- an independent crash/reload boundary;
- a clean bridge surface (`openProject`, `saveProject`, `export`, `pickMedia`);
- the option to move Vizzy to its own window later.

The shell reserves a rectangular region and attaches the view. On route change, detach and
destroy it after the project is saved or the user confirms.

---

## 3. Repository layout

```
desktop-electron/
  package.json
  electron-builder.yml
  tsconfig.json
  vite.config.ts
  electron/
    main.ts                  # app lifecycle, windows, protocol, single instance
    preload.ts               # contextBridge API
    ipc/
      index.ts               # typed router
      auth.ts
      api.ts
      files.ts
      media.ts
      ffmpeg.ts
      templates.ts
      vizzy.ts
      pipeline.ts
      diagnostics.ts
      updates.ts
    services/
      session.ts             # tokens, refresh, saved accounts
      api-client.ts          # fetch wrapper, retries, error envelope
      store.ts               # SQLite + migrations
      paths.ts               # managed dirs, safe path checks
      ffmpeg.ts              # jobs, progress, cancel
      pipeline/
        orchestrator.ts      # job queue, stage machine, retry/resume
        render-host.ts       # offscreen Vizzy render workers
        bindings.ts          # template + run binding
        merge.ts             # concat, reel, validation
        upload.ts            # YouTube publish hand-off
        templates.ts         # Vizzy pipeline template store + validation
      coordinators/          # downloads, pipeline recovery, image sync, progress sync
      updates.ts
      notifications.ts
      logger.ts              # structured, redacted, rotated
      crash.ts
    vizzy-host/
      server.ts              # loopback or custom-protocol host
      bridge.ts              # postMessage protocol
  src/
    main.tsx
    app.tsx
    router.tsx
    shell/
      titlebar.tsx
      sidebar.tsx
      footer.tsx
      command-palette.tsx
      notifications.tsx
    features/
      auth/
      dashboard/
      profile/
      progress/
      music/
      image/
      vizzy/
      pipeline/              # Renders panel, job detail, shared pipeline widgets
      marketplace/
      settings/
    components/              # design-system primitives
    lib/
      api.ts                 # typed client over window.camxora.api
      query.ts               # query keys, polling defaults
      format.ts
      guards.ts
    styles/
      tokens.css
      globals.css
  vizzy/                     # built from the Rea source (see vizzy/02-MODULE-MAP.md)
    index.html
    assets/
  resources/
    ffmpeg/
    fonts/
    icons/
  tests/
    unit/
    e2e/
```

`desktop-electron/` is a new top-level folder in the monorepo. It does **not** import
`camxora_python`; it talks to `platform_api` like any other client. Shared TypeScript types
may be copied from `camxora.com/lib` when they already match the API contract.

---

## 4. Security model

| Control | Requirement |
|---|---|
| `contextIsolation` | `true` |
| `sandbox` | `true` for the shell; `false` only if a Vizzy requirement forces it (document why) |
| `nodeIntegration` | `false` |
| Preload surface | Explicit allowlist of typed functions; no `ipcRenderer` exposure |
| IPC validation | Every handler parses input with a Zod schema; unknown channels throw |
| Navigation | `will-navigate` blocked except allowlisted origins; `setWindowOpenHandler` opens external URLs in the system browser |
| CSP | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: camxora-media:; media-src 'self' camxora-media:; connect-src 'self'` |
| Remote content | None. Marketplace previews are fetched through main and served from a managed cache |
| Tokens | Main process only; encrypted with `safeStorage`; never logged |
| Files | Paths resolved under allowlisted roots; symlink checks; no arbitrary `fs` from renderer |
| FFmpeg | Arguments built as arrays, never shell strings; output paths validated |
| Updates | Signature verified; HTTPS only; rollback on failed install |
| Permissions | Deny camera/mic/geolocation by default; allow notifications only |
| DevTools | Disabled in production; enabled with `CAMXORA_DEVTOOLS=1` |

### 4.1 Token and session flow

```
Renderer                Main                         platform_api
   │  login(email,pw)      │                              │
   ├──────────────────────►│  POST /auth/login             │
   │                      ├─────────────────────────────►│
   │                      │◄──── access + refresh ───────┤
   │                      │  safeStorage.encrypt(refresh)│
   │◄── session summary ──┤  access token kept in memory  │
   │                      │                              │
   │  api.get('/users/me')│                              │
   ├──────────────────────►│  attach Bearer, send         │
   │                      ├─────────────────────────────►│
   │                      │◄──── 401 ────────────────────┤
   │                      │  refresh once, retry once    │
   │◄──── data ───────────┤                              │
```

- One in-flight refresh (single-flight). A 401 triggers at most one refresh; concurrent
  requests await the same promise.
- Refresh-token rotation is adopted atomically. If the server rotates and the app crashes
  mid-write, the next start falls back to the last known-good token and then to login.
- `Remember me` stores the refresh token in the OS keystore. Without it, tokens live only for
  the session.
- Saved accounts are a list of user summaries (id, email, display name, avatar) with no
  tokens. Selecting one starts a fresh login or a stored refresh flow.
- Logout clears tokens, in-memory access, query cache and all per-user local caches; it does
  **not** delete user files.

### 4.2 Google OAuth

1. Main starts a loopback HTTP listener on `127.0.0.1` with an ephemeral port and a random
   state value.
2. `shell.openExternal` opens the platform's Google authorization URL with
   `redirect_uri=http://127.0.0.1:<port>/callback`.
3. The listener accepts exactly one callback, validates `state`, exchanges the code in main,
   and closes.
4. The renderer receives only the resulting session summary.
5. Timeout: 3 minutes; the user can cancel from the login screen.

If the backend requires a fixed redirect URI, use the same one as `music.camxora.com` and a
custom `camxora://auth/callback` protocol as the fallback.

---

## 5. IPC contract

All channels are namespaced and typed. The table is the contract; adding a channel requires a
Zod schema and a test.

| Channel | Direction | Payload | Returns |
|---|---|---|---|
| `auth:login` | R→M | `{ email, password, remember }` | `SessionSummary \| AuthError` |
| `auth:google` | R→M | `{}` | `SessionSummary \| AuthError` |
| `auth:register` | R→M | `{ email, password, displayName }` | `SessionSummary \| AuthError` |
| `auth:logout` | R→M | `{}` | `void` |
| `auth:saved-accounts` | R→M | `{}` | `SavedAccount[]` |
| `auth:switch` | R→M | `{ userId }` | `SessionSummary \| AuthError` |
| `auth:restore` | R→M | `{}` | `SessionSummary \| null` |
| `api:request` | R→M | `{ method, path, query?, body?, timeoutMs? }` | `{ status, data, headers }` |
| `api:upload` | R→M | `{ path, name, mime, fields? }` | `{ status, data }` |
| `files:pick` | R→M | `{ kind: 'file'\|'dir', filters?, multiple? }` | `string[]` |
| `files:open` | R→M | `{ path }` | `void` |
| `files:reveal` | R→M | `{ path }` | `void` |
| `files:ensure-dir` | R→M | `{ path }` | `void` |
| `files:read-image` | R→M | `{ path }` | `{ bytes: Uint8Array, mime }` |
| `media:url` | R→M | `{ path }` | `camxora-media://...` |
| `ffmpeg:probe` | R→M | `{ path }` | `MediaInfo` |
| `ffmpeg:run` | R→M | `FfmpegJob` | `{ jobId }` |
| `ffmpeg:cancel` | R→M | `{ jobId }` | `void` |
| `templates:list/install/delete` | R→M | template id/path | `TemplateRecord` |
| `vizzy:open` | R→M | `{ projectPath? }` | `{ viewId }` |
| `vizzy:save` | R→M | `{ projectPath, bytes }` | `void` |
| `vizzy:export` | R→M | `ExportRequest` | `{ jobId }` |
| `diagnostics:send` | R→M | `{ note? }` | `{ uploadId }` |
| `updates:check` | R→M | `{}` | `UpdateOffer \| null` |
| `updates:install` | R→M | `{ version }` | `{ started }` |
| `app:info` | R→M | `{}` | `{ version, env, platform }` |

**Events (M→R):** `ffmpeg:progress`, `ffmpeg:done`, `ffmpeg:failed`, `download:progress`,
`pipeline:changed`, `update:available`, `update:progress`, `session:expired`,
`notification:show`, `vizzy:request`.

Every handler returns a discriminated result; never throw raw errors across IPC. The error
shape is `{ code, message, detail?, retryable? }`.

---

## 6. API client

### 6.1 Base URL

| Build | API base |
|---|---|
| production | `https://api.camxora.com/api/v3` |
| sandbox | `https://api.sandbox.camxora.com/api/v3` |
| local | `http://127.0.0.1:8000/api/v1` or `:8100` (configurable by env) |

The renderer never sees the base URL; it requests paths such as `/users/me`.

### 6.2 Behaviour

- JSON by default; multipart for uploads.
- Timeout 30 s for reads, 120 s for generations, 600 s for exports.
- Retry `GET` on network errors and 5xx with exponential backoff (3 attempts, jitter).
  Never retry a mutation automatically.
- Unwrap the platform error envelope into `ApiError` with `status`, `code`, `message`,
  `requestId`.
- Emit `session:expired` when refresh fails; the shell returns to login without losing the
  current route intent.
- Query keys are centralised in `src/lib/query.ts`; polling intervals live with the page.

### 6.3 Type generation

`platform_api` exposes `/openapi.json`. CI runs:

```bash
curl -fsS http://127.0.0.1:8000/openapi.json -o openapi.json
npx openapi-typescript openapi.json -o src/lib/api-schema.d.ts
npx tsc --noEmit
```

The generated file is committed. A schema drift check fails the build.

---

## 7. State and storage

### 7.1 Renderer state

| Concern | Tool |
|---|---|
| Server data | TanStack Query (cache, polling, invalidation) |
| Session summary | Zustand + a small persisted slice |
| Route/layout/theme | Zustand + `localStorage` (non-sensitive) |
| Form state | React Hook Form |
| Transient UI (dialogs, toasts) | Zustand or local state |

Never duplicate server data into Zustand. If a value comes from the API, it lives in Query.

### 7.2 Main-process storage

| Data | Location | Format |
|---|---|---|
| Session/tokens | `app.getPath('userData')/session.bin` | `safeStorage` encrypted |
| Saved accounts | `userData/accounts.json` | JSON, no tokens |
| Settings cache | `userData/cache/settings.json` | JSON, per user |
| Workspace cache | `userData/cache/<userId>/*.json` | JSON, per page |
| Templates | `userData/templates/<uid>/` | `template.json` + assets |
| Projects (Vizzy) | user-chosen folder; recent list in SQLite | `.camxora-vizzy.json` |
| Media cache | `userData/media-cache/` | content-addressed by SHA-256 |
| Image cache | `userData/image-cache/` | per user/run |
| Logs | `userData/logs/` | rotated JSONL |
| Crash dumps | `userData/crashes/` | minidump + JSON |
| SQLite DB | `userData/camxora.db` | migrations in `electron/services/store/migrations` |

Use WAL mode, foreign keys, and a schema version. A migration failure disables only the
affected feature, not the whole app.

### 7.3 Cache policy

- Query cache: 30 s stale for lists, 5 min for profiles/settings, infinite for static
  catalogues until invalidated.
- Workspace cache: written on successful load; used as the first paint when the network is
  slow; marked `staleAt` and refreshed in the background.
- On account switch: clear all per-user caches, never the user's files.

---

## 8. Files, media and FFmpeg

### 8.1 Managed directories

```
userData/
  downloads/        # Suno MP3s
  renders/          # video/merge outputs
  images/           # generated backgrounds/thumbnails
  templates/        # installed marketplace templates
  projects/         # default Vizzy project folder
  cache/
  logs/
```

The user may point the Suno output root elsewhere (Settings → Preferences). All other
managed folders stay under `userData` unless the user changes them.

### 8.2 Serving local media to the renderer

Register a privileged scheme:

```ts
protocol.registerSchemesAsPrivileged([
  { scheme: 'camxora-media', privileges: { standard: true, secure: true, supportFetchAPI: true } }
]);
```

`protocol.handle('camxora-media', ...)` maps an opaque token to an allowlisted absolute path,
streams the file with the correct MIME and range support, and refuses anything outside the
allowlist. The renderer never receives a raw `file://` URL.

### 8.3 FFmpeg jobs

- One queue in main with a configurable concurrency (default 2).
- Jobs are `{ id, kind: 'video'|'merge'|'audio'|'probe', inputs, output, args }`.
- Progress is parsed from `-progress pipe:1` and emitted as `{ jobId, frame, fps, timeMs,
  percent }`.
- Cancel sends `q`/SIGTERM, then kills after 5 s; partial outputs are deleted.
- Every job writes a JSON sidecar with the exact argv, codec, duration and result for
  support.
- FFmpeg binaries are verified by SHA-256 at build time and on first run.

### 8.4 Codec fallback ladder (native)

1. H.264 + AAC in MP4 (`libx264`, `-pix_fmt yuv420p`).
2. MPEG-4 + AAC in MP4.
3. VP9 + Opus in WebM.
4. VP8 + Vorbis in WebM.

Hardware encoders (`h264_nvenc`, `h264_qsv`, `h264_amf`) are optional and only used when a
probe succeeds; the output is validated before it is reported as done.

---

## 9. Vizzy host

### 9.1 Build

- Rea is copied/built from `G:\Developments\Rea\editor` into `desktop-electron/vizzy/` by a
  reproducible script (`scripts/build-vizzy.mjs`).
- `base: './'` so assets load from a custom scheme.
- Source maps are generated for diagnostics but excluded from the shipped installer.
- Public assets are pruned: keep fonts, icons, vendor shaders, lottie and the reference
  projects used for tests; the 91-template library (14.2 MB JSON + 265.6 MB media) ships as a
first-run pack by default, or bundled if product accepts the installer size.
- Templates are lazy-loaded from the local template store or marketplace.

### 9.2 Serving

Preferred: a custom `camxora-vizzy://` scheme with COOP/COEP headers:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
Cross-Origin-Resource-Policy: cross-origin
```

If Electron cannot provide `crossOriginIsolated` reliably over the custom scheme, fall back
to a loopback HTTP server on `127.0.0.1:<random>` with a random path token and the same
headers. The server is bound to localhost, accepts only the token, and shuts down with the
view.

### 9.3 Bridge protocol

```ts
// shell -> vizzy
{ type: 'vizzy:open', project: unknown }
{ type: 'vizzy:new', resolution: { width, height } }
{ type: 'vizzy:export', options: ExportOptions }
{ type: 'vizzy:theme', tokens: Record<string, string> }

// vizzy -> shell
{ type: 'vizzy:ready' }
{ type: 'vizzy:dirty', dirty: boolean }
{ type: 'vizzy:save', bytes: ArrayBuffer, name: string }
{ type: 'vizzy:pick-media', kind: 'image'|'video'|'audio' }
{ type: 'vizzy:export-progress', jobId, percent }
{ type: 'vizzy:export-done', jobId, path }
{ type: 'vizzy:error', message, stack? }
```

Messages are validated on both sides. Binary payloads use `ArrayBuffer` transfer, not base64,
except where the existing Rea API requires base64.

### 9.4 Project I/O

- Native project format: the Rea project snapshot JSON (`.camxora-vizzy.json`).
- Import: Vizzy project export JSON, spectrum preset JSON, creation/template JSON.
- Autosave: debounced 2 s to a recovery folder; a crash prompts "Restore last autosave".
- Recent projects: SQLite table with path, name, thumbnail, last opened, duration.
- Save As: native dialog, validated extension, atomic write (temp + rename).

### 9.5 Export

Export step A uses the existing Rea exporter (ffmpeg.wasm) so behaviour is unchanged while
the host is being proven. Export step B routes frames through the main-process native
exporter and is the release path:

1. Vizzy renders frames at export resolution and posts `RGBA` buffers.
2. Main writes raw frames to a temp file / pipe and runs FFmpeg.
3. Progress and cancel are bridged.
4. Audio is muxed from the decoded track, with the project's audio settings applied.

The native path is the release path; wasm remains a fallback only if the native probe fails.

### 9.6 Crash isolation

The Vizzy `WebContentsView` has its own `render-process-gone` handler. On crash:

- keep the shell alive;
- show "Vizzy stopped responding" with **Reload** and **Save recovery**;
- restore the last autosave on reload;
- log the crash with the project id, not the project contents.

### 9.7 Pipeline render host

The automation pipeline reuses the Vizzy renderer in a **headless render host**:

- a hidden `BrowserWindow`/`WebContentsView` loads the same Vizzy bundle;
- the project is a **Vizzy-native** pipeline template (`template.json` + `pipeline.json`);
- old 1.7.1 Camxora video templates are **not** accepted and are not converted;
- bindings replace audio, background, logo, text and palette;
- the renderer seeks by project time and returns frames as `ArrayBuffer`;
- main encodes with native FFmpeg and validates with `ffprobe`.

The pipeline is a stage machine (`queued → rendering → encoding → merging → uploading →
done`), persisted in SQLite, with retry/resume and per-stage failure isolation. The full
contract is in [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).

---

## 10. Background coordinators

These run in the main process and are independent of the visible route:

| Coordinator | Interval | Responsibility |
|---|---|---|
| Music downloads | 4 s with pending, 12 s idle | Poll `/music/downloads/pending`, download MP3s, POST `/music/downloads/sync` |
| Pipeline recovery | 60 s | Find missing local files, re-fetch, mark run state |
| Image output sync | 30 s | Sync generated image paths/status to the platform |
| Progress local sync | 60 s | Reconcile local run state with `/progress` |
| Video pipeline | event-driven | **2.0.0.** Drive render/merge/reel/upload jobs on the Vizzy renderer and report stages. See [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md). |
| Workspace prefs sync | on change, debounced 1 s | Push desktop preferences to `/settings` |
| Updates | 6 h + on start | Check release channel; respect mandatory gate |
| Notifications | persistent WebSocket/SSE | Show OS notifications and in-app toasts |

Each coordinator has: single-flight guard, backoff, pause when offline, a status row in
Diagnostics, and a kill switch in Settings.

---

## 11. Updates and packaging

### 11.1 Windows

- `electron-builder` NSIS, per-user install by default, optional machine-wide.
- Code signing via the organisation's certificate (EV or Azure Trusted Signing).
- `appId: com.camxora.desktop`, `productName: Camxora`.
- Protocol: `camxora://`.
- Installer checks: no running instance, disk space, VC++ runtime if needed.
- Uninstall keeps user projects and settings unless "remove local data" is checked.

### 11.2 Update flow

1. Main checks the release manifest at start and every 6 h.
2. If newer, download in the background; show a quiet "Update ready" affordance.
3. Security/mandatory releases show a blocking gate with progress; the user cannot skip.
4. On install, close child processes (FFmpeg, Vizzy view), write a marker, run the helper,
   relaunch.
5. On start, verify the new version. If the install failed, surface the persisted error and
   offer a manual download.

### 11.3 Channels

`sandbox` (default for development), `beta`, `stable`. The channel is baked into the build
and not user-editable.

---

## 12. Observability

- **Logs:** JSONL, one file per day, 7-day retention, redaction of tokens, emails, cookies
  and absolute paths outside the app root.
- **Renderer errors:** caught by an error boundary + `window.onerror`; forwarded to main
  with a breadcrumb, never a full project payload.
- **Crash dumps:** `crashReporter` with upload disabled by default; a user-triggered
  diagnostics send includes the last crash summary.
- **Diagnostics:** `diagnostics:send` packages logs, app/OS info, feature flags and a user
  note; it previews the redacted bundle size before upload.
- **Metrics:** local counters only (route visits, job durations, error codes). No third-party
  analytics in 2.0.0 without an explicit product decision.

---

## 13. Performance budgets

| Scenario | Budget |
|---|---|
| Shell JS (gzip) | ≤ 350 KB initial route |
| Vizzy bundle (gzip) | ≤ 1.5 MB JS + assets lazy |
| Route chunk | ≤ 150 KB gzip |
| Dashboard chart paint | ≤ 16 ms per update |
| Music history (500 rows) | ≤ 100 ms filter/sort |
| Progress poll update | ≤ 50 ms reconcile |
| Image preview decode | off-main-thread, ≤ 100 ms for 2 MP |
| Vizzy stage | 60 fps at 1080p on a mid-range GPU; 30 fps floor |
| Idle CPU | ≤ 3 % |
| Memory | ≤ 450 MB after five routes |

---

## 14. Build and CI

```bash
npm ci
npm run typecheck
npm run lint
npm run test:unit
npm run build            # shell + vizzy
npm run test:e2e         # Playwright + Electron
npm run package:win      # electron-builder
```

CI gates:

1. Typecheck + lint + unit tests.
2. OpenAPI drift check.
3. Build shell and Vizzy.
4. Playwright smoke on a Windows runner (login, dashboard, music, vizzy open/export).
5. Dependency audit (`npm audit --omit=dev`) with an allowlist.
6. Installer checksum + signature verification.
7. Artifact retention: 30 days; release artifacts 1 year.

No deploy job in this program. Packaging produces a local artifact only.

---

## 15. Architecture decisions

See [`05-RISKS-DECISIONS.md`](05-RISKS-DECISIONS.md) for the full ADR list. The load-bearing
ones are:

- ADR-001 Electron + React + Vite.
- ADR-002 Host Rea in a `WebContentsView`.
- ADR-003 Tokens and API calls live in main.
- ADR-004 Native FFmpeg.
- ADR-005 SQLite for metadata, files for blobs.
- ADR-006 Design refresh, feature parity.
- ADR-007 Vizzy is the only 2.0.0 video engine; the pipeline renders on the same renderer, with no Python sidecar.
