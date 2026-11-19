# Camxora Desktop (Electron) — Planning Pack

> **Status:** Planning. No implementation code yet.
> **Release target:** **Camxora Desktop 2.0.0** (all phases ship into 2.0.0; no per-phase version bumps)
> **Worktree:** `G:\Developments\Projects\Camxora Desktop`
> **Branch:** `desktop/electron-v1`
> **Base:** `camxora-1.7.1-build` @ `1e1cf3e` (`main`)
> **Owner:** Product + Desktop engineering
> **Last updated:** 2026-11-19

This pack is the single source of truth for rebuilding the Camxora desktop client as an
Electron application and porting the Vizzy editor into it as a first-class page.

> **Version note:** `Version:` fields inside these documents are *document revisions*. The
> product version is **2.0.0** for every phase in this pack. See
> [`08-RELEASE-2.0.0.md`](08-RELEASE-2.0.0.md).

The word **clone** in this pack means **functional and behavioural parity** with the
existing `camxora_python` client and with the Rea/Vizzy editor. It does **not** mean copying
third-party source code or shipping third-party assets. See
[`01-BUSINESS-REQUIREMENTS.md`](01-BUSINESS-REQUIREMENTS.md) §9.

---

## 1. Scope

Nine product pages, plus the shell and shared services that make them work:

| # | Page | Route | Doc |
|---|---|---|---|
| 1 | Login | `/auth` | [`pages/01-LOGIN.md`](pages/01-LOGIN.md) |
| 2 | Dashboard | `/app/home` | [`pages/02-DASHBOARD.md`](pages/02-DASHBOARD.md) |
| 3 | Profile | `/app/profile` | [`pages/03-PROFILE.md`](pages/03-PROFILE.md) |
| 4 | Progress | `/app/progress` | [`pages/04-PROGRESS.md`](pages/04-PROGRESS.md) |
| 5 | Music | `/app/music` | [`pages/05-MUSIC.md`](pages/05-MUSIC.md) |
| 6 | Image | `/app/image` | [`pages/06-IMAGE.md`](pages/06-IMAGE.md) |
| 7 | Vizzy | `/app/vizzy` | [`pages/07-VIZZY.md`](pages/07-VIZZY.md) |
| 8 | Marketplace | `/app/marketplace` | [`pages/08-MARKETPLACE.md`](pages/08-MARKETPLACE.md) |
| 9 | Settings | `/app/settings` | [`pages/09-SETTINGS.md`](pages/09-SETTINGS.md) |

Shared shell, auth/session, updates, notifications, background coordinators and
diagnostics: [`pages/10-SHELL-AND-SERVICES.md`](pages/10-SHELL-AND-SERVICES.md).

**Automation pipeline:** not a separate page. It is the Vizzy renderer driven by Music/
Progress, with a Renders panel in Vizzy. Contract and tasks:
[`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).

**Out of scope as separate pages:** Workflow, Create, Video, Merger, Studio, Log (raw
console), admin portal, public website, music streaming, and the Python app itself. The
**capabilities** of the Video/Merger pages are included in 2.0.0 through the Vizzy pipeline
(Auto-Video/Merge/Reel/Upload), not as separate pages. See §4 of the business requirements
and [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).

---

## 2. Document map

| Doc | Purpose |
|---|---|
| [`01-BUSINESS-REQUIREMENTS.md`](01-BUSINESS-REQUIREMENTS.md) | Vision, users, scope, success metrics, constraints, release criteria |
| [`02-TECHNICAL-ARCHITECTURE.md`](02-TECHNICAL-ARCHITECTURE.md) | Stack, process model, IPC, security, API/auth, storage, media, packaging |
| [`03-IMPLEMENTATION-PLAN.md`](03-IMPLEMENTATION-PLAN.md) | Phases, workstreams, task IDs, dependencies, estimates, milestone gates |
| [`04-QA-ACCEPTANCE.md`](04-QA-ACCEPTANCE.md) | Test pyramid, page acceptance suites, parity, security, performance, release gates |
| [`05-RISKS-DECISIONS.md`](05-RISKS-DECISIONS.md) | ADRs, open questions, risks and mitigations |
| [`06-DESIGN-SYSTEM.md`](06-DESIGN-SYSTEM.md) | UX direction, tokens, components, layout, accessibility, unslop rules |
| [`07-TRACEABILITY.md`](07-TRACEABILITY.md) | Feature IDs ↔ pages ↔ phases ↔ tests ↔ source files |
| [`08-RELEASE-2.0.0.md`](08-RELEASE-2.0.0.md) | 2.0.0 scope, compatibility with 1.7.1, versioning, rollout |
| [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md) | Vizzy pipeline contract, headless render, batch/merge/reel/upload, Vizzy content parity, no legacy migration |
| [`STATUS.md`](STATUS.md) | Live implementation status, verification evidence, open decisions |
| [`pages/`](pages/00-PAGE-INDEX.md) | Per-page feature checklists and acceptance criteria |
| [`vizzy/`](vizzy/01-FEATURE-INVENTORY.md) | Deep port plan, feature inventory, module map, parity harness |

---

## 3. Working decisions

These are the current defaults. Each has an ADR in
[`05-RISKS-DECISIONS.md`](05-RISKS-DECISIONS.md); changing one requires updating the
affected docs and tasks.

| # | Decision |
|---|---|
| D-01 | **Electron + React + TypeScript + Vite** renderer; Node main process for native work. Confirmed. |
| D-02 | **Vizzy is hosted, not rewritten.** Build the existing Rea editor as a separate Vite bundle and mount it in a dedicated `WebContentsView`; bridge files, project I/O and export through the Electron main process. Confirmed. |
| D-03 | **All API calls go through the main process.** Tokens live in the main process and are encrypted with the OS keystore; the renderer never holds a refresh token. |
| D-04 | **Native FFmpeg** for video/audio export and merge. FFmpeg.wasm may remain only as a fallback until the native bridge is proven. |
| D-05 | **Design is an intentional desktop refresh**, not a pixel copy of the PySide6 app. Feature parity is mandatory; layout parity is by region and workflow. The visual bar is professional/operator-grade, not decorative. |
| D-06 | **Windows first.** macOS/Linux packaging is planned but not a 2.0.0 release gate. |
| D-07 | **English first.** The music-language setting is product data, not UI localisation. |
| D-08 | **No production deploy.** This program builds and verifies locally until an explicit release decision. |
| D-09 | **Version 2.0.0 only.** All phases deliver into 2.0.0. Internal build metadata may increment (`2.0.0+YYYYMMDD.N`); the user-facing version does not bump per phase. |
| D-10 | **2.0.0 is the full replacement.** Vizzy is the only video engine: editor + pipeline automation (Auto-Video/Merge/Reel). The old Video page is removed. **Old Camxora video templates are not migrated in 2.0.0.** **All 91 Vizzy templates are ported and available to users.** The pipeline renders **the current Vizzy preview saved by the user as their video template**; bindings are auto-detected with optional overrides. **Auto-Upload keeps the 1.7.1 behavior exactly (toggle remains disabled; upload uses the existing publication flow).** See [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md). |

---

## 4. Status legend

Use these markers everywhere. A feature is only `☑` when its acceptance criteria are
verified against a real `platform_api`, not a mock.

| Marker | Meaning |
|---|---|
| `☐` | Not started |
| `◐` | In progress / partially verified |
| `☑` | Done and verified |
| `⊘` | Blocked (link the blocker) |
| `—` | Out of scope for this phase |

---

## 5. How to use this pack

1. **Before a phase starts:** read its page doc and confirm every `P0` feature is listed.
2. **During work:** tick the task checkboxes in
   [`03-IMPLEMENTATION-PLAN.md`](03-IMPLEMENTATION-PLAN.md), and tick the matching feature
   checkboxes in the page doc.
3. **Before a phase is declared done:** run the acceptance suite in
   [`04-QA-ACCEPTANCE.md`](04-QA-ACCEPTANCE.md) and attach evidence (test log, screenshots,
   API trace).
4. **When a requirement changes:** change the page doc first, then the task, then the code.
   Never mark a feature done because the UI exists; mark it done because the acceptance
   test passes.

---

## 6. Immediate next actions

- [ ] Review and approve the 2.0.0 scope and the full-replacement pipeline in
      [`01-BUSINESS-REQUIREMENTS.md`](01-BUSINESS-REQUIREMENTS.md),
      [`08-RELEASE-2.0.0.md`](08-RELEASE-2.0.0.md) and
      [`09-PIPELINE-AUTOMATION.md`](09-PIPELINE-AUTOMATION.md).
- [ ] Approve the “no legacy Camxora template migration in 2.0.0” decision, the
      **all-91-templates** gate and the **Vizzy content parity** gate.
- [ ] Decide the 91-template delivery: bundle in the installer or install as a first-run
      “Vizzy Templates” pack (recommended, keeps the base installer lean).
- [ ] Approve the Electron architecture (especially D-02 and D-03).
- [ ] Approve the design direction in [`06-DESIGN-SYSTEM.md`](06-DESIGN-SYSTEM.md).
- [ ] Create the `desktop-electron/` scaffold (Phase 0, `T-P0-01`).
- [ ] Generate the API types from `platform_api` OpenAPI (`T-P0-05`).
- [ ] Run the Vizzy hosting spike (`T-P7-01`) before committing to the full Vizzy phase.
