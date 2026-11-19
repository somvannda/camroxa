# Implementation Status

> **Updated:** 2026-11-19
> **Worktree:** `G:\Developments\Projects\Camxora Desktop`
> **Branch:** `desktop/electron-v1`
> **Phase:** P1 auth complete; P2–P6 pages merged; P7 editor, library, templates, render, Renders and batch orchestration merged; upload and P8–P9 remain

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
| **Shell guard** | Unsaved settings block sidebar navigation with a Stay / Discard-and-leave confirm |
| **Device paths** | FFmpeg and Suno output paths persist locally, and FFmpeg resolution prefers the configured binary |
| **P7 host spike** | `camxora-vizzy://` + loopback, all isolation/WebGL/worker/WASM checks pass; see [`vizzy/HOST-SPIKE.md`](vizzy/HOST-SPIKE.md) |
| **P7 Vizzy host** | Vendored Rea editor served from `camxora-vizzy://`, sandboxed `WebContentsView`, native open/save, crash recovery, shell strip; see [`vizzy/INTEGRATION-STATUS.md`](vizzy/INTEGRATION-STATUS.md) |
| **P7 template library** | All 91 templates staged with a manifest (`vizzy-library/`, 263.4 MB), safe slug-only reader, thumbnails allowed through `camxora-media://`; the editor's Creations browser lists and previews all 91, and `test:e2e:library` imports **91/91** with 0 skipped and exports one to a validated MP4 |
| **P7 pipeline contract** | Validated `pipeline.json`, conservative binding detection, run-input application, atomic video-template store with PNG thumbnails, render-plan builder |
| **P7 template pickers** | Publication selects saved long/reel templates and persists `video_template_id`/`reel_template_id`; shell-only list/read/delete IPC |
| **P7 export + renders** | Native export through the editor's exporter, chunked to `renders/`, progress/cancel, inline Renders panel with confirmed delete; `vizzy-export` E2E |
| **P7 save + render templates** | “Save template” dialog with detected/overridable bindings and PNG thumbnail; saved-template rail with preview/render/delete; a saved template renders a real 1080p MP4 with the run audio |
| **P7 merge groundwork** | FFmpeg concat planning (copy/re-encode), escaped list files, timeout/cleanup and long/reel output naming |
| **P7 queue groundwork** | Durable `pipeline_jobs` queue with dedupe/retry, next-item API, and a sequential runner with failure isolation, stop and merge hooks |
| **P7 batch orchestration** | Offscreen Vizzy render host (hidden `BrowserWindow`, dedicated `vizzy-render` partition) shared export session, template→plan→audio→export→ffprobe→merge orchestrator, `pipeline_*` IPC, durable batches; Music “Render videos” trigger; Progress “Video pipeline” table with real Cancel/Retry/Reveal; `pipeline-batch` E2E (no `/vizzy` open) |

### Verification

```text
npm run typecheck      PASS
npm run lint           PASS
npm test               278/278 PASS
npm run build          PASS (shell bundle unchanged; pages split)
npm run test:e2e       PASS (15 suites incl. pipeline-batch)
npm run api:check      PASS
npm audit --omit=dev   0 vulnerabilities
npx electron-builder --win --dir   PASS (unpacked app launched)
```

E2E screenshots: `desktop-electron/artifacts/` (dashboard/profile success, empty, error; login; auth gates; settings; vizzy shell/editor, library, save dialog, templates, rendered preview; batch progress/complete).

The Vizzy editor bundle is not committed. Build it once with `npm --prefix vizzy ci` then
`npm run vizzy:build` (or `npm run vizzy`); `vizzy-dist/` is required for `test:e2e` and
packaging.

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
- `9f8aac7` shell unsaved-navigation guard
- `b80c649` device-local FFmpeg/Suno paths
- `652e6aa` template library audit
- Vizzy merge `0bd869d` (`df46fe8` … `f999121` on `desktop/vizzy`)
- `c80dabc` …, `3c3f033` 91-template staging + reader
- `0941d40` pipeline contract, `943f027` video-template store, `c32e438` run bindings
- `653a34c` creations-layout staging, `ef60e25` library served to the editor (91 browsable/previewable)
- `2cd7e14` per-profile template pickers, `5d907cd` pipeline render plan
- Export merge `2b0cc7b` (`208da89` + `1291682` on `desktop/pipeline`)
- `8009d68` 91-template import matrix, `8af3ef7` FFmpeg merge groundwork
- `f13aabc` pipeline queue, `1a427ae` sequential runner
- `a5a0afa` real FFmpeg merge test, `a090213` library export matrix
- Templates merge `6881f13` (`e707508` … `581779f` on `desktop/templates`), `ab09985` strip fit
- Batch orchestration on `desktop/batch` — offscreen render host, orchestrator, pipeline IPC,
  Music trigger, Progress table, `pipeline-batch` E2E

## Remaining

- P1: startup/bootstrap polish only.
- P7: editor, 91-template library, save-as-template, single-template render, Renders and batch
  orchestration (offscreen render, merge, reel branch, cancel/retry, Music trigger, Progress
  table) are merged. **Upload is the remaining P7 gap**: Auto-Upload stays disabled exactly as
  1.7.1 and no publish IPC exists for the pipeline.
- P8–P9 remain.

### Settings follow-ups

- Diagnostics prepare a local reference; upload is not enabled.
- No IPC yet to measure/clear the analysis cache.
- `PUT /profiles/{id}` treats `null` as “leave unchanged”, so logo/cover and template ids
  cannot be cleared; replacing a template works.

## Merged pages

| Page | Status |
|---|---|
| Dashboard | Merged — KPIs, chart, quota, activity, fixture E2E |
| Profile | Merged, fixture E2E |
| Progress | **Merged** — filters, stats, 12-column table, detail, manual recovery, downloads, polling, 200-row E2E; **Video pipeline** table (durable queue, cancel/retry/reveal, merged output) |
| Music | **Merged** — composer, draft/polish, channels, automation/cost, generate fan-out, polling, 9-column history; “Render videos” queues the profile's saved template for ready songs |
| Image | **Merged** — queue, previews, prompts, retry/clear, 4 s polling |
| Marketplace | **Merged** — catalog, filters/search/paging, install/reinstall, archive safety, legacy policy |
| Settings | **Merged** — Profiles (create/edit/delete, allowance, media, YouTube), Publication (visibility, schedule, playlists, metadata), Preferences (FFmpeg, output dir, workers, thumbnails, diagnostics), deep link |
| Vizzy | **Merged** — real Rea editor in a `WebContentsView`, `camxora-vizzy://`, native open/save, crash recovery, shell strip, templates, native export, renders, offscreen batch rendering |

Branding is aligned to camxora.com: original logo, Inter/Niradei, Font Awesome, #070a13 /
#0f1322 / #a855f7 palette, 28 px page titles, gradient primary CTA. Pages are lazy-loaded; the
shell chunk is ~333 kB (103 kB gzip).
