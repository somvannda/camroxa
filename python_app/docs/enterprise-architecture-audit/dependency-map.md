# Dependency Map — MusicGenerator (`python_app/`)

**Generated:** 2026-06-09
**Scope:** All first-level packages under `python_app/`

---

## 1. Package Inventory

| Package | Role | Size (files) |
|---|---|---|
| `app/` | Application shell: bootstrap, main window, UI bus, theme, resources, logging, widgets | 8 |
| `features/` | Feature coordinators: auto_video, merge, persistence, profiles, progress, templates, video_export, youtube | 19 |
| `views/` | UI view mixins & components: dashboard, image, music, progress, settings, video, workflow, youtube | 11 |
| `controllers/` | Controller layer: music_controller, image_controller | 2 |
| `services/` | External integrations: Suno, SLAI image, YouTube, ngrok, callback, video export, dpapi | 12 |
| `database/` | Persistence layer: music_db, image_db, youtube_db, dashboard_db, persistence, migrations, pools | 7 |
| `models/` | Data shapes & normalization: music_model, spectrum_model | 2 |
| `utils/` | Pure utilities: music_common (db connect, text helpers) | 1 |
| `visualizer/` | Audio rendering engine: GPU render, audio analyzer, effects, particles, config | 11 |
| `tools/` | One-off refactoring scripts | 5 |
| `config/` | *(not present — configuration lives in `.env` + `database/persistence.py`)* | 0 |

---

## 2. Target Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                          app/                                    │
│                    (MainWindow, bootstrap)                       │
│          ┌──────────────┴──────────────┐                        │
│          ▼                             ▼                        │
│     features/  ◄──────►  views/  ◄──── controllers/            │
│          │                  │                                   │
│          ▼                  ▼                                   │
│     services/              visualizer/                          │
│          │                  │                                   │
│          ▼                  ▼                                   │
│     database/              models/                              │
│          │                  ▲                                   │
│          ▼                  │                                   │
│       models/  ◄────────────┘                                   │
│          ▲                                                      │
│          │                                                      │
│       utils/ ───────────────────────────────────────────────────┘
│          (imported by many, imports nothing internal)            │
└─────────────────────────────────────────────────────────────────┘

Dependency flows DOWN only (no upward or sideways arrows except noted).
```

### 2.1 Approved Layer Ordering (top → bottom)

| Layer | May depend on |
|---|---|
| `app/` | `features/`, `views/`, `controllers/`, `database/`, `services/`, `models/`, `visualizer/`, `utils/` |
| `views/` | `models/`, `visualizer/`, other `views/` sub-modules |
| `features/` | `services/`, `database/`, `models/`, `utils/`, selected `views/` (bridge contracts only) |
| `controllers/` | `services/`, `database/`, `models/`, `utils/` |
| `services/` | `database/`, `models/`, `utils/` |
| `database/` | `models/`, `utils/` |
| `visualizer/` | `models/` (narrow DTO only), external rendering libs |
| `models/` | stdlib only |
| `utils/` | stdlib + external libs only (no internal packages) |

### 2.2 Forbidden Directions

| Rule | From | → | To | Rationale |
|---|---|---|---|---|
| A | `views/` | → | `database/` | Views must not access persistence directly |
| B | `views/` | → | `services/` | Views must not call provider APIs directly |
| C | `services/` | → | `views/` | Services must not assume UI concerns |
| D | `services/` | → | `app/main_window.py` | Services must not depend on shell internals |
| E | `database/` | → | `views/` or `app/` | Database must not know about UI |
| F | `models/` | → | any internal package | Models are pure data shapes |
| G | `visualizer/` | → | `database/`, `services/`, `app/` | Renderer must be data-in, frames-out |
| H | `features/X` | → | `features/Y` internals | Cross-feature must go through coordinator facade |
| I | `utils/` | → | any internal package | Utils are leaf dependencies |

---

## 3. Actual Dependency Matrix

An "X" means the source package imports from the target package in current code.

```
Source          → targets
───────────────────────────────────────────────────────────────
app/            → features, views, database, services,
                  controllers, models, visualizer, utils

features/       → services, database, models, utils,
                  views (bridge only), app (TYPE_CHECKING + logging)

views/          → visualizer, models
                  (no direct DB or service imports — CLEAN)

controllers/    → database, services, models
                  (no views import — CLEAN)

services/       → database (image_generation.py),
                  utils (music_generation.py)
                  (no views or app imports — CLEAN)

database/       → models (persistence.py),
                  utils (all DB modules)
                  (no views, app, or service imports — CLEAN)

visualizer/     → (no internal imports — CLEAN)

models/         → (no internal imports — CLEAN)

utils/          → (no internal imports — CLEAN)
```

---

## 4. Current Violations & Transition Issues

### 4.1 Fixed Violations

| # | Status | Fix Applied |
|---|---|---|
| V1 | **FIXED** | Progress coordinator now calls `host.youtube_coordinator.list_upload_jobs_for_batches(...)`, `.cancel_jobs_for_row(...)`, `.force_job_pending(...)`, `.get_account(...)` — 6 call sites converted to facade methods |
| V2 | **FIXED** | `print_inline`/`end_inline` moved to `utils/terminal.py`; both `app/logging.py` and `features/youtube/coordinator.py` import from utils layer |
| V6 | **FIXED** | `AutoVideoCoordinator` ffmpeg import fixed from non-existent `utils.ffmpeg_utils` to `services.video_export` |

### 4.2 Remaining Violations

| # | Severity | Source | Imports from | Description |
|---|---|---|---|---|
| V3 | **LOW** | `features/video_export/view.py` | `views/video_view` | Feature package re-exporting a view mixin. Bridge contract (acceptable, documented). |
| V4 | **LOW** | `features/progress/view.py` | `views/progress_view` | Same pattern as V3 — bridge contract. |
| V5 | **MEDIUM** | `app/main_window.py` | ALL packages | MainWindow imports from every layer. Known "god object" being incrementally extracted. Expected during migration but must shrink over time. |

### 4.2 Transitional Exceptions (tolerated)

| # | Source | Imports from | Status |
|---|---|---|---|
| T1 | All `features/*/coordinator.py` | `app.main_window.MainWindow` (TYPE_CHECKING only) | Acceptable — host interface pattern for incremental extraction |
| T2 | `features/youtube/coordinator.py` | `app.logging` | Logged — logging interface should be abstracted |
| T3 | `controllers/*` | `database/`, `services/` | Acceptable — controllers are partial orchestration being superseded by features/ |
| T4 | `app/main_window.py` | direct DB + service calls | Accepted during migration — shrinking over time |

### 4.3 Clean Packages (no violations)

| Package | Status |
|---|---|
| `models/` | CLEAN — no internal imports |
| `utils/` | CLEAN — no internal imports |
| `visualizer/` | CLEAN — no internal imports |
| `views/` | CLEAN — only imports `visualizer/` and `models/` (allowed) |
| `database/` | CLEAN — only imports `models/` and `utils/` (allowed) |

---

## 5. Package Dependency Detail

### 5.1 `app/` dependencies

| Target | Imported by | Notes |
|---|---|---|
| `features/` | `main_window.py`, `bootstrap.py` | All coordinators + export modules |
| `views/` | `main_window.py`, `widgets.py` | All view mixins + components |
| `database/` | `main_window.py` | persistence, music_db, music_migrate, music_pools, image_db |
| `services/` | `main_window.py` | music_generation, music_callback, music_ngrok, music_suno, suno_credits, image_generation, dpapi |
| `controllers/` | `main_window.py` | music_controller, image_controller |
| `models/` | `main_window.py` | music_model, spectrum_model |
| `visualizer/` | `main_window.py` | gpu_render, audio |
| `utils/` | (indirect via other packages) | music_common |

### 5.2 `features/` dependencies

| Feature module | Internal deps |
|---|---|
| `persistence/coordinator` | `database/music_migrate`, `database/persistence`, `models/music_model` |
| `profiles/coordinator` | (TYPE_CHECKING → MainWindow only) |
| `profiles/management` | (TYPE_CHECKING → MainWindow only) |
| `templates/coordinator` | (TYPE_CHECKING → MainWindow only) |
| `templates/management` | `models/spectrum_model`, `database/persistence` |
| `video_export/export` | re-exports `services/video_export` |
| `video_export/workspace` | `services/video_export`, `database/persistence` |
| `video_export/view` | re-exports `views/video_view` |
| `progress/coordinator` | `database/image_db`, `database/music_db`, **`features/youtube/db`** (violation V1) |
| `progress/view` | re-exports `views/progress_view` |
| `youtube/coordinator` | `services/dpapi`, `database/music_db`, `database/persistence`, `database/youtube_db`, `services/video_export`, **`app/logging`** (violation V2) |
| `youtube/oauth` | re-exports `services/youtube_oauth` |
| `youtube/uploader` | `services/youtube_uploader` |
| `youtube/db` | re-exports `database/youtube_db` |
| `auto_video/coordinator` | `database/image_db`, **`utils/ffmpeg_utils`** (broken — V6) |
| `merge/worker` | (no internal imports) |

### 5.3 `controllers/` dependencies

| Controller | Internal deps |
|---|---|
| `music_controller` | `models/music_model`, `database/persistence`, `database/music_db`, `services/music_generation`, `services/suno_lyrics`, `database/music_pools` |
| `image_controller` | `database/image_db`, `database/music_db`, `services/music_suno`, `services/image_generation` |

### 5.4 `services/` dependencies

| Service | Internal deps |
|---|---|
| `music_generation` | `utils/music_common` |
| `image_generation` | `database/image_db`, `database/music_db`, `database/persistence` |
| All others | stdlib + external libs only |

### 5.5 `database/` dependencies

| Module | Internal deps |
|---|---|
| `persistence` | `utils/music_common`, `models/music_model`, `models/spectrum_model` |
| `music_db` | `utils/music_common` |
| `image_db` | `utils/music_common` |
| `youtube_db` | `utils/music_common` |
| `music_migrate` | `utils/music_common` |
| `music_pools` | `utils/music_common` |
| `dashboard_db` | `utils/music_common` |

---

## 6. Target Layering Rules (enforcement checklist)

For every new or modified file, verify:

- [ ] No `database/` import in any `views/` file
- [ ] No `services/` import in any `views/` file
- [ ] No Qt/UI import in any `services/` file
- [ ] No `app/` import in any `services/` file
- [ ] No `views/` or `app/` import in any `database/` file
- [ ] No internal package import in `models/` or `utils/` or `visualizer/`
- [ ] No cross-feature import (feature → feature internals) — use coordinator facade
- [ ] `features/` → `app/` imports are TYPE_CHECKING-only (host interface pattern)
- [ ] New coordinator delegates to existing coordinators, not their internals

---

## 7. Dependency Health Scorecard

| Dimension | Status | Notes |
|---|---|---|
| Leaf purity (models, utils, visualizer) | **GOOD** | Zero internal imports |
| View isolation | **GOOD** | No DB/service imports |
| Database isolation | **GOOD** | No UI/service imports |
| Service isolation | **GOOD** | No UI/app imports |
| Feature cross-talk | **NEEDS WORK** | Progress → YouTube direct (V1) |
| App layering (MainWindow) | **IN PROGRESS** | Known god object, shrinking via coordinators |
| Broken imports | **CRITICAL** | `utils.ffmpeg_utils` missing (V6) |
| Feature → app logging | **NEEDS WORK** | YouTube coordinator depends on app.logging (V2) |

---

## 8. Migration Roadmap (dependency cleanup)

| Priority | Action | Affected files | Risk |
|---|---|---|---|
| P0 | Fix broken `utils.ffmpeg_utils` import in `auto_video/coordinator.py` | `features/auto_video/coordinator.py` | Low — function exists in `services/video_export` |
| P1 | Replace `progress/coordinator` → `features/youtube/db` calls with `YouTubeCoordinator` facade | `features/progress/coordinator.py` (6 sites) | Medium — requires YouTubeCoordinator to expose needed methods |
| P2 | Abstract logging: inject logger into coordinators instead of importing `app.logging` | `features/youtube/coordinator.py` | Low |
| P3 | Continue extracting MainWindow responsibilities into existing coordinators | `app/main_window.py` | High — large file, incremental |
| P4 | Consolidate `controllers/` into `features/` coordinators (or remove if superseded) | `controllers/*` | Medium — verify no orphan logic |

---

*This document should be updated after each architectural change. See `dependency-rules.md` for the rule definitions this map audits against.*
