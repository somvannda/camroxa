# Risks and Decisions — Camxora Desktop (Electron)

> **Document ID:** CAMXORA-ED-05
> **Version:** 1.0.0
> **Status:** Draft
> **Owner:** Tech lead + Product
> **Last updated:** 2026-11-19

---

## 1. Architecture decision records

### ADR-001 — Electron + React + Vite

**Status:** Accepted (confirmed 2026-11-19)

**Context:** The desktop client is PySide6. The product also has a Next.js web app and a
web-native Vizzy editor. We need one desktop stack that can host web content and native
services.

**Decision:** Build the shell in Electron with React 19, TypeScript and Vite. The renderer is
a SPA with a memory router; the main process owns native work.

**Consequences:** Faster UI iteration, shared design tokens/components, Chromium weight
(+~150 MB), a new codebase to maintain. It is the base for the 2.0.0 pipeline automation.

---

### ADR-002 — Host Rea in a `WebContentsView`

**Status:** Accepted (confirmed 2026-11-19; the COOP/COEP spike remains a technical gate)

**Context:** Rea is a vanilla TS/DOM/three.js app. Mounting it inside React risks CSS/DOM
conflicts and a shared crash domain.

**Decision:** Build Rea separately and mount it in a dedicated `WebContentsView`. Bridge
files, project I/O and export through IPC.

**Consequences:** Near-zero renderer rewrite; a clean crash boundary; a bridge to maintain;
one more process. If the view cannot get `crossOriginIsolated`, fall back to a tokenised
loopback server.

---

### ADR-003 — API and tokens in the main process

**Status:** Accepted

**Decision:** The renderer never holds tokens or the API base URL. It calls
`window.camxora.api.request`; main attaches auth, refreshes once on 401 and returns a
discriminated result.

**Consequences:** Stronger security and no CORS; every call crosses IPC; streaming must be
handled in main.

---

### ADR-004 — Native FFmpeg

**Status:** Accepted

**Decision:** Ship static FFmpeg/ffprobe and run jobs in main. Keep ffmpeg.wasm only as a
Vizzy fallback until the native export matrix passes.

**Consequences:** Much faster exports, a bigger installer, codec/signing/AV concerns, a
platform-specific binary matrix.

---

### ADR-005 — SQLite for metadata, files for blobs

**Status:** Accepted

**Decision:** Use SQLite for projects, templates, recent files and job history; store blobs
(media, thumbnails, exports) as files under managed directories. Phase 0 uses Node 24's
`node:sqlite` through `electron/services/database.ts` to avoid a native rebuild. If packaging
or the experimental API proves unstable, swap to `better-sqlite3` behind the same Store
interface.

**Consequences:** Fast queries and no giant JSON; migrations required. `node:sqlite` emits an
experimental warning; the abstraction makes a later swap low-risk.

---

### ADR-006 — Feature parity, intentional visual refresh

**Status:** Accepted

**Decision:** Match every capability, workflow and data binding of the PySide6 client, but
redesign the shell with the tokens in [`06-DESIGN-SYSTEM.md`](06-DESIGN-SYSTEM.md). Do not
attempt a pixel copy.

**Consequences:** Design work is in scope; "looks different" is not a parity bug; layout
regressions are still bugs.

---

### ADR-007 — Vizzy is the only video engine in 2.0.0

**Status:** Accepted (2026-11-19)

**Context:** The 1.7.1 Video page is a batch pipeline: it takes a run's song/profile, renders a
Camxora template, merges, reels and uploads. Vizzy is a composition editor with its own
project and renderer. 2.0.0 must replace the Video page, not keep two renderers.

**Decision:** 2.0.0 ships **Vizzy editor + automation pipeline**. The pipeline is built on the
same Rea renderer:

- a pipeline template (`template.json` + `pipeline.json`) with audio/background/logo/text/
  palette/duration bindings;
- a headless render host with deterministic project-time analysis and frame readback;
- native FFmpeg encode, merge and reel;
- YouTube upload through `platform_api`;
- job orchestration with progress/cancel/retry/resume and partial-batch handling.

The Python visualizer is **not** shipped. **Old 1.7.1 Camxora video templates are not
migrated in 2.0.0.** They are not selectable by the pipeline and are not converted. The
pipeline uses **Vizzy-native pipeline templates only**. Users who need an old template stay on
1.7.x or re-author it in Vizzy later. All existing Vizzy content (presets, catalogues,
particle/Butterchurn presets, templates) must work as-is.

**Fallback:** None. A legacy sidecar is explicitly rejected; a converter is out of scope for
2.0.0. The product decision is a clean break for old Camxora video templates.

**Consequences:** The pipeline adds ~12–18 engineer-weeks. There is no legacy migration cost.
All 91 Vizzy templates are available and can be saved as video templates. Auto-Upload keeps the
1.7.1 behavior (disabled toggle). The plus side is one project model, one renderer, one template
format and one export path for manual and automatic video.

---

### ADR-008 — New codebase, not a revival of the archived Electron app

**Status:** Accepted

**Context:** `archive/electron-app` is a previous-generation Electron app with a 102 KB
`main.ts`, a 130 KB `Home.tsx`, direct Suno/Postgres access and a Python visualizer sidecar.

**Decision:** Use it as reference for patterns (job queue, FFmpeg, IPC), not as the base. The
new app talks only to `platform_api` and follows `PRODUCT_SCOPE.md`.

**Consequences:** More upfront work, but no old schema/security debt.

---

### ADR-009 — Windows-first release

**Status:** Accepted

**Decision:** 2.0.0 ships Windows x64. macOS/Linux builds are planned but not release gates.

**Consequences:** Code must remain cross-platform, but installer/signing/update work focuses
on Windows.

---

### ADR-010 — English-only UI

**Status:** Accepted

**Decision:** UI is English in 2.0.0. The music language setting remains product data.

**Consequences:** No i18n framework in 2.0.0; strings centralised for a later pass.

---

## 2. Risk register

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | Desktop rewrite takes much longer than estimated | High | High | Phase gates, MVP scope, reuse web components, one page at a time | Delivery |
| R-02 | Two desktop clients diverge during migration | High | High | Freeze new PySide6 feature work or mirror it; shared API contract | Product |
| R-03 | Vizzy host cannot get COOP/COEP / threaded FFT | Medium | High | Spike first; loopback fallback; sequential tier acceptable | Vizzy eng |
| R-04 | Vizzy renderer regresses in Electron | Medium | High | Parity harness, 10-project matrix, no renderer changes | Vizzy eng |
| R-05 | Pipeline delivery slips and 2.0.0 misses automation | High | High | Dedicated WS-G, phase gate on render→merge→upload, no upload work before render/merge green | Delivery |
| R-06 | API schema drift | Medium | Medium | OpenAPI generation + CI drift check | Backend |
| R-07 | Token/security incident | Low | Critical | Main-process tokens, safeStorage, IPC validation, redaction tests | Security |
| R-08 | Installer size/AV false positives | Medium | Medium | Prune assets, sign binaries, test on clean VMs | Release |
| R-09 | FFmpeg codec/GPU differences | Medium | Medium | Fallback ladder, probe output, validate files | Native |
| R-10 | Marketplace ZIP slip / malware | Low | High | Path validation, no executables, licence metadata | Security |
| R-11 | Design refresh diverges from feature parity | Medium | Medium | Page checklists + design gate; parity is a bug | Design |
| R-12 | Old Electron code is accidentally reused | Low | Medium | Archive is reference-only; ADR-008; review | Tech lead |
| R-13 | User data migration loses paths/settings | Medium | High | Migration wizard, backup, dry run | Product |
| R-14 | Update signing/rollback failure | Low | High | Signed manifest, staged rollout, rollback test | Release |
| R-15 | Accessibility debt | Medium | Medium | axe gate + manual keyboard pass per page | QA |
| R-16 | Performance regression in big tables/Vizzy | Medium | Medium | Budgets, virtualization if needed, profiling | Eng |
| R-17 | Licence issue with templates/assets | Low | High | Asset inventory + licence checks; no Vizzy assets | Legal |
| R-18 | Timeline slips because Settings/P2 grows | High | Medium | Split Settings core/advanced; P8 separate | Delivery |
| R-19 | Users lose access to old Camxora video templates in 2.0.0 | High | High | Publish the limitation, keep 1.7.x available, provide a re-author path in Vizzy | Product |
| R-20 | Headless render is too slow for batch use | Medium | High | Early benchmark, worker tuning, lower-res fallback with explicit estimate | Pipeline |
| R-21 | Deterministic render drifts between runs | Medium | High | Project-time analysis, seeded randomness, repeat-render test in CI | Pipeline |
| R-22 | Existing publication/manual upload uses wrong defaults | Medium | High | Publication preflight, field validation, retry without re-render; Auto-Upload remains disabled | Product |
| R-23 | Pipeline/editor output diverges | Medium | High | Manual-vs-pipeline parity test on the same template/inputs | Pipeline |
| R-24 | Credits charged for failed renders | Medium | High | Consume only after validated output; refund on failure; tests | Billing |
| R-25 | Vizzy content parity regresses (presets/catalogues/templates) | Medium | High | Content parity suite enumerating every built-in; release gate | Vizzy |
| R-26 | All 91 templates cannot be cleared for redistribution or bloat the installer | High | High | First-run template pack; licensing record; bundle option only if cleared | Product/Legal |
| R-27 | Pipeline output diverges from the saved preview | Medium | High | Save the exact project, same renderer, preview-parity test | Pipeline |

---

## 3. Open questions

| # | Question | Needed by | Owner |
|---|---|---|---|
| Q-01 | Confirm the 91-template delivery: first-run pack (recommended) or bundle in the installer | P7 | Product |
| Q-11 | Confirm the 91-template licensing/asset clearance record before public release | Release | Legal |
| Q-02 | Is `camxora.com` the shared component source, or only tokens? | P0 | Frontend |
| Q-03 | Do we migrate local settings/paths from PySide6, or document manual setup? | P9 | Product |
| Q-04 | Which marketplace templates are licensed for desktop install? | P6 | Legal/Product |
| Q-05 | Do we ship macOS/Linux in the first year? | P9 | Product |
| Q-06 | Is telemetry opt-in, opt-out, or absent in 2.0.0? | P0 | Product |
| Q-07 | Should Vizzy open in a separate window for multi-monitor users? | P7 | Design |
| Q-08 | Which app ID/signing identity is used for Windows? | P9 | Release |
| Q-09 | Is the desktop app still "legacy" per `PRODUCT_SCOPE.md`? | P0 | Product |
| Q-10 | Who owns the PySide6 client after the Electron release? | P9 | Product |

---

## 4. Assumptions

1. `platform_api` v3 is stable and documented via OpenAPI.
2. Sandbox credentials and a seeded account are available for QA.
3. Rea source, fixtures and parity data can be vendored for desktop use.
4. Windows 11 is the primary QA target; Windows 10 is best-effort.
5. Users accept a larger installer for Chromium + FFmpeg.
6. The existing PySide6 client remains the fallback until the Electron client passes the
   release criteria.

---

## 5. Kill criteria

Pause or re-scope the program if:

- the foundation gate slips by > 6 weeks without a working login;
- the Vizzy host cannot run WebGL/FFT in Electron after the spike;
- the pipeline cannot produce a validated long/reel output by the P7 mid-gate;
- the security review finds an unfixable P0 in the chosen architecture;
- two desktop clients cannot be maintained without feature drift.

A kill decision is a product decision, not an engineering failure. The fallback is the
PySide6 + QtWebEngine Vizzy path documented earlier.
