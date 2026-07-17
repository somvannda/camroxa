# Workflow Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-05-WORKFLOW  
> **Version:** 1.0.0  
> **Status:** Approved for implementation  
> **Phase:** 5  
> **Source of truth:** `camxora/src/renderer/src/features/shell/WorkflowPage.tsx`  
> **Target:** `camxora_python/features/workflow/`  
> **Last updated:** 2026-07-07

---

# 1. Document purpose

Complete requirements for the Workflow page — a **visual-only pipeline board** for one selected progress run at a time. Must match **100% functional parity** with Electron. Native PySide6 + `deep_blue.py` QSS.

**Build rule:** Do not mark Workflow complete until every item in **§14 Definition of Done** is checked.

---

# 2. Overview

## 2.1 What Workflow is

The Workflow page (`/app/workflow`) shows **run lanes** from the progress aggregate API, lets the user pick one lane, and renders a **5-stage board** (Music → Image → Converter → Merger → YouTube) with desktop runtime overlays for converter/merger when local MP4 outputs exist.

## 2.2 What Workflow is not

- Not an operational recovery page — no download/retry/folder actions (that's **Progress**)
- Not a batch editor
- Does not mutate API data

## 2.3 Desktop IPC on this page

Electron uses `useProgressVideoRuntime` to:
1. List local run directory entries via desktop API
2. Read active video export workspace state
3. Override converter/merger stage, status, notes, and percents when local outputs or active export detected

Python must port `videoRuntimeInspection.ts` and inspect directories natively (this app **is** the desktop runtime).

---

# 3. Entry points & navigation

| Property | Value |
|----------|-------|
| Path | `/app/workflow` |
| Sidebar key | `workflow` |
| Label | Workflow |
| Eyebrow | Workspace |
| Description | Timeline view for the selected run and channel, driven by the shared progress aggregate feed. |

---

# 4. Data requirements

## 4.1 Progress rows API

| Method | Path | Params |
|--------|------|--------|
| GET | `/api/v1/progress` | `limit=80`, `active_only`, `from_date`, `to_date` |

**Python:** `PlatformApi.list_progress()` via `WorkflowLoadWorker`.

## 4.2 Desktop runtime overlay

After rows load, for each row with `meta.run_dir`:
- List directory entries (max 500)
- Classify `.mp4` files: long, reel, merged long, merged reel
- Merge with optional `VideoWorkspaceState` (active export/merge)
- Produce `ProgressRuntimePresentation` per lane key `{batch_id}:{profile_id}:{role}`

**Python:** `shared/lib/video_runtime_inspection.py` + `VideoWorkspaceService` (stub until Video phase wires live export state).

## 4.3 Polling

| Condition | Interval |
|-----------|----------|
| Default | 12s |
| Active only checked | 4s |
| Page hidden / deactivated | Stop timer |

Manual **Refresh** button re-fetches immediately.

---

# 5. Layout structure

```text
[ Filter card: summary chips + date range + active only + refresh + helper text ]

[ Error banner — on API failure ]

[ Empty state — loading or no runs ]

[ Two-column body when rows exist ]
  [ Run Lanes list (320px-ish) ]  [ Selected Run panel ]
                                    - Header + pipeline badge + 5 metric tiles
                                    - Stage board (5 cards)
                                    - Notes | Asset Readiness | Upload Snapshot
```

---

# 6. Functional requirements

## FR-1 — Filter toolbar

| ID | Requirement |
|----|-------------|
| FR-1.1 | Summary chips: `{n} runs`, `{n} active`, `{n} need attention`, `{n} done` |
| FR-1.2 | Date pickers From/To (default today) |
| FR-1.3 | Active only toggle |
| FR-1.4 | Refresh button; disabled while fetching |
| FR-1.5 | Helper text: *"One selected run, visual only. Use `Progress` for recovery actions..."* |

## FR-2 — Error & empty states

| ID | Requirement |
|----|-------------|
| FR-2.1 | Error banner: *"Workflow data could not be loaded from the progress aggregate API."* |
| FR-2.2 | Loading empty: *"Loading workflow runs..."* / *"Refreshing the visual pipeline board."* |
| FR-2.3 | Empty: *"No runs found"* / widen date range hint |

## FR-3 — Run lanes list

| ID | Requirement |
|----|-------------|
| FR-3.1 | Title **Run Lanes** + subtitle *"Pick one lane to inspect visually."* |
| FR-3.2 | Each lane: channel, role badge (Primary/Secondary), run date, stage/status pills, song/bg/th metrics, notes |
| FR-3.3 | Selected lane highlighted (fuchsia border) |
| FR-3.4 | Auto-select first lane when selection invalid |
| FR-3.5 | Stage/status pills use tone colors (done=emerald, running=sky, failed=rose) |

## FR-4 — Selected run header

| ID | Requirement |
|----|-------------|
| FR-4.1 | Channel name + role + effective stage/status pills |
| FR-4.2 | Run date + last updated |
| FR-4.3 | **Current focus** paragraph from `build_current_focus()` |
| FR-4.4 | Pipeline badge: *Music -> Image -> Converter -> Merger -> YouTube* |
| FR-4.5 | Five metric tiles: Songs, Images, Converter, Merger, YouTube |

## FR-5 — Stage board

| ID | Requirement |
|----|-------------|
| FR-5.1 | Five steps with state colors: done / running / failed / inactive |
| FR-5.2 | Each card: title, duration, progress bar, percent, two detail lines |
| FR-5.3 | Converter/merger percent and labels from runtime overlay when present |
| FR-5.4 | Subtitle: *"Converter and merger cards reflect the real desktop runtime..."* |

## FR-6 — Detail panels

| ID | Requirement |
|----|-------------|
| FR-6.1 | **Notes** — runtime notes or row notes |
| FR-6.2 | **Asset Readiness** — Long/Reel Ready/Waiting + run_dir |
| FR-6.3 | **Upload Snapshot** — status + success/pending/failed counts + youtube_url |

---

# 7. Workflow step logic

Port `buildWorkflowSteps()` from `WorkflowPage.tsx` including:
- Music percent from `saved/expected`
- Image percent from avg of bg/th readiness
- YouTube percent from success/pending/failed counts
- `stateFor()` using effective stage from runtime
- Runtime overrides for converter/merger when downstream complete or desktop inspection active

Port helpers: `build_current_focus`, `build_selected_run_metrics`, `format_role_label`, `stage_tone_classes`.

---

# 8. Test requirements

| Test ID | Scenario | Assert |
|---------|----------|--------|
| T-1 | Loading | Empty state loading copy |
| T-2 | Error | Error banner exact message |
| T-3 | Success | Lane list + 5 stage cards bind |
| T-4 | Steps | Music stage running at 40% for 2/5 saved |
| T-5 | Runtime | MP4 inspection marks converter completed |
| T-6 | Runtime | Active export workspace sets Converting stage |

---

# 9. Implementation structure

```text
features/workflow/
  views/workflow_view.py
  widgets/          — filter, lanes, selected panel, stage cards, error, empty
  lib/workflow_steps.py

shared/
  lib/video_runtime_inspection.py
  services/file_service.py
  services/video_workspace_service.py  — stub until Video phase
  workers/data_workers.py              — WorkflowLoadWorker
```

---

# 10. Electron source reference

| Area | File |
|------|------|
| UI | `camxora/src/renderer/src/features/shell/WorkflowPage.tsx` |
| Progress query | `camxora/src/renderer/src/features/shell/useProgressRowsQuery.ts` |
| Video runtime | `camxora/src/renderer/src/features/shell/useProgressVideoRuntime.ts` |
| Inspection | `camxora/src/renderer/src/shared/lib/videoRuntimeInspection.ts` |
| Tests | `camxora/src/renderer/src/shared/lib/videoRuntimeInspection.test.ts` |

---

# 11. Definition of Done (100% checklist)

### Data & lifecycle
- [x] **W-1** Fetch progress rows with filters; poll 12s / 4s active-only
- [x] **W-2** Desktop directory inspection + runtime map
- [x] **W-3** Refresh button + deactivate stops polling; 1.5s runtime poll during export

### UI sections (FR-1–FR-6)
- [x] **W-4** Summary chips + filter toolbar + helper text (layout: chips left, controls right)
- [x] **W-5** Error banner + loading/empty states; stale rows kept on error
- [x] **W-6** Run lanes list (320px) with selection + tone pills
- [x] **W-7** Selected run header + metrics + current focus + pipeline badge
- [x] **W-8** Five-column stage board with state colors + step icons
- [x] **W-9** Notes / Asset Readiness / Upload Snapshot panels (1.4:1:1)

### Logic
- [x] **W-10** `build_workflow_steps` parity with runtime overlay
- [x] **W-11** `video_runtime_inspection` port + tests

### Quality
- [x] **W-12** Tests T-1 through T-6 passing
- [ ] **W-13** Manual verify with live API + local run directory
- [x] **W-14** `02_IMPLEMENTATION_STATUS.md` updated: Workflow ✅

---

# 12. Revision history

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-07-07 | AI + user | Initial requirements from Electron WorkflowPage |
