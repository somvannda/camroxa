# Progress Page — Requirements Document

> **Document ID:** CAMXORA-PAGE-06-PROGRESS  
> **Version:** 1.0.0  
> **Status:** Implemented  
> **Phase:** 6  
> **Source of truth:** `camxora/src/renderer/src/features/shell/ProgressPage.tsx`  
> **Target:** `camxora_python/features/progress/`  
> **Last updated:** 2026-07-07

---

# 1. Document purpose

Complete requirements for the Progress page — the **operational pipeline view** for monitoring failures, waiting rows, manual asset handoff, and recovery actions. Must match Electron functional parity using **standard PySide6 widgets + `deep_blue.py` QSS only** (no custom workflow-style panels).

---

# 2. Overview

## 2.1 What Progress is

The Progress page (`/app/progress`) shows filtered progress aggregate rows in a table, with desktop runtime overlays for converter/merger truth, pending Suno download queue, and manual-image recovery actions.

## 2.2 What Progress is not

- Not the visual-only lane board (that's **Workflow**)
- Does not replace Music/Image/Video phase pages

## 2.3 Desktop IPC on this page

Electron uses:
1. `useProgressVideoRuntime` — local MP4 inspection + active export workspace
2. Desktop file API — list run directory images for manual asset inspection
3. `openPath` / `ensureDirectory` — open manual asset folders
4. Settings query — `imageSourceMode` for manual-image recovery UI

Python implements these natively via `video_runtime_inspection.py`, `manual_asset_paths.py`, and `file_service.py`.

---

# 3. Layout structure (standard theme)

```text
[ Toolbar: From, To, Active only, Limit, Stage, Refresh — plain page background ]

[ Helper subtitle ]

[ Summary line — API summary + desktop runtime suffix ]

[ Manual mode notice — subtitle label, hidden when AI mode ]

[ 4 × StatCard row — no wrapper card ]

[ Meta line — visible rows · pending downloads · stage filter ]

[ Error banner — dashboard_error_banner styling ]

[ Operational rows — account_card + data_table ]

[ Desktop download queue — account_card, hidden when empty ]
```

---

# 4. Data requirements

| Source | Endpoint / module |
|--------|-------------------|
| Progress rows | `GET /progress` via `WorkflowLoadWorker` + runtime overlay |
| Settings | `GET /settings` → `imageSourceMode` |
| Pending downloads | `GET /music/downloads/pending?limit=12` |
| Manual sync | `POST /image-jobs/sync-manual` |

---

# 5. Polling

| Stream | Interval |
|--------|----------|
| Progress rows (default) | 12s |
| Progress rows (active only) | 4s |
| Pending downloads (page visible) | 5s |
| Page hidden | Stop timers |

---

# 6. Table columns

Batch, Run Date, Channel, Status, Music, Image, Converter, Merge, YouTube, Stage, Notes, Updated.

Music column includes download pending/ready sub-lines. Notes column includes manual asset inspection + Open Folder / Continue Pipeline when manual mode is active.

---

# 7. Stat cards

| Card | Logic |
|------|-------|
| Active Runs | Rows where effective stage ∉ {done, error} |
| Converter / Merger | effective stage ∈ {converter, merger} |
| Waiting On User | manual mode + Image stage + inspection not ready |
| Failed / Blocked | effective stage = error OR effective status = failed |

---

# 8. Definition of Done

- [x] P-1 Toolbar filters on plain background (standard QDateEdit, QCheckBox, QComboBox, QPushButton)
- [x] P-2 Four StatCards without outer wrapper card
- [x] P-3 Operational table in `account_card` with `data_table`
- [x] P-4 Download queue in `account_card`
- [x] P-5 Runtime overlay for converter/merger/stage/status/notes
- [x] P-6 Manual asset folder inspection + open folder + sync manual
- [x] P-7 Pending downloads polling
- [x] P-8 Error banner with stale-data retention
- [x] P-9 Unit tests for view + manual asset helpers
- [ ] P-10 Manual verify against live `platform_api`

---

# 9. Python modules

| Module | Role |
|--------|------|
| `features/progress/views/progress_view.py` | Page orchestration |
| `features/progress/widgets/stats_row.py` | Four StatCards |
| `features/progress/widgets/operational_rows_card.py` | Table card |
| `features/progress/widgets/download_queue_card.py` | Pending downloads |
| `features/progress/widgets/error_banner.py` | API error banner |
| `shared/lib/manual_asset_paths.py` | Manual asset inspection |
| `shared/workers/data_workers.py` | Load/sync/inspect workers |
