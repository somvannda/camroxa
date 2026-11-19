# Business Requirements — Camxora Desktop (Electron)

> **Document ID:** CAMXORA-ED-01
> **Version:** 1.0.0
> **Status:** Draft for approval
> **Scope owner:** Product
> **Last updated:** 2026-11-19

---

## 1. Purpose

Camxora Desktop is a Windows-first production studio for faceless music channels. It lets a
creator generate songs and images, run a multi-stage publishing pipeline, compose Vizzy
visuals, install templates, and manage account/channel settings without using a browser.

The current client is a PySide6 application (`camxora_python`, v1.7.1). This program rebuilds
that client on Electron so that:

1. the UI and rendering stack are web-native and shareable with `camxora.com` and the Vizzy
   editor;
2. the Vizzy editor can be hosted in the same product without rewriting its renderer;
3. one codebase can serve Windows, macOS and Linux;
4. UI iteration is faster and the design system is consistent across web and desktop.

This document defines **what** the Electron client must do. It does not define the code
structure; that is in [`02-TECHNICAL-ARCHITECTURE.md`](02-TECHNICAL-ARCHITECTURE.md).

---

## 2. Product vision

> A night-shift production desk for a faceless music channel: write the song, generate the
> artwork, compose the visual, run the pipeline, publish. Everything in one window, with the
> state of every run visible.

The desktop client is not a dashboard for a SaaS. It is a **workbench**: dense, keyboard-first,
interruptible, and honest about what is running, what failed, and what needs a human.

---

## 3. Users and jobs to be done

| User | Context | Job to be done |
|---|---|---|
| Solo creator / operator | Runs 1–10 channels, often overnight | Turn a batch of songs into finished, publishable videos with minimal clicks |
| Small studio operator | Manages profiles for several channels | Keep channel profiles, templates, prompts and publication defaults consistent |
| Power user | Iterates on visuals and timing | Open Vizzy, edit a composition frame-accurately, export without leaving the app |
| Support / power user | Something failed | Read a run's stage, open the right folder, retry only what failed, send diagnostics |

**Primary environment:** Windows 11, 1920×1080 or larger, discrete or integrated GPU,
intermittent connectivity. The app must remain usable while the backend is slow or briefly
unreachable.

---

## 4. Scope

### 4.1 In scope (2.0.0)

| Area | Included |
|---|---|
| Authentication | Email/password, Google, remember me, recent accounts, session restore, paid-access gate, email-confirmation gate, onboarding gate, logout/switch |
| Application shell | Frameless window, custom title bar, sidebar, page header, status footer, notifications, single instance, deep links |
| Dashboard | KPI row, weekly usage chart, remaining-month bars, quota summary, recent activity |
| Profile | Account, membership, channel profiles, activity |
| Progress | Filters, stat cards, operational table, runtime overlay, pending downloads, manual asset recovery |
| Music | Settings strip, song editor, draft/polish, channel pairs, automation toggles (video/merge/reel/upload), credit planning, generate, batch status, history |
| Image | Date filters, job queue, retries, clear queue, previews, prompt autosave |
| Vizzy | Full Rea/Vizzy editor: project, composition, nodes, inspector, effects, analyzers, automations, presets, templates, lyrics, timeline, stage, audio, manual export, **pipeline template authoring and Renders panel** |
| Pipeline | **Auto-Video, Auto-Merge, Auto-Reel and YouTube upload on the Vizzy renderer**, driven by Music/Progress; Vizzy-native template binding, headless render, batch/orchestration. **No legacy Camxora template migration.** |
| Vizzy content | **All existing Vizzy content works as-is**: built-in presets, spectrum catalogue, particle presets, Butterchurn presets, community/user presets, templates, thumbnails, import/export |
| Marketplace | Catalog, filters, search, pagination, preview, install, reinstall, installed state, pipeline template kind/compatibility |
| Settings | Profiles, publication, preferences, descriptions, structures, moods, pools, Suno, pipeline template pickers |
| Shared services | Secure session, API client, background coordinators, local store, FFmpeg, updates, diagnostics, crash logging |
| Packaging | Signed Windows installer, auto-update, first-run setup, uninstall |

### 4.2 Out of scope as separate pages (2.0.0)

| Area | Why |
|---|---|
| Workflow page | Not in the nine-page brief; its data is still used by Progress |
| Create page | Music covers creation; the separate Create workspace is deferred |
| Video page | **Removed.** Its editor is Vizzy; its pipeline is the 2.0.0 automation service (see §4.3) |
| Merger page | **Removed as a page.** Merge is a pipeline stage in Progress/Vizzy |
| Legacy Camxora video templates | **Not migrated in 2.0.0.** The pipeline uses Vizzy-native templates; old templates are not selectable. Users who need them stay on 1.7.x or re-author later. |
| Studio (hidden route) | Belongs to a separate product effort |
| Raw Diagnostics console | Support-only; keep a hidden route behind an env flag |
| Admin portal, public website, streaming portal | Separate products |
| macOS/Linux release | Planned, not a 2.0.0 gate |
| UI localisation | English-only UI; music-language data remains |

### 4.3 Vizzy is the only video engine (2.0.0 decision)

2.0.0 is the **full replacement** of the Video and Merger pages:

| 1.7.1 surface | 2.0.0 |
|---|---|
| Video page: preview, edit, template picking | **Vizzy editor** |
| Video page: per-run batch render | **Vizzy headless pipeline** |
| Video page: export queue | **Vizzy Renders panel + Progress** |
| Merger page / merge stage | **Native FFmpeg merge stage** |
| Reel variant | **Pipeline reel branch (1080×1920)** |
| YouTube upload | **Existing publication/manual flow**; Auto-Upload toggle stays disabled |
| Video/Reel templates | **Pipeline templates** (Vizzy project + `pipeline.json`) |

**What "Vizzy renders automatically" requires** (not optional):

1. **Pipeline template contract** — when the user likes the current preview, **“Save as video
   template”** captures that exact project as their template. A manifest records audio,
   background, logo, title/artist/album, palette and duration bindings; the save flow
   auto-detects them and lets the user confirm or override.
2. **Per-run binding** — the pipeline takes a run's MP3, AI background, profile logo, song
   metadata and publication settings and binds them to the saved template. The render must
   match the preview the user saved.
3. **Headless render service** — an offscreen WebGL render host with deterministic
   project-time audio analysis, frame readback and native FFmpeg encoding.
4. **Batch orchestration** — queue, progress, cancel, retry only the failed stage, resume,
   dedupe, partial-batch handling, credits/refunds.
5. **Merge and reel** — validate per-song MP4s, merge long-form, render vertical reels.
6. **YouTube upload** — keeps the 1.7.1 behavior exactly. The Auto-Upload toggle stays
   disabled; upload uses the existing publication/manual flow. Publication settings,
   schedule, playlist and credits are unchanged.
7. **Vizzy-native templates only** — the 1.7.1 Camxora template schema is **not migrated** in
   2.0.0. Old Camxora video templates are not selectable by the pipeline and are not shipped
   as Vizzy templates. Users who need them stay on 1.7.x, or re-author in Vizzy later.
   The Python visualizer is not shipped.
8. **Vizzy content parity** — every template, preset and catalogue already in Vizzy must work
   exactly as it does today: 5 built-in spectrum presets, 32 spectrum catalogue presets,
   18 particle presets, 6 Butterchurn presets, community presets (empty is valid), user
   presets, the templates modal/panel, preset thumbnails and import/export.
9. **All 91 templates are available to users** — all 90 reference exports + the Moai Money
   creation must open, render, save, reopen and export in the Electron host. They are part of
   the Vizzy template library, not a hidden test corpus. Users can open any of them, preview
   it, adjust it, and save it as their own video template.
   - **Delivery:** 14.2 MB of JSON + 265.6 MB of media. Recommended delivery is a first-run
     “Vizzy Templates” pack so the base installer stays lean; the app presents all 91 as
     available. Bundling everything in the installer is acceptable if product accepts the
     size.
   - **Licensing/asset clearance** is a release dependency. Engineering ports all 91; legal
     clearance must be recorded before public distribution.

The full contract, binding rules, render budgets, job model and acceptance are in
[`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).

**Why this is the right architecture:** it removes the second renderer, makes the editor and
the pipeline share one project model, and lets a template be authored and previewed in the
same place that renders it. The cost is the pipeline layer (~**12–18 engineer-weeks**) on top
of the editor. There is **no legacy template migration cost** in 2.0.0.

**Not doing it** would mean keeping the Python visualizer or dropping automation. Both
contradict the 2.0.0 goal.

### 4.4 Versioning

- The user-facing version of this program is **2.0.0**.
- Every phase in this pack ships into 2.0.0. Do **not** bump to 2.0.1, 2.1 or similar for
  phase work.
- Internal build metadata may increment (`2.0.0+20261119.1`) for CI and support; the product
  version stays 2.0.0 until release.
- There is no 2.1 deferral in this plan. The next version is a separate product decision after
  2.0.0.

---

## 5. Product principles

1. **Parity before polish.** Every existing user-facing capability must exist before the
   design is allowed to diverge. "Clone" means the job can be completed, not that a button
   moved.
2. **The run is the unit of truth.** Progress, Music and Image all speak the same batch/run
   identifiers. A row clicked in Progress must lead to the same channel, date and files as
   the Music history.
3. **Never hide a failure.** Errors are visible, specific and actionable. A failed mutation
   never looks like an empty state.
4. **Local-first where it is safe.** Paths, caches, drafts and templates work offline. Auth and
   generation are online.
5. **Keyboard-first.** Every primary action has a shortcut; the command palette can reach
   every route and action.
6. **No surprise data loss.** Autosave is debounced and visible; destructive actions confirm;
   in-flight generations survive navigation.
7. **One visual language.** Desktop and web share tokens, iconography and component
   behaviour. The desktop is denser, not different.

---

## 6. Page outcomes

| Page | The user can… | Success looks like |
|---|---|---|
| Login | Sign in, restore a session, recover access, understand a gate | A valid user reaches Dashboard in under 10 seconds on a warm cache |
| Dashboard | See usage, quota and recent activity at a glance | Five KPIs and the chart are correct on first load, with no refresh button |
| Profile | Verify identity, plan, profiles and lifetime counters | Every field matches `/users/me`, `/licenses/validate` and `/profiles` |
| Progress | Find a run, see its real stage, recover a blocked run | Every operational row resolves to a stage and the correct next action |
| Music | Compose a batch, draft/polish, generate with automation, inspect history | Generate produces exactly the planned batches, the right credit total, and the pipeline renders/merges/uploads as configured |
| Image | Inspect jobs, preview outputs, retry/clear | A retry or clear changes the backend state and the table refreshes |
| Vizzy | Open, edit, save, preview, and **save the current preview as a video template**; render/export a composition | A project round-trips; all 91 templates and every preset/catalogue work as-is; an export produces a playable file |
| Pipeline | Auto-render, merge and reel a run using the saved preview template | The render matches the preview the user saved; a batch produces validated long/reel MP4s |
| Marketplace | Browse, filter, install a template | Installed template appears in the template picker without a restart and is usable by the pipeline |
| Settings | Manage profiles, publication, prompts, pools, Suno | A saved change survives restart and is visible to the next page load |

---

## 7. UX direction (summary)

The full specification is in [`06-DESIGN-SYSTEM.md`](06-DESIGN-SYSTEM.md).

| Line | Direction |
|---|---|
| **Product** | A night-shift production studio for faceless music channels: generate, compose, run, publish |
| **Character** | Operator-grade, precise, quietly energetic |
| **World** | camxora.com after hours: deep navy surfaces, Inter + Niradei type, violet as the signal, never a wash |
| **Moments** | The Vizzy stage preview and the Dashboard weekly chart carry the color; everything else stays quiet |
| **Signature** | A 2px signal rail on the active nav item, a live status dot, and mono timecode with tabular figures |

Deliberate anti-slop rules: no hue gradients on surfaces, no gradient text, no glows, no
colored shadows, no emoji as icons, no uppercase tracked labels, no "New ✨" badges, no
looping decorative motion, one icon set at one size, one accent used rarely.

---

## 8. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Cold start to interactive shell | ≤ 3.5 s on a warm OS cache, ≤ 6 s cold |
| NFR-02 | Route switch (cached page) | ≤ 150 ms |
| NFR-03 | API page first paint | ≤ 700 ms after response |
| NFR-04 | Memory (idle, 5 pages visited) | ≤ 450 MB |
| NFR-05 | Installer size (Windows x64) | ≤ 220 MB, excluding user media |
| NFR-06 | Crash-free sessions | ≥ 99.5 % |
| NFR-07 | Renderer security | `contextIsolation: true`, `sandbox: true`, no `nodeIntegration` |
| NFR-08 | Token storage | OS-encrypted at rest; never in `localStorage` |
| NFR-09 | Accessibility | WCAG 2.2 AA for contrast, focus, keyboard, labels |
| NFR-10 | Offline shell | Login screen and cached pages render with a clear offline state |
| NFR-11 | Data safety | No destructive action without confirmation; no partial writes |
| NFR-12 | Updates | Mandatory gate for security releases; optional for minor releases |
| NFR-13 | Observability | Structured logs, redacted diagnostics, crash dump on unhandled error |
| NFR-14 | Vizzy isolation | A Vizzy crash cannot take down the shell; recover with a reload action |
| NFR-15 | Pipeline render throughput | 1080p/30 fps ≥ 12 fps render, two workers ≥ 20 fps aggregate on a mid-range GPU |
| NFR-16 | Pipeline determinism | Same project + inputs produces the same frames at the accepted tolerance |
| NFR-17 | Pipeline recovery | A cancelled/crashed batch resumes without re-rendering valid outputs |
| NFR-18 | Upload safety | A failed upload never deletes the local file; retry is explicit |

---

## 9. Legal, platform and data constraints

1. **Use our code, not Vizzy's.** The Rea editor is an independent implementation. Port the
   Rea code and the documented behaviour. Do not ship Vizzy's minified client bundle, source
   maps, shaders or artwork. Public data formats and measured layout values are fine.
2. **Third-party assets.** Templates, fonts, Lottie files and music must have a recorded
   licence or be replaced. Marketplace installs carry their own licence metadata.
3. **Backend contract.** `platform_api` v3 is the only backend. No direct Suno, Firestore,
   Firebase or PostgreSQL access from the desktop. The old Electron app did this; it must not
   return.
4. **Secrets.** No API keys in the renderer or the installer. OAuth uses the system browser
   and a loopback listener; refresh tokens live in the main process.
5. **User files.** All local paths are user-owned. The app never deletes outside its own
   managed directories without an explicit action.
6. **Telemetry.** Opt-in/known policy: diagnostics are sent only on user action or an
   explicit crash-report choice. Redact tokens, emails and file paths.
7. **Release hold.** No production deploy from this program until an explicit decision.
   Builds are local/sandbox only.

---

## 10. Success metrics

| Metric | Definition | Target |
|---|---|---|
| Page parity | P0 features verified against the live API | 100 % before a page is "done" |
| Task completion | Scripted E2E flows pass on Windows | 100 % of P0 flows |
| API error handling | Every page has loading/empty/error/stale states | 100 % |
| Vizzy round-trip | Open → edit → save → reopen → export | 100 % on 10 reference projects |
| Vizzy content parity | Every built-in preset/catalogue/template applies, renders, saves and reloads | 100 % of the inventory |
| 91-template library | Every template opens, previews, saves, reopens, exports and can be saved as a video template | 100 % of the library |
| Vizzy parity | Existing Rea parity suite passes in the Electron host | No regression vs Rea baseline |
| Pipeline success | Auto-video jobs that produce a valid MP4 | ≥ 99 % excluding user input errors |
| Pipeline determinism | Repeat renders matching at tolerance | 100 % of the acceptance set |
| Pipeline throughput | 1080p/30 fps render speed | ≥ 12 fps per worker; two workers ≥ 20 fps |
| Upload success | Uploads accepted by the platform | ≥ 99 % excluding quota/consent errors |
| Crash-free | Sessions without a renderer/main crash | ≥ 99.5 % |
| Update adoption | Installs on the latest version within 14 days | ≥ 90 % of active installs |
| Support load | Diagnostics uploaded per 100 active users | ≤ 2 |

---

## 11. Release criteria (2.0.0)

A release candidate is shippable only when all of the following are true:

- [ ] All nine page docs have every `P0` feature `☑`.
- [ ] The acceptance suites in [`04-QA-ACCEPTANCE.md`](04-QA-ACCEPTANCE.md) pass on a clean
      Windows VM against sandbox `platform_api`.
- [ ] The Vizzy reference set (10 projects) opens, saves, reopens and exports.
- [ ] The pipeline acceptance set passes: long render, reel, merge, upload, determinism,
      resume, retry, partial batch.
- [ ] Vizzy content parity passes: built-in presets, spectrum catalogue, particle presets,
      Butterchurn presets, community/user presets, templates and import/export.
- [ ] All 91 templates are available in the Vizzy template library and pass
      open/preview/save/reopen/export.
- [ ] All 91 can be saved as a user video template and rendered by the pipeline.
- [ ] Licensing/asset clearance for the 91-template pack is recorded before public release.
- [ ] Old Camxora video templates are not offered as usable templates; the limitation is
      published.
- [ ] No open `P0`/`P1` security finding.
- [ ] Installer is signed, auto-update is verified from the previous build, uninstall leaves
      no orphan processes.
- [ ] Diagnostics redaction is verified with a seeded token/email/path.
- [ ] The supported OS matrix and known limitations are published in the release notes.
- [ ] The 1.7.1 → 2.0.0 compatibility statement is published, including the Video/Merger
      page replacement and the “old Camxora templates are not migrated in 2.0.0” policy (§4.3).
- [ ] Product signs off the out-of-scope list (§4.2) and the pipeline decision (§4.3).

---

## 12. Assumptions and open questions

| # | Assumption / question | Owner | Needed by |
|---|---|---|---|
| A-01 | `platform_api` v3 remains the contract; no new desktop-only endpoints | Backend | Phase 0 |
| A-02 | `camxora.com` is the long-term web shell; desktop components may be shared | Product | Phase 0 |
| A-03 | Windows is the only 2.0.0 release target | Product | Phase 0 |
| A-04 | 2.0.0 includes the full Vizzy pipeline; the Python visualizer is not shipped | Product | Phase 0 |
| A-05 | Vizzy reference projects and the Rea parity harness can be used as test fixtures | Legal/Product | Phase 7 |
| A-06 | Marketplace templates are licensed for desktop install and pipeline use | Product | Phase 6 |
| A-07 | Existing users can migrate local settings/paths from the PySide6 app | Product | Phase 9 |
| A-08 | The old Electron app is reference-only; it is not revived as the base | Engineering | Phase 0 |
| A-09 | Old Camxora video templates are not migrated in 2.0.0; the pipeline uses Vizzy templates | Product | Phase 7 |
| A-10 | Auto-Upload keeps the 1.7.1 behavior: the toggle stays disabled; upload uses the existing publication/manual flow | Product | Phase 7 |
| A-11 | All 91 Vizzy templates and all presets/catalogues are in scope and must work as-is | Product | Phase 7 |
| A-12 | The 91-template delivery is a first-run “Vizzy Templates” pack by default; bundling is a product choice | Product | Release |

---

## 13. Approval

| Role | Name | Decision | Date |
|---|---|---|---|
| Product | | ☐ Approve ☐ Request changes | |
| Engineering | | ☐ Approve ☐ Request changes | |
| Design | | ☐ Approve ☐ Request changes | |
| Security | | ☐ Approve ☐ Request changes | |
