# Implementation Status

> **Updated:** 2026-11-19
> **Worktree:** `G:\Developments\Projects\Camxora Desktop`
> **Branch:** `desktop/electron-v1`
> **Phase:** P1 — Auth and shell (started; P0 foundation complete locally)

---

## Completed

| Task | Evidence |
|---|---|
| `T-P0-01` Electron/React/Vite scaffold | `desktop-electron/package.json`, `vite.config.ts`, esbuild main/preload build |
| `T-P0-02` Secure BrowserWindow | `contextIsolation: true`, `sandbox: true`, `nodeIntegration: false`, navigation allowlist |
| `T-P0-03` Typed IPC + Zod | `electron/ipc/index.ts`, `electron/shared/types.ts`, `electron/preload.ts` |
| `T-P0-04` Design primitives | Button, Input, Card, PageHeader, Badge, Dialog, Table, Toast, ErrorBoundary |
| `T-P0-05` OpenAPI types | `openapi.json` (940 paths), `src/lib/api-schema.d.ts`, `npm run api:types`, `npm run api:check` |
| `T-P0-06` API client in main | `electron/services/api-client.ts`, `api:request`, `/health` call from Foundation page |
| `T-P0-07` Session storage + refresh | `safeStorage`, encrypted `session.bin`, single-flight `/auth/refresh` |
| `T-P0-08` SQLite store + migrations | `node:sqlite`, `electron/services/database.ts`, `store.ts`, schema version 1 |
| `T-P0-09` Paths + file picker + media protocol | `paths.ts`, `files:pick`, `camxora-media://` token registry with range support |
| `T-P0-10` FFmpeg probe + transcode queue | `electron/services/ffmpeg.ts`, `ffmpeg:probe`, `ffmpeg:run`, `ffmpeg:cancel`, progress events |
| `T-P0-11` Logger + redaction + error boundary | JSONL logs, `redact.ts`, renderer console/load logging, `ErrorBoundary` |
| `T-P0-12` CI | `.github/workflows/desktop-electron.yml` (Windows, typecheck/lint/test/build/E2E) |
| `T-P0-13` Design baseline + shells | Tokens, Tailwind, shell, nine routes, professional foundation page |
| `T-P0-14` ADRs + plan | `docs/electron-desktop/*` |
| E2E smoke | `tests/e2e/smoke.mjs`, screenshot `artifacts/foundation.png` |
| Packaged build smoke | `npx electron-builder --win --dir`; `release/win-unpacked/Camxora.exe` launched |

### Verification run

```text
npm run typecheck   PASS
npm run lint        PASS
npm test            8/8 PASS
npm run build       PASS (renderer ~100 kB gzip JS)
npm run test:e2e    PASS (title "Camxora", version 2.0.0, session bridge, FFmpeg available)
npm run api:check   PASS (schema up to date)
npm audit --omit=dev  0 vulnerabilities
```

## Active workstreams (parallel)

| Worktree | Branch | Scope |
|---|---|---|
| `Camxora Desktop` | `desktop/electron-v1` | Integrator: shared files, reviews, merges |
| `Camxora Desktop Auth` | `desktop/auth` | Google OAuth, paid/email/onboarding gates |
| `Camxora Desktop Account` | `desktop/account` | Dashboard + Profile |
| ~~`Camxora Desktop Vizzy Host`~~ | ~~`desktop/vizzy-host`~~ | **Merged** — custom protocol recommended; see [`vizzy/HOST-SPIKE.md`](vizzy/HOST-SPIKE.md) |

Merge order and file ownership: [`WORKSTREAMS.md`](WORKSTREAMS.md).

## Phase 1 started

| Item | Status |
|---|---|
| Login screen | Implemented: email/password, remember me, loading/error, professional layout |
| Main-process login | `auth:login` against `platform_api`, token pair persisted via `safeStorage` |
| Session gate | `AuthGate` restores a session or shows login; sign-out returns to login |
| Dev/E2E bypass | `CAMXORA_DEV_AUTH=1`, only when `!app.isPackaged` |
| E2E | `smoke.mjs` (shell) + `login.mjs` (login) both pass; screenshots in `artifacts/` |
| Remaining P1 | Google OAuth, paid/onboarding gates, update gate, startup/onboarding polish |

## Vizzy host spike (merged)

- **Recommendation:** `camxora-vizzy://` custom protocol primary, tokenised loopback fallback.
- **Measured:** `crossOriginIsolated`, SharedArrayBuffer/Atomics, WebGL2 draw, classic+module
  worker, WASM/SIMD all true on both transports.
- **Gap fixed:** `camxora-media://` now sends `Cross-Origin-Resource-Policy: cross-origin`
  and `Access-Control-Allow-Origin: *`; CORS enabled on the scheme.
- **Range/HEAD verified:** `tests/e2e/media.mjs` returns HTTP 206 for `bytes=10-19/256`,
  correct bytes, and a valid HEAD response.
- **Still to prove:** real Rea bundle, macOS/Linux and SwiftShader.
- Details: [`vizzy/HOST-SPIKE.md`](vizzy/HOST-SPIKE.md).

## Remaining before Phase 0 exit

- Updater skeleton (electron-updater wiring).
- App icon/signing configuration for the installer.
- Optional: renderer crash screenshot/recovery verification.
- CI first run verification on GitHub.
- FFmpeg was detected on the development machine; verify the bundled-binary path on a clean VM.
- Packaged NSIS installer (the unpacked directory build is verified).

## Notes

- Electron userData is isolated at `%APPDATA%\Camxora Desktop`, so the legacy
  `%APPDATA%\Camxora` PySide6 data is untouched.
- Electron 45.4.1, React 19, Vite 7, Tailwind 3.4, TypeScript 5.9.
- The store uses Node 24's `node:sqlite` (experimental warning). It is behind
  `electron/services/database.ts`; swap to `better-sqlite3` if packaging proves unstable.
- Dev audit has 6 moderate advisories from `electron-builder`/`minimatch`; production audit is
  clean.
- Nothing has been committed or pushed yet.

## Decisions locked

1. **All 91 templates** are in scope and available to users.
2. **Pipeline renders the preview the user saves** with “Save as video template”; bindings are
   auto-detected with optional overrides.
3. **Auto-Upload keeps 1.7.1 behavior** (toggle disabled; existing publication/manual flow).
4. **Old Camxora video templates are not migrated** in 2.0.0.
5. **Vizzy is hosted, not rewritten**; the Electron shell and pipeline are new code.

## Remaining P7 decision

- 91-template delivery: first-run **“Vizzy Templates” pack** (recommended) or bundle in the
  installer. Licensing/asset clearance must be recorded before public release.
