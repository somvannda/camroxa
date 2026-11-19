# Camxora Desktop 2.0.0 — Electron

Phase 0 foundation for the Electron rebuild.

## Run

```bash
npm install
npm run dev        # Vite + Electron
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e     # launches Electron via Playwright
```

The E2E smoke writes `artifacts/foundation.png`.

The API base defaults to `http://127.0.0.1:8000/api/v1`. Override it with
`CAMXORA_API_BASE_URL`.

## Phase 0 scope

- Electron window with a typed, sandboxed preload bridge.
- Main-process API client with auth injection and single-flight refresh.
- OS-encrypted session storage (`safeStorage`).
- Managed app directories and structured logs with redaction.
- React shell, routes and design tokens.
- Foundation page that proves bridge, metadata and API health.
- CI scripts for typecheck, lint, unit tests and build.

## Deliberate boundaries

- **Vizzy is hosted, not rewritten.** The Rea editor is vendored/built and mounted in a
  `WebContentsView` in P7; the core renderer and project model are not rewritten.
- **No legacy Camxora video-template migration in 2.0.0.** The pipeline uses Vizzy-native
  pipeline templates.
- **Old Video/Merger pages are removed.** Their capabilities are the 2.0.0 pipeline.
- **SQLite, media protocol, FFmpeg jobs and updater** land later in Phase 0/P9; the
  foundation keeps the interfaces explicit.

## Structure

```
electron/
  main.ts           window lifecycle, security, navigation
  preload.ts        contextBridge API
  ipc/              typed IPC router
  services/         api-client, session, logger, paths, redact
  shared/           shared types
src/
  shell/            title bar, sidebar, footer, routes
  components/       design-system primitives
  features/         page surfaces
  lib/              bridge types, API wrapper, formatting
  styles/           tokens and globals
tests/unit/         pure-logic tests
```
