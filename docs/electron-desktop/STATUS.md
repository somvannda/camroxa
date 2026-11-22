# Implementation Status

> **Updated:** 2026-11-22
> **Worktree:** `G:\Developments\Projects\Camxora Desktop`
> **Branch:** `desktop/electron-v1`
> **Phase:** P1–P8 complete; packaging produces a Windows NSIS installer that defaults to production

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
| Packaging | `npm run package:win` produces `release/Camxora-2.0.0-setup.exe`; a packaged app defaults to `https://api.camxora.com/api/v1` (unpackaged dev still defaults to localhost) |
| **P1 auth** | Email/password, remember-me, Google OAuth loopback, in-app credits/top-up gate, email-confirmation gate, sign-out, dev/E2E bypass. Free accounts can sign in and buy credits in the app; generation stays gated server-side. A missing channel profile is not a gate |
| **P1 updates** | HTTPS release manifest, mandatory blocking gate, optional update card, download hand-off, unit + E2E coverage |
| **P2 account** | Dashboard (KPIs, weekly chart, quota, activity) and Profile (account, membership, channels, activity) |
| **P2 settings** | Profiles (list/create/edit/delete, allowance, media, YouTube), Publication (visibility, schedule, playlists, metadata), Preferences (FFmpeg, output dir, workers, thumbnails, diagnostics) |
| **P8 settings catalogs** | Descriptions, Structures, Moods (workspace defaults + paired structure + user prompt CRUD), Pools (read-only stats/table/pager) and Suno (bounded defaults); save-all covers all writable tabs |
| **Shell guard** | Unsaved settings block sidebar navigation with a Stay / Discard-and-leave confirm |
| **Shell footer parity** | 40 px footer with Ready, Local/Sandbox/Dev API badge, `v2.0.0`, live credits and profile allowance; auth footer shows env/version only |
| **Update parity** | Checks the platform `/public/desktop-release`, blocks before auth on mandatory offers, persists the gate across restart/unreachable checks and clears it on withdrawal |
| **Device paths** | FFmpeg and Suno output paths persist locally, and FFmpeg resolution prefers the configured binary. Portable backend run keys (`profile\date_album`) and relative image outputs resolve under the Suno output folder, so Open folder, image preview and batch folder creation work from any page |
| **P7 host spike** | `camxora-vizzy://` + loopback, all isolation/WebGL/worker/WASM checks pass; see [`vizzy/HOST-SPIKE.md`](vizzy/HOST-SPIKE.md) |
| **P7 Vizzy host** | Vendored Rea editor served from `camxora-vizzy://`, sandboxed `WebContentsView`, native open/save, crash recovery, shell strip; see [`vizzy/INTEGRATION-STATUS.md`](vizzy/INTEGRATION-STATUS.md) |
| **P7 template library** | All 91 templates staged with a manifest (`vizzy-library/`, 263.4 MB), safe slug-only reader, thumbnails allowed through `camxora-media://`; the editor's Creations browser lists and previews all 91, and `test:e2e:library` imports **91/91** with 0 skipped and exports one to a validated MP4 |
| **P7 pipeline contract** | Validated `pipeline.json`, conservative binding detection, run-input application, atomic video-template store with PNG thumbnails, render-plan builder |
| **P7 template pickers** | Profiles selects saved long/reel templates and persists `video_template_id`/`reel_template_id` with the profile; the full saved-template list lives in the same card; shell-only list/read/delete IPC |
| **P7 export + renders** | Native export through the editor's exporter, chunked to `renders/`, progress/cancel, inline Renders panel with confirmed delete; `vizzy-export` E2E |
| **P7 save + render templates** | One-click “Save template” dialog that writes the whole snapshot and auto-detects every binding; the same dialog can save a **new** template or overwrite an **existing** one in place (id/createdAt kept, whole folder replaced); saved-template rail with preview/render/delete; a saved template renders a real 1080p MP4 with the run audio; `candy-wave` also completed save → render at 640×360/60. The Export rail's resolution, fps, bitrate, CRF, preset, profile, audio bitrate and encoder are saved in `pipeline.json` and reused by every pipeline render; start/end stay tied to the live audio |
| **P7 merge groundwork** | FFmpeg concat planning (copy/re-encode), escaped list files, timeout/cleanup and long/reel output naming |
| **P7 queue groundwork** | Durable `pipeline_jobs` queue with dedupe/retry, next-item API, and a sequential runner with failure isolation, stop and merge hooks |
| **P7 batch orchestration** | Offscreen Vizzy render host (hidden `BrowserWindow`, dedicated `vizzy-render` partition) shared export session, template→plan→audio+background→export→ffprobe→merge orchestrator, `pipeline_*` IPC, durable batches; **auto-video coordinator** polls Progress every 12 s and starts long/reel branches independently with the generated 16:9/9:16 background; Progress “Video pipeline” table with real Cancel/Retry/Reveal; `pipeline-batch` E2E (no `/vizzy` open); reel 1080×1920 verified |
| **P7 output layout** | Pipeline renders write beside their audio in the downloaded run folder under the configured Suno output directory (`<song>.mp4`, `<song>-reel.mp4`), never the managed `renders/` folder. The merged file is `<album><MMDD>.mp4`; a second merge on the same day becomes `<album><MMDD> (1).mp4`. Editor/manual exports still use `renders/`. Run background/logo bindings clear the template's `assetId`, so the generated image is used instead of the template's bundled texture |
| **Music Simple mode** | Simple mode is prompt-only: no content pools, moods, structures, titles or lyrics are generated locally. Camxora names only the album (needed for run folders); Suno Description mode writes the title and lyrics from the selected description. The callback copies Suno's title/lyrics onto the song before image jobs; retries resubmit the description. Simple batches store no mood id. Covered by `test_batch_service.py` and `test_generation_service.py`. Deployed to sandbox only; production deploy awaits approval |
| **Music channel pairing** | The Primary/Secondary selection is saved in `/settings` (`primaryProfileIds`, `secondaryProfileIds`) on every toggle and restored on launch; a background refresh can no longer re-seed stale channels. `tests/e2e/music.mjs` restores a saved pair, changes it, asserts the PATCH, and reloads |
| **Image previews** | The Image page reads a local output first, then falls back to `GET /image-jobs/{id}/output` (session auth) for AI outputs that only exist on the server/B2. Fetched bytes are cached at the portable run path under the Suno folder, so the auto-video coordinator can reuse them as backgrounds |
| **P8 settings catalogs** | Descriptions, Structures, Moods (workspace defaults + paired structure + user prompt CRUD), Pools (read-only stats/table/pager) and Suno (bounded defaults); save-all covers all writable tabs |
| **P4 downloads** | Main-process coordinator (`download-coordinator.ts` + `download-targets.ts` + `download-io.ts`, `electron/ipc/downloads.ts`): 12 s/4 s polling, bounded concurrency, atomic temp→rename, 3-attempt backoff, dedupe, skip-if-present, cancel/pause/retry/reveal, completion sync; Progress shows live bytes and real actions; unit + `downloads` E2E |
| **Manual YouTube upload** | Ported 1.7.1 flow behind an explicit Progress action: access token → `POST /publish/jobs` → resumable `videos.insert` (chunks, 308 resume, retry) → `/youtube/uploads/report` → `/publish/jobs/{uid}/complete`; playlist, cancel, retry and readable disable reasons. Auto-Upload stays disabled |

### Verification

```text
npm run typecheck      PASS
npm run lint           PASS
npm test               397/397 PASS
python -m pytest platform_api/tests/test_generation_service.py \
  platform_api/tests/test_callbacks_router.py platform_api/tests/test_batch_router.py \
  platform_api/tests/test_batch_preflight_credits_only.py \
  platform_api/tests/test_music_downloads_router.py            PASS (93)
npm run build          PASS (shell bundle unchanged; pages split)
npm run vizzy:parity   PASS (59 decompile files; only 4 intentional patches + 3 host shims)
npm run test:e2e       PASS (18 suites incl. downloads, auto-video, pipeline-batch and youtube-upload)
node tests/e2e/settings.mjs PASS (8 tabs, prompt CRUD, pools pager, Suno bounds, save-all order)
node tests/e2e/youtube-upload.mjs PASS (job, 3 chunks resuming at 308, report, complete, link,
                                      cancel, quota failure + /retry, Auto-Upload disabled)
npm run api:check      PASS
npm audit --omit=dev   0 vulnerabilities
npm run package:win    PASS (`release/Camxora-2.0.0-setup.exe`, 515 MB)
node tests/e2e/packaged-smoke.mjs PASS (packaged app boots with no env overrides:
                                      production API + portal, release build, login page)
```

P8 was merged after the settings suite passed; the branch’s only extra requirement was the
`vizzy-dist` bundle used by the full chain.

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

The music **history** payload (`MusicHistorySong`) exposes output folders and
`downloaded_ok/alt` but **no per-song download URL**, so Music does not get a Download action:
the shell can only reveal a file that already exists. The download queue
(`/music/downloads/pending`) is the only source of download URLs. Completion is acknowledged
through `POST /music/downloads/sync`, which exists in the contract and matches 1.7.1; a
download URL therefore never needs the session token.

## P4 download coordinator

| Concern | Implementation |
|---|---|
| Entry points | `electron/ipc/downloads.ts` (shell-only `list`, `start`, `stop`, `retry`, `cancel`, `reveal`, `downloads:changed`), started at app boot, stopped in `before-quit` |
| Files | `download-targets.ts` (containment + URL guard, pure), `download-coordinator.ts` (state machine), `download-io.ts` (part file → rename) |
| Renderer | `use-download-queue.ts` (5 s visible poll, hidden-aware, single-flight, change events), `download-queue.tsx` (live bytes, retry/cancel/reveal/pause) |
| Output | Device Suno folder, else `<userData>/downloads`; `..`, absolute escapes and folder targets are rejected |
| Concurrency / retry | 2 (max 3); 3 attempts with 0.75 s/2 s backoff; permanent errors for 404/410, 401/403, unsupported URLs |
| Dedupe | `task_id::role`; repeated pending items and existing non-empty files are never re-downloaded |
| Measured (`downloads` E2E) | 4 real files written with exact bytes; repeated item fetched once; 500 retried 3× then manual retry succeeded; cancel left no `.part`; traversal target never fetched; 4 completions synced |

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
- Batch merge `21b4fe3` (`cdad89e` + `258330f` on `desktop/batch`) — offscreen render host,
  orchestrator, pipeline IPC, Music trigger, Progress table, `pipeline-batch` E2E
- P8 merge `4c7fb96` (`f2bc591` + `56174ae` on `desktop/settings-p8`) — five Settings tabs
- Downloads merge `c83238f` (`dd06f71` on `desktop/downloads`) — coordinator, live Progress,
  `downloads` E2E
- Upload merge `1bfcaae` (`6764b83` … `f08a8e3` on `desktop/youtube-upload`) — manual YouTube
  upload, resumable transfer, cancel/retry, `youtube-upload` E2E

## Remaining

- P1: startup/bootstrap polish only.
- P4: the download coordinator is merged and writes real audio, with live Progress and completion
  sync. Music has no per-song Download action because the history contract exposes no URL (see
  “Open API gap”); folder reveal remains the honest action for existing files.
- P7: editor, library, templates, render, Renders, batch orchestration and the **manual YouTube
  upload** are merged; Auto-Upload stays disabled exactly as 1.7.1.
- Upload risk: the resumable path is verified against a local fake Google endpoint, not real
  Google credentials or a live daily quota. A real-channel smoke test is still required; the UI
  reports provider refusals verbatim and never retries a refusal automatically.
- P8: all eight Settings tabs are merged.
- P9: installer/signing/clean-VM gate, the update install helper, and the 91-template
  bundle-size decision.

### Settings follow-ups

- Diagnostics prepare a local reference; upload is not enabled.
- No IPC yet to measure/clear the analysis cache.
- `PUT /profiles/{id}` treats `null` as “leave unchanged”, so logo/cover and template ids
  cannot be cleared; replacing a template works.
- Prompt CRUD is user-scoped: `/prompts/me/{descriptions|structures|moods}`. The
  `/prompts/{kind}` and `/prompts/{kind}/user-prompts` routes are admin-only (AdminUserDep), so
  the desktop Settings tabs cannot use them. Workspace selectors use
  `/prompts/{kind}/workspace`.
- `/prompts/me/*` writes archive the row; the list refreshes from the server, so the desktop
  never assumes a hard delete.
- `/content-pools/stats` reports only `total`/`unused` per pool. There are no per-user
  ownership counts, so the Pools tab shows “Account-wide” and explains editing is in the Admin
  Portal.
- `/settings` is an untyped key/value map. Suno bounds (version list, timeout, retries, merge
  group) are enforced by the desktop; the server accepts any value the client sends.

## Merged pages

| Page | Status |
|---|---|
| Dashboard | Merged — credits-only KPIs, weekly chart, credit wallet, grouped activity, fixture E2E |
| Profile | Merged, fixture E2E — identity, member since, role, desktop access, credits & usage, profiles, live activity |
| Plan | **Merged** — credit packs, hosted checkout, top-up history |
| Progress | **Merged** - filters, stats, desktop-parity 11-column table with local render/merge progress folded in, right-hand detail, manual recovery, polling, 200-row E2E; row right-click menu (open run folder, reveal rendered video, copy batch ID/album, retry images, cancel/retry render, YouTube URL); the second queue table only appears for renders that have no operational row; **Download queue** driven by the shell coordinator (real files, live bytes, retry/cancel/reveal/pause); **manual YouTube upload** (confirm → resumable → report → link, cancel/retry, Auto-Upload still off) |
| Music | **Merged** — composer, draft/polish, channels, automation/cost, generate fan-out, polling, 9-column history; **Simple mode** (Description + Songs per batch only); “Render videos” queues the profile’s saved template for ready songs |
| Image | **Merged** — queue, previews, prompts, retry/clear, 4 s polling |
| Marketplace | **Merged** — catalog, filters/search/paging, install/reinstall, archive safety, legacy policy |
| Settings | **Merged** — all eight tabs: Profiles, Publication, Preferences, Descriptions, Structures, Moods, Pools, Suno; template pickers and deep link |
| Vizzy | **Merged** — real Rea editor in a `WebContentsView`, `camxora-vizzy://`, native open/save, crash recovery, shell strip, templates, native export, renders, offscreen batch rendering |

Branding is aligned to camxora.com: original logo, Inter/Niradei, Font Awesome, #070a13 /
#0f1322 / #a855f7 palette, 28 px page titles, gradient primary CTA. Pages are lazy-loaded; the
shell chunk is ~333 kB (103 kB gzip).

## QA round (2026-11-19)

- Settings uses horizontal tabs instead of the vertical rail; the immediate-action note moved
  below the tab strip.
- Music's **Simple mode** is a checkbox inside Run settings (not a separate page). When it is on,
  only Description and Songs per batch shape the generation; the Song card and the generation
  options are hidden. The batch posts `structure_mode: "suno"` with no structure/mood and default
  language/creativity. Automation stays visible and is honoured in both modes.
- Automation labels/order: Music, Image, Video (16:9), Video (9:16), Merge Video, YouTube Upload
  (disabled). One Generate button; the separate "Render videos" action is gone.
- Primary/secondary channel lists are exclusive in both directions and a single profile is never
  preselected on both sides.
- Vizzy forces a first frame after `did-finish-load`/ready; the strip shows `Starting…` until the
  editor reports ready.
- Music History matches the Python desktop table: No, Album 1, Album 2, Title, Description,
  Structure, Mood, Primary Channel, Secondary Channel, Suno, Run date, grouped under a batch
  separator with channel pair, albums, song count, run date and generated time. Rows still load
  the composer; each channel keeps its folder button.
- All credit displays use at most two decimals (`formatCredits`) instead of raw micro-units or
  three-decimal `toLocaleString` output — footer, dashboard wallet/KPIs, Profile, Plan packs,
  top-up and the QR modal.
- Image parity with the Python app: Clear Filters, Deselect, per-kind source selectors in the
  preview cards, Manual Generation (regenerate the selected job, or create a today row through
  `/image-jobs/manual-generate`), a right-click row menu (Open output/folder, Retry or Regenerate
  background, thumbnail or both), and double-click to open a preview or queue job (failed jobs
  retry instead, like the Python app). Preview headers expose an output-folder button.
- Dashboard is credits-only and compact: six KPIs (balance, spent, songs, images, videos, uploads),
  a credit wallet card (granted/spent/remaining, exports, uploads, last export), a weekly chart
  with a labelled shared axis, and a grouped recent-activity timeline. Plan, song quota and image
  quota are gone.
- Profile matches: Account, Credits & usage (balance, profiles allowance, spend, counters),
  Channel Profiles, Activity at the same compact density.
- Progress is denser (accent stat cards) and shows the selected run's detail in a sticky right
  column from 1600 px; below that it sits under the table so all eleven columns still fit at 1440
  and 1280. The old visible/loaded/downloads summary line is gone.
- Window: 1440×900 by default, minimum 1280×800.
- `npm run dev:sandbox` runs the dev app against the sandbox API
  (`https://api.sandbox.camxora.com/api/v1`) and portal (`https://app.sandbox.camxora.com`).
- Profile is identity + work, not repeated stats: member since, role, desktop access,
  top-up/manage shortcuts, credits & usage, channel profiles, and a live activity feed.
- New **Plan** page (`/plan`, titled “Buy credits.”) matches the production pricing cards:
  credits/price headline, total songs, extra value vs the base pack, 30-day validity, instant
  delivery, “Most popular” on Medium, a “Every pack includes” strip, and one “Buy {pack}” action.
  Billing activity reads `credits/history`, converts micro-units to display credits, hides zero
  rows and humanizes ledger types. Buy opens a compact **in-app ChmabaPay QR modal** (340 px):
  the KHQR payload is rendered natively via Chmaba's SVG renderer inside our Dialog, with no
  provider page and no scrolling; the app polls `/topups/payments/{id}` and closes it when credits
  land. A webview is only a fallback if a provider returns no QR payload.
- Sidebar groups: **Overview** (Dashboard), **Create** (Progress, Music, Image, Vizzy),
  **Discover** (Marketplace), **Account** (Profile, Plan, Settings).
- The header update icon only appears when an update offer exists, matching the Python desktop;
  no manual "check for updates" control.
- Progress table matches the desktop's operational scan: Run Date, Channel, Album, Stage,
  Progress, Music, Image, Video (Render), Merge, YouTube, Updated. The stage percent is shown with
  a bar; status/notes live in the detail panel.
- Notifications: toasts float top-right on an opaque card; the title bar has a bell with
  unread count, history, mark-read and clear, plus an update button.
- Vizzy clears stale load errors when the editor becomes ready and ignores aborted navigations,
  so the red "could not be loaded" banner no longer appears after a successful load.
- Vizzy is embedded as one app: the editor's own topbar/status line is hidden, the canvas sits in
  a bordered frame, and the shell strip uses compact, grouped actions — New / Open / Save project
  (file), Export / Save as template (output), Templates / Renders (rails), Close (stop). Each
  action has a tooltip stating its purpose. The editor UI itself uses Camxora's navy surfaces,
  Inter stack, purple accent, rounded controls and blue/purple timeline tints; its left rail is
  now a horizontal Composition/Analyzers/Effects/Automations/Media/Projects/Lyrics bar directly
  under the Vizzy strip. Notifications on `/vizzy` stay inside the 48 px strip so the native
  editor view cannot cut them off.
- Free accounts land on a full-page native **top-up** surface, not a portal or webview: pack grid,
  one click creates the ChmabaPay KHQR and shows it natively, with “I’ve paid — check access” and
  “Use a different account”. The top-up page and Plan page share the same `CreditPackCard`
  (Most popular, credits/price, songs, extra value, validity, instant delivery), so packs read
  the same everywhere. The login fallback now asks the user to sign in instead of opening the web
  billing page. The sandbox API was hotfixed (auth/desktop_access) and restarted so free accounts
  can authenticate for this flow; generation remains paid-gated.
- Vizzy Export mirrors the editor's own Export dialog field-for-field: encoder (WASM /
  WebCodecs), the full resolution list, 24/30/60 fps, H.264/VP9/VP8, bitrate, CRF, preset,
  profile, audio bitrate, start/end and the estimated size, with the same defaults (60 fps,
  height-based bitrate). It reads the **live** composition duration when it opens, so a loaded
  track exports its full length instead of the 12-second default. The export framebuffer is
  pinned while rendering, so opening a rail/status strip or resizing the window mid-export can no
  longer corrupt a long 1080p file. The validated output lands in Camxora's `renders/` folder.
- Batch/offscreen renders go through the same Vizzy `runExport` with the same defaults (height
  based bitrate, CRF 20, veryfast/high, 192 kbps) and the pinned framebuffer. FFmpeg is used only
  for probing and the final merge — never as a second renderer.
- A Vizzy route change only hides the live editor; unsaved layers, undo history and the loaded
  audio survive when returning. **Close** or window close still stops it, and hidden views are
  throttled and stop preview audio.
- The Spectrum inspector's **Spectrum layers** group and every Layer 1/2/3 row collapse again
  (the group had no click handler and `.layer-controls { display:flex }` overrode `[hidden]`).
- Settings → Profiles owns the saved video templates: long/reel pickers plus the full template
  list with thumbnails, kind and selected state. Templates save with the profile; Publication no
  longer duplicates the pickers.
- Weekly Usage now draws monotone cubic curves (no square steps, no zero overshoot) with the same
  labelled axis and point markers.
- Shared control primitives (`Field`, `Input`, `Select`, `Checkbox`, `Range`) now back Music,
  Settings, Progress, Image and the Vizzy export menu, so heights, focus rings and disabled
  states match everywhere.
- Controls are real library components: `Select` is a Radix listbox, `Checkbox` is a Radix
  checkbox with a check icon, and `DatePicker` is a custom month calendar (no native browser
  picker). Empty dates are allowed for optional filters.
- Onboarding is gone: any confirmed account reaches the app even with zero channel profiles.
  Free/unpaid accounts can authenticate, but the shell stays closed behind a **top-up modal**
  (packs + hosted checkout). "I've paid — check access" refreshes the entitlement; generation
  remains blocked server-side until credits exist.

- Local DB drift: `platform_db` had an `alembic_version` revision from a diverged checkout, so
  migrations 175-211 never ran and `/progress` 500ed on `batches.auto_upload_youtube`. The local
  database was repaired in place (schema + representative pricing seeds) and stamped to `211`.
  This is a local-only repair; a fresh DB should come from `alembic upgrade head`.

