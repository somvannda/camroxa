# Implementation Plan — Camxora Desktop (Electron)

> **Document ID:** CAMXORA-ED-03
> **Version:** 1.0.0
> **Status:** Draft for approval
> **Owner:** Delivery lead
> **Last updated:** 2026-11-19

---

## 1. How to read this plan

- **Phase** = a shippable slice with an exit gate.
- **Task ID** = `T-P<phase>-<nn>`. One task is one branch/worktree and one logical commit.
- **A task is done** only when its acceptance is verified and its page/feature checkboxes
  are ticked.
- Estimates assume **one experienced engineer** unless stated. Parallel work can compress
  the calendar, not the total effort.
- **Version:** every phase ships into **Camxora Desktop 2.0.0**. Do not bump the product
  version per phase; internal build metadata may increment (`2.0.0+YYYYMMDD.N`). The pipeline
  automation is part of 2.0.0, not a later version.
- Commit/push/merge happen only when the user explicitly asks, per `AGENTS.md`.

---

## 2. Workstreams

| WS | Name | Owns |
|---|---|---|
| **WS-A** | Platform foundation | Electron shell, build, IPC, API client, session, storage, security |
| **WS-B** | Account surfaces | Login, dashboard, profile, settings core |
| **WS-C** | Pipeline surfaces | Progress, music, image, 2.0.0 compatibility states |
| **WS-D** | Marketplace | Catalog, install, template store |
| **WS-E** | Vizzy | Host, project I/O, media, native export, parity |
| **WS-G** | Automation pipeline | Template contract, bindings, headless render, merge/reel, upload, Vizzy content parity |
| **WS-F** | Design & QA | Tokens, components, visual baselines, E2E, accessibility |

WS-A and WS-F start first. WS-B/WS-C/WS-D/WS-E/WS-G start after the foundation gate. One agent
per worktree; never run two editors in the same directory.

---

## 3. Phase overview

| Phase | Name | Effort (1 eng) | Can start | Exit gate |
|---|---|---|---|---|
| **P0** | Foundation and scaffold | 3–4 wk | Now | Shell boots, API call works, CI green |
| **P1** | Auth, shell, update, onboarding | 3–4 wk | P0 | Login → Dashboard on sandbox |
| **P2** | Settings core, Dashboard, Profile | 4–5 wk | P1 | Pages verified; profiles/settings round-trip |
| **P3** | Progress + live pipeline stages | 3–4 wk | P2 | Run recovery and live stage/retry end-to-end |
| **P4** | Music | 4–5 wk | P2 | Generate + history verified; credits exact |
| **P5** | Image | 2–3 wk | P2 | Queue/retry/clear verified |
| **P6** | Marketplace | 2–3 wk | P2 | Install/reinstall + picker refresh |
| **P7** | Vizzy + automation pipeline | 14–20 wk | P0/P1 | 10 projects round-trip + content parity + pipeline end-to-end |
| **P8** | Settings advanced + diagnostics | 3–4 wk | P2/P6 | All 8 tabs; prompts/pools/Suno |
| **P9** | Hardening and 2.0.0 release | 5–7 wk | P7/P8 | Signed installer, update, pipeline + content parity gates |

**Calendar estimate to 2.0.0:** 10–14 months with 4 parallel workstreams (1 lead + 3
engineers + shared QA/design); 8–11 months with 5–6 engineers; a single engineer should plan
for 16–22 months. The pipeline is the long pole, not the editor. These are planning ranges,
not commitments.

**No 2.1 deferral:** the automation pipeline is part of 2.0.0. Old Camxora video templates are
**not migrated**; Vizzy content parity is a release gate. The next version is a separate
product decision after 2.0.0.

---

## 4. Phase 0 — Foundation and scaffold

**Goal:** a running Electron shell that can call the API, store a session and pass CI.

> **Status (2026-11-19):** scaffold, secure window, typed IPC, API client, session storage,
> paths/file picker, logger/redaction, design tokens/shell and E2E smoke are implemented.
> OpenAPI types, SQLite, FFmpeg jobs, CI workflow and media protocol remain. See
> [`STATUS.md`](STATUS.md).

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P0-01 | Create `desktop-electron/` scaffold | `npm run dev` opens a window; `npm run build` produces a bundle | 2 d |
| T-P0-02 | Electron main/preload with `contextIsolation` + `sandbox` | Security checklist passes; no Node in renderer | 2 d |
| T-P0-03 | Typed IPC router + Zod schemas | Invalid payload test fails safely; typed client | 2 d |
| T-P0-04 | Tailwind + tokens + component primitives | Button/Input/Card/Table/Dialog/Toast match tokens | 3 d |
| T-P0-05 | Generate API types from OpenAPI | `api-schema.d.ts` builds; drift check in CI | 1 d |
| T-P0-06 | API client in main + `api:request` | GET `/users/me` returns typed data with a fake token | 2 d |
| T-P0-07 | Session storage (`safeStorage`) + single-flight refresh | Token round-trip; refresh test | 2 d |
| T-P0-08 | SQLite store + migrations | DB created; migration test; WAL on | 2 d |
| T-P0-09 | File/path services + media protocol | Open/reveal; media URL renders; outside-root rejected | 2 d |
| T-P0-10 | FFmpeg service + probe + job queue | Probe version; run a 2 s test job; cancel works | 3 d |
| T-P0-11 | Logger + redaction + crash boundary | Seeded secret absent; renderer crash recoverable | 2 d |
| T-P0-12 | CI: typecheck, lint, unit, build, Playwright smoke | Red on failure; artifacts retained | 2 d |
| T-P0-13 | Design baseline + page shells | Routes render empty states at 1440×900 | 2 d |
| T-P0-14 | ADR-001…006 recorded | Decisions link to code | 1 d |

**Exit gate**

- [ ] Shell boots in ≤ 3.5 s warm.
- [ ] API call + token refresh works against sandbox.
- [ ] `npm run typecheck lint test build` green.
- [ ] Security review of preload/IPC passes.
- [ ] Tokens/components reviewed by design.

---

## 5. Phase 1 — Auth, shell, update, onboarding

**Goal:** a real user can sign in, pass gates, and land on Dashboard.

> **Status (2026-11-19):** login screen, main-process login, remember-me session storage,
> `AuthGate`, sign-out and dev/E2E bypass are implemented. Google OAuth, paid gate,
> email-confirmation/onboarding gates and the update gate remain. See [`STATUS.md`](STATUS.md).

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P1-01 | Window chrome + title bar + window state | Drag, min/max/close, restore size | 2 d |
| T-P1-02 | Sidebar + footer + page header | Routes, active rail, status, account summary | 3 d |
| T-P1-03 | Login form | LG-11 … LG-22 | 3 d |
| T-P1-04 | Register flow | LG-23 … LG-27 | 1 d |
| T-P1-05 | Google OAuth loopback | LG-28 … LG-32 | 3 d |
| T-P1-06 | Session restore/expiry/logout | LG-40 … LG-43; SH-24 … SH-29 | 3 d |
| T-P1-07 | Paid gate + plans dialog | LG-33 … LG-35 | 2 d |
| T-P1-08 | Email-confirmation + onboarding gates | LG-36 … LG-39 | 2 d |
| T-P1-09 | Startup splash + bootstrap progress | LG-01 … LG-03 | 2 d |
| T-P1-10 | Update check/gate/install | LG-04 … LG-10; SH-65 … SH-71 | 4 d |
| T-P1-11 | Auth E2E | LG-T1 … LG-T10 | 2 d |

**Exit gate**

- [ ] Login → Dashboard against sandbox, including Google.
- [ ] Mandatory update gate blocks and recovers.
- [ ] Session survives restart with Remember me.
- [ ] No token in logs/localStorage.
- [ ] LG `P0` all `☑`.

---

## 6. Phase 2 — Settings core, Dashboard, Profile

**Goal:** the account surfaces and the settings needed by every other page.

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P2-01 | Dashboard data + KPI/chart/activity | DB-01 … DB-44 | 4 d |
| T-P2-02 | Profile cards + table | PR-01 … PR-32 | 3 d |
| T-P2-03 | Settings shell + dirty/save model | ST-108 … ST-120 | 3 d |
| T-P2-04 | Profiles tab (CRUD, logo/cover, templates) | ST-01 … ST-24 | 5 d |
| T-P2-05 | Publication tab | ST-25 … ST-44 | 4 d |
| T-P2-06 | Preferences: paths + workers | ST-45 … ST-58 | 3 d |
| T-P2-07 | Preferences: image/rendering + sample mode | ST-59 … ST-67 | 3 d |
| T-P2-08 | YouTube OAuth card + polling | ST-114 … ST-116 | 3 d |
| T-P2-09 | Workspace cache + account switch | ST-112/113; SH-29 | 2 d |
| T-P2-10 | Visual baselines + a11y pass | QA-01 … QA-05 | 2 d |

**Exit gate**

- [ ] Dashboard/Profile match the live payloads.
- [ ] Profile CRUD + publication round-trip.
- [ ] Settings values survive restart and account switch.
- [ ] Design review approves the shell density.

---

## 7. Phase 3 — Progress + live pipeline stages

**Goal:** see and recover any run, including the live converter/merge stages and the existing
upload flow.

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P3-01 | Progress data + filters + stats | PG-01 … PG-13 | 3 d |
| T-P3-02 | Operational table + runtime overlay | PG-14 … PG-27 | 4 d |
| T-P3-03 | Row detail + file actions | PG-28 … PG-32 | 2 d |
| T-P3-04 | Manual asset recovery | PG-33 … PG-38 | 3 d |
| T-P3-05 | Pending download queue | PG-39 … PG-43 | 2 d |
| T-P3-06 | Polling lifecycle + stale handling | PG-44 … PG-49 | 2 d |
| T-P3-07 | Pipeline stage model | Live converter/merge/reel stages; upload uses the existing flow; per-stage status and retry | 3 d |
| T-P3-08 | Pipeline event consumption | Render/encode/merge events update rows and the footer; upload status stays the existing flow | 3 d |
| T-P3-09 | Historical + live display | Old runs with stored values and new runs with live stages both render correctly | 2 d |
| T-P3-10 | Progress E2E | PG-T1 … PG-T9 | 3 d |

**Exit gate**

- [ ] A real run shows the correct live stage and next action.
- [ ] Manual recovery completes a run.
- [ ] Download queue reflects the coordinator.
- [ ] Converter, merge and reel stages are live and retryable; upload uses the existing flow.
- [ ] Historical data still renders.

---

## 8. Phase 4 — Music

**Goal:** compose, draft/polish, generate and inspect history with exact credits.

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P4-01 | Workspace bootstrap + state | MU-01 … MU-08 | 3 d |
| T-P4-02 | Top settings strip + autosave | MU-09 … MU-20 | 3 d |
| T-P4-03 | Song editor + copy/effects | MU-21 … MU-36 | 4 d |
| T-P4-04 | Draft flow + content pools | MU-37 … MU-45 | 4 d |
| T-P4-05 | Polish flow | MU-46 … MU-49 | 2 d |
| T-P4-06 | Channel pair selection + validation | MU-50 … MU-57 | 2 d |
| T-P4-07 | Automation card + cost model | MU-58 … MU-76 | 5 d |
| T-P4-08 | Generate fan-out + manual dirs | MU-77 … MU-85 | 4 d |
| T-P4-09 | Batch status polling | MU-86 … MU-89 | 1 d |
| T-P4-10 | History table + row load | MU-90 … MU-99 | 3 d |
| T-P4-11 | Download coordinator | MU-100 … MU-107 | 3 d |
| T-P4-12 | Music E2E + cost parity | MU-T1 … MU-T14 | 3 d |
| T-P4-13 | Automation hand-off | Generate triggers render/merge/reel with the selected toggles; status flows to Progress/Vizzy; Auto-Upload stays disabled | 4 d |

**Exit gate**

- [ ] Cost parity scenarios pass exactly (including video/merge/upload costs).
- [ ] 3-day × 2-pair generate creates 6 batches with correct dates.
- [ ] Draft claim/finalize/release verified.
- [ ] History row loads a real song.
- [ ] Downloads sync updates Progress.
- [ ] Auto-Video/Merge/Reel start from Generate and report status; Auto-Upload stays disabled.

---

## 9. Phase 5 — Image

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P5-01 | Workspace + polling | IM-01 … IM-07 | 2 d |
| T-P5-02 | Filters + stats | IM-08 … IM-13 | 2 d |
| T-P5-03 | Queue grouping/table | IM-14 … IM-24 | 4 d |
| T-P5-04 | Retry/open interactions | IM-25 … IM-31 | 2 d |
| T-P5-05 | Preview cards + file loading | IM-32 … IM-38 | 3 d |
| T-P5-06 | Prompt autosave | IM-39 … IM-45 | 2 d |
| T-P5-07 | Clear queue | IM-46 … IM-51 | 2 d |
| T-P5-08 | Image E2E | IM-T1 … IM-T10 | 2 d |

**Exit gate**

- [ ] Grouping/filter parity with a 20-job fixture.
- [ ] Retry/clear verified against sandbox.
- [ ] Previews never block the UI.

---

## 10. Phase 6 — Marketplace

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P6-01 | Template store + manifest validation | Extract safely; no partial installs | 3 d |
| T-P6-02 | Catalog query + pagination/filter/search | MK-01 … MK-08 | 2 d |
| T-P6-03 | Card grid + preview proxy | MK-09 … MK-18 | 3 d |
| T-P6-04 | Install/reinstall + progress | MK-19 … MK-30 | 4 d |
| T-P6-05 | Cache invalidation + picker refresh | MK-27; ST-14/15 | 2 d |
| T-P6-06 | Marketplace E2E | MK-T1 … MK-T10 | 2 d |

**Exit gate**

- [ ] A real catalog item installs and appears in Settings.
- [ ] Reinstall does not duplicate.
- [ ] Corrupt ZIP cannot break the store.
- [ ] Error vs empty is distinct.

---

## 11. Phase 7 — Vizzy + automation pipeline

**Goal:** the full editor runs inside the host **and** the same renderer powers automatic
video, merge, reel and upload. The old Video page is fully replaced.

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P7-01 | Hosting spike: custom protocol + COOP/COEP | `crossOriginIsolated` true; worker + WASM load | 3 d |
| T-P7-02 | Vendor Rea + sync script + patch set | Hash recorded; build reproducible | 2 d |
| T-P7-03 | `WebContentsView` host + bounds + lifecycle | Attach/detach/resize; no orphan | 3 d |
| T-P7-04 | Bridge (`window.camxoraVizzy`) + preload | All methods typed; messages validated | 3 d |
| T-P7-05 | Native project I/O + recent + autosave | VZ-61/64/66; VZ-H5/H6 | 5 d |
| T-P7-06 | Media bridge + picker + protocol | VZ-60; VZ-H3/H4 | 4 d |
| T-P7-07 | Import mapping + export JSON | VZ-62/63; 10 fixtures | 5 d |
| T-P7-08 | Native image export | VZ-90; validated PNG | 2 d |
| T-P7-09 | Native video export + audio mux | VZ-91/94/95; probe matrix | 6 d |
| T-P7-10 | Parity harness + 10-project matrix | VZ-H1 … VZ-H12; VZ-T10 | 6 d |
| T-P7-11 | Crash isolation + recovery | VZ-H7; shell survives | 2 d |
| T-P7-12 | Token override + shell strip + account | VZ-C01 … VZ-C07 | 3 d |
| T-P7-13 | Marketplace template picker | VZ-C20/C21 | 2 d |
| T-P7-14 | Vizzy E2E + visual baselines | VZ-T1 … VZ-T17 | 4 d |
| T-P7-15 | Pipeline template schema + store | PL-01/02; valid/invalid fixtures | 4 d |
| T-P7-16 | Binding inspector + save as template | PL-03 … PL-11 | 6 d |
| T-P7-17 | Headless render host | PL-12; offscreen WebGL + frame readback | 6 d |
| T-P7-18 | Deterministic time/analysis | PL-13/18; repeat render matches | 4 d |
| T-P7-19 | Native encode + validation | PL-17/31; `ffprobe` gate | 3 d |
| T-P7-20 | Job orchestrator + persistence | PL-20 … PL-28 | 6 d |
| T-P7-21 | Merge + reel | PL-29/30; validated long/reel outputs | 6 d |
| T-P7-22 | YouTube upload | PL-32 … PL-35; publication fields + retry | 5 d |
| T-P7-23 | Music/Progress/Settings/Marketplace integration | PL-36 … PL-39; live toggles/stages/pickers | 5 d |
| T-P7-24 | Vizzy Renders panel + template library | PL-40/46; queue, progress, cancel/retry, open output, create/duplicate/delete/import/export/protect | 5 d |
| T-P7-25 | Vizzy content parity audit | PL-41 … PL-45; every built-in preset/catalogue/particle/Butterchurn/template enumerated | 3 d |
| T-P7-26 | Vizzy content parity regression suite | Every enumerated item applies/renders/saves/reloads | 5 d |
| T-P7-31 | All 91 templates available | Import all 90 + Moai Money; open/preview/save/export; first-run pack or bundle | 6 d |
| T-P7-32 | Save preview as video template | Capture current project exactly; auto-detect/confirm bindings; store as user template | 4 d |
| T-P7-33 | Preview → pipeline parity | Pipeline output matches the saved preview at the accepted tolerance | 4 d |
| T-P7-27 | Pipeline E2E + performance | PL-T1 … PL-T10; throughput budget | 6 d |
| T-P7-28 | Credits/refund/consent | PL-35; preflight, consume, refund | 3 d |
| T-P7-29 | Manual vs pipeline parity | Same Vizzy template/inputs produce the same file at tolerance | 4 d |
| T-P7-30 | Support/release docs | Operator guide, known limits, no-legacy-template policy | 2 d |

**Exit gate**

- [ ] All 10 projects open, save, reopen, export.
- [ ] Video exports play with audio; duration ±1 frame.
- [ ] No renderer regression vs the Rea baseline.
- [ ] A Vizzy crash does not kill the shell.
- [ ] Tokens applied without layout regressions.
- [ ] Auto-Video/Merge/Reel/Upload work end-to-end from Music Generate.
- [ ] The old Video page has no remaining surface or dead link.
- [ ] Every Vizzy preset/catalogue/particle/Butterchurn/template works as-is.
- [ ] All 91 templates are available, open/preview/save/reopen/export, and can be saved as video templates.
- [ ] The pipeline output matches the saved preview.
- [ ] The 91-template delivery pack and licensing record are complete.
- [ ] Auto-Upload remains disabled exactly as 1.7.1.
- [ ] Old Camxora video templates are not offered as usable templates.
- [ ] Determinism, resume, retry, partial-batch and throughput tests pass.

---

## 12. Phase 8 — Settings advanced + diagnostics

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P8-01 | Descriptions/Structures/Moods tabs | ST-82 … ST-93 | 4 d |
| T-P8-02 | Pools tab | ST-94 … ST-100 | 2 d |
| T-P8-03 | Suno tab | ST-101 … ST-107 | 2 d |
| T-P8-04 | Sample packs/library (if enabled) | ST-68 … ST-74 | 3 d |
| T-P8-05 | Storage cache + diagnostics send | ST-75 … ST-81; SH-73 … SH-79 | 3 d |
| T-P8-06 | Coordinator status + kill switches | SH-51/SH-52 | 2 d |
| T-P8-07 | Settings E2E + a11y | ST-T1 … ST-T15 | 3 d |

**Exit gate**

- [ ] All eight tabs complete with loading/error/dirty states.
- [ ] Prompt CRUD and pools verified.
- [ ] Diagnostics redaction verified.
- [ ] Account switch leaves no leakage.

---

## 13. Phase 9 — 2.0.0 hardening and release

| ID | Task | Acceptance | Est |
|---|---|---|---|
| T-P9-01 | Performance pass | NFR-01 … NFR-05 met or documented | 4 d |
| T-P9-02 | Security review + dependency audit | No P0/P1 findings | 3 d |
| T-P9-03 | Accessibility audit | WCAG 2.2 AA on all pages | 3 d |
| T-P9-04 | Installer + signing + first run | Clean VM install/uninstall | 3 d |
| T-P9-05 | Auto-update from previous build | Update, relaunch, rollback on failure | 3 d |
| T-P9-06 | Migration from PySide6 settings/paths | Import wizard or documented manual steps | 3 d |
| T-P9-07 | Release notes + known limitations | Out-of-scope list published | 1 d |
| T-P9-08 | 1.7.1 → 2.0.0 compatibility statement | Video/Merger page replacement, pipeline scope and legacy template policy are explicit | 1 d |
| T-P9-09 | Full regression + sign-off | All page docs `P0` `☑` | 5 d |
| T-P9-10 | Package 2.0.0 artifacts (local only) | Checksums + signatures; version string `2.0.0` | 1 d |
| T-P9-11 | Pipeline release gate | Long/reel/merge/upload/determinism/resume/retry/partial-batch pass | 4 d |
| T-P9-12 | Vizzy content parity gate | Every built-in preset/catalogue/template verified; no-legacy-template policy published | 3 d |

**Exit gate**

- [ ] Release criteria in [`01-BUSINESS-REQUIREMENTS.md`](01-BUSINESS-REQUIREMENTS.md) §11
      all pass.
- [ ] Pipeline release gate and Vizzy content parity gate pass.
- [ ] Product, design, security sign-off.
- [ ] No production deploy without an explicit decision.

---

## 14. Critical path

```
P0 foundation
  ├─ P1 auth/shell ─ P2 dashboard/profile/settings-core
  │                     ├─ P3 progress
  │                     ├─ P4 music
  │                     ├─ P5 image
  │                     ├─ P6 marketplace
  │                     └─ P8 settings-advanced
  └─ P7 vizzy + pipeline (can start after P0/P1; needs P6 for templates)
                          └─ P9 hardening/release
```

The critical path is **P0 → P1 → P2 → P4 (Music) → P7 (pipeline) → P9**, with the Vizzy editor
starting in parallel. Marketplace must land before the Vizzy template/pipeline picker is
declared done. The pipeline, not the editor, sets the 2.0.0 date.

---

## 15. Staffing and parallelisation

| Role | Count | Focus |
|---|---|---|
| Tech lead | 1 | Architecture, security, reviews, critical path |
| Electron/native | 1 | Main process, IPC, storage, FFmpeg, updates, Vizzy host |
| Frontend A | 1 | Shell, login, dashboard, profile, settings |
| Frontend B | 1 | Progress, music, image |
| Vizzy engineer | 1 | Host, bridge, project I/O, export, parity (can be the native engineer) |
| Design/QA | 0.5–1 | Tokens, visual baselines, E2E, a11y |

Parallel rules:

- one agent per worktree; one task per branch;
- the foundation is not parallelised until the IPC/API contract is stable;
- Vizzy can run in a separate worktree once the bridge contract is frozen;
- never let two workstreams edit `package.json` or the design tokens at the same time.

---

## 16. Definition of done (program)

- [ ] All nine page docs have every `P0` feature `☑`.
- [ ] All acceptance suites pass on a clean Windows VM against sandbox.
- [ ] Vizzy 10-project matrix passes; no renderer regression.
- [ ] Pipeline end-to-end passes: long, reel, merge, upload, determinism, resume, retry,
      partial batch.
- [ ] Every Vizzy preset/catalogue/template works as-is; all 91 templates are available and saveable as video templates; old Camxora templates are not offered.
- [ ] Installer signed; update and rollback verified.
- [ ] Security and accessibility sign-off.
- [ ] Out-of-scope list and known limitations published.
- [ ] Traceability has no orphan feature.
- [ ] No production deploy without an explicit decision.

---

## 17. Change control

1. Change the page doc first (requirement).
2. Change this task list (scope/estimate).
3. Change the code.
4. Update [`07-TRACEABILITY.md`](07-TRACEABILITY.md).
5. If a change affects the architecture, add an ADR in
   [`05-RISKS-DECISIONS.md`](05-RISKS-DECISIONS.md).

A task that grows beyond 3 days is split. A phase that slips by > 20 % triggers a scope
review, not silent overtime.

---

## 18. Pipeline workstream detail (P7)

The pipeline is part of P7, not a later release. Its contract, job model, render budgets,
merge/upload rules, Vizzy content parity and acceptance are in
[`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).

**Critical sub-path:**

```
template schema → binding inspector → headless render → native encode/validate
  → job orchestrator → merge → reel → upload → surfaces (Music/Progress/Vizzy/Settings/Marketplace)
```

Rules:

- Do not start upload work before render + merge validation is green.
- Do not expose a toggle or stage until its job path is implemented end-to-end.
- Vizzy content parity is a release gate; old Camxora templates are not migrated.
- Determinism and resume/retry are tested before throughput tuning.
- The old Python visualizer is not a fallback and is not shipped.

**P7 pipeline acceptance:** a user selects a song batch, a profile, a pipeline template and
Generate, and receives validated long-form + reel outputs and an optional YouTube upload
without opening the editor or the old Video page.
