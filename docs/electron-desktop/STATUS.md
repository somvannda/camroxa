# Implementation Status

> **Updated:** 2026-11-19
> **Worktree:** `G:\Developments\Projects\Camxora Desktop`
> **Branch:** `desktop/electron-v1`
> **Phase:** P1 auth complete (update gate shipped); P2 Dashboard/Profile/Settings merged; P3–P6 pages merged

---

## Completed

| Area | Evidence |
|---|---|
| Electron/React/Vite foundation | Secure window, typed IPC modules, design tokens, shell, nine routes |
| API client + OpenAPI | Main-process client, 940-path schema, drift check |
| Session storage | `safeStorage`, remember-me, single-flight refresh, saved account summary |
| SQLite store | `node:sqlite`, migrations, templates/projects/jobs tables |
| Media protocol | tokenised `camxora-media://`, CORP/CORS, Range/HEAD E2E |
| FFmpeg | probe, transcode queue, progress/cancel, E2E availability |
| Logging/diagnostics | JSONL, redaction, renderer console/load logging, error boundary |
| CI | Windows workflow: typecheck/lint/test/build/E2E |
| Packaging | unpacked Windows build launched |
| **P1 auth** | Email/password, remember-me, Google OAuth loopback, paid gate, email-confirmation gate, onboarding gate, sign-out, dev/E2E bypass |
| **P1 updates** | HTTPS release manifest, mandatory blocking gate, optional update card, download hand-off, unit + E2E coverage |
| **P2 account** | Dashboard (KPIs, weekly chart, quota, activity) and Profile (account, membership, channels, activity) |
| **P2 settings** | Profiles (list/create/edit/delete, allowance, media, YouTube), Publication (visibility, schedule, playlists, metadata), Preferences (FFmpeg, output dir, workers, thumbnails, diagnostics) |
| **P7 host spike** | `camxora-vizzy://` + loopback, all isolation/WebGL/worker/WASM checks pass; see [`vizzy/HOST-SPIKE.md`](vizzy/HOST-SPIKE.md) |

### Verification

```text
npm run typecheck      PASS
npm run lint           PASS
npm test               147/147 PASS
npm run build          PASS (shell 331 kB / 103 kB gzip, pages split)
npm run test:e2e       PASS (smoke, login/gates, media, account, progress, progress-retry, music, image-marketplace, settings, update)
npm run api:check      PASS
npm audit --omit=dev   0 vulnerabilities
npx electron-builder --win --dir   PASS (unpacked app launched)
```

E2E screenshots: `desktop-electron/artifacts/` (dashboard/profile success, empty, error; login; auth gates).

## Brand alignment

The desktop now uses the real camxora.com brand assets and tokens:

- original `camxora-logo.svg` in the title bar and auth frame (no letter tile);
- Inter Variable (bundled) + Niradei for Khmer;
- Font Awesome 6 solid icons (replacing Lucide);
- `#070a13` page / `#0a0d18` sidebar / `#0f1322` panels / `#181f36` controls;
- `#a855f7` accent and the `#7c3aed → #a855f7` brand gradient for the primary CTA and mark;
- camxora.com type scale (11–30 px, 28 px page title) and 34/36/44 control heights;
- 256 px desktop sidebar.

The web's glass/blur treatments are intentionally not copied onto chrome; the gradient is
reserved for the logo and the one primary CTA.

## Open API gap

`/licenses/validate` is **not present in the current `platform_api` OpenAPI**. The account pages
degrade to `null` and fall back to `/users/me` + `/stats/dashboard`; plan expiry will show
“Not provided” until the endpoint exists or the licence fields move to an existing endpoint.
This is a backend contract decision, not a renderer bug.

## Merge history

- `10993c2` foundation
- `a7892b3` Vizzy host spike
- `6fdaef8` media range/CORS verification
- Auth merge (`c771a18`) — Google OAuth + bootstrap gates
- Account merge (`ed6a7d5`) — Dashboard + Profile
- `a982e63` brand alignment
- Wave 2: Progress `8d52316`, Music `950ae2b`, Image/Marketplace `4282787`
- `e908a88` Font Awesome sweep + lazy routes
- `e25f67e` mandatory update gate
- `886d82d` window title/build stamp
- Settings merge `9c2b788` (`b568624` on `desktop/settings`)
- `1e70f6a` Settings brand sweep + settings E2E in the chain

## Remaining

- P1: startup/bootstrap polish only; the mandatory update gate is complete.
- P5/P6/P7: Vizzy integration (real editor host, project I/O, pipeline) — **running** in `desktop/vizzy`.
- P8–P9 remain.

### Settings follow-ups

- Unsaved-settings navigation guard is `beforeunload` only; blocking sidebar navigation needs a
  shared router guard.
- Device-local paths (`ffmpegPath`, `sunoOutputDir`) live in account `/settings`; a local store
  would match 1.7.1.
- Diagnostics prepare a local reference; upload is not enabled.
- No IPC yet to measure/clear the analysis cache or probe a custom FFmpeg binary.
- `PUT /profiles/{id}` treats `null` as “leave unchanged”, so logo/cover cannot be removed.

## Merged pages

| Page | Status |
|---|---|
| Dashboard | Merged, 47-test baseline, fixture E2E |
| Profile | Merged, fixture E2E |
| Progress | **Merged** — filters, stats, 12-column table, detail, manual recovery, downloads, polling, 200-row E2E |
| Music | **Merged** — composer, draft/polish, channels, automation/cost, generate fan-out, polling, 9-column history |
| Image | **Merged** — queue, previews, prompts, retry/clear, 4 s polling |
| Marketplace | **Merged** — catalog, filters/search/paging, install/reinstall, archive safety, legacy policy |
| Settings | **Merged** — Profiles (create/edit/delete, allowance, media, YouTube), Publication (visibility, schedule, playlists, metadata), Preferences (FFmpeg, output dir, workers, thumbnails, diagnostics), deep link |
| Vizzy | **Running** — real Rea editor host, native project open/save; host spike merged |

Branding is aligned to camxora.com: original logo, Inter/Niradei, Font Awesome, #070a13 /
#0f1322 / #a855f7 palette, 28 px page titles, gradient primary CTA. Pages are lazy-loaded; the
shell chunk is ~328 kB (102 kB gzip).
