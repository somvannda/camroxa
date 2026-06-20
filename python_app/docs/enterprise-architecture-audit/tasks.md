## Enterprise Architecture Audit & Restructure Plan

### Goal
Prepare the Python desktop application for enterprise-grade maintainability, scalability, and team development without breaking current production workflows.

### Verified Current Priorities
- `app/main_window.py` is still a monolithic host file at ~10,923 lines.
- `views/components.py` is also large (~1,435 lines).
- `visualizer/gpu_render.py` is a major subsystem (~3,158 lines).
- UI mixins exist, but orchestration and state ownership are still concentrated in `MainWindow`.
- `MainWindow` directly touches DB APIs, service APIs, threads/timers, feature flows, and UI state.

---

## Phase 0 — Guardrails
- [ ] Define non-breaking refactor policy for all future extraction work
- [ ] Freeze feature rewrites while structural decomposition is in progress
- [ ] Create a module ownership map for every top-level package in `python_app/`
- [ ] Add a refactor checklist for smoke validation after each extraction step

### Must-not-break flows
- [ ] App bootstrap / launch
- [ ] Page navigation
- [ ] Music generation
- [ ] Image generation
- [ ] Progress page refresh / actions
- [ ] Video workspace preview
- [ ] Video export / merge
- [ ] YouTube OAuth / queue / upload
- [ ] Profile save/load
- [ ] Template save/load

---

## Phase 1 — Architecture Baseline
- [ ] Produce a dependency map for:
  - [ ] `app/`
  - [ ] `views/`
  - [ ] `controllers/`
  - [ ] `services/`
  - [ ] `database/`
  - [ ] `models/`
  - [ ] `features/`
  - [ ] `visualizer/`
- [ ] Classify every large file by responsibility
- [ ] Identify forbidden dependency directions and current violations
- [ ] Define target layering rules and naming conventions

---

## Phase 2 — MainWindow Decomposition
- [ ] Split `MainWindow` into feature coordinators without changing visible behavior
- [ ] Extract DB-facing host logic into application services / coordinators
- [ ] Extract long-running worker orchestration out of `MainWindow`
- [ ] Extract page-specific command handlers into feature host modules
- [ ] Reduce `MainWindow` to:
  - [ ] app composition
  - [ ] signal wiring
  - [ ] shared state injection
  - [ ] page shell coordination

### Candidate extraction slices
- [ ] Music profile management coordinator
- [ ] YouTube account / OAuth coordinator
- [ ] YouTube queue and upload coordinator
- [ ] Progress page actions coordinator
- [ ] Template management coordinator
- [ ] Video workspace state coordinator
- [~] DB settings and migration coordinator — Slice 3 moved bootstrap/hydration, DB collection reload, settings patch persistence, and migrate+reload orchestration behind `features/persistence/coordinator.py`; broader persistence-related host logic still remains in `MainWindow`

---

## Phase 3 — UI Layer Cleanup
- [ ] Keep `views/*` focused on widget construction and lightweight view behavior
- [ ] Split oversized `views/components.py` into focused modules:
  - [ ] preview widgets
  - [ ] image helpers
  - [ ] text/overlay helpers
  - [ ] reusable controls
- [ ] Audit which mixin methods are actually view responsibilities vs orchestration responsibilities
- [ ] Standardize host-method interface between mixins and coordinators

---

## Phase 4 — Workflow / Application Layer
- [ ] Formalize a real application layer between UI and DB/services
- [ ] Convert current ad-hoc host methods into feature-oriented coordinators/use-cases
- [ ] Move workflow state machines out of UI host class
- [ ] Centralize background job scheduling / polling policies
- [ ] Normalize event payload contracts emitted through `UiBus`

---

## Phase 5 — Data Layer Standardization
- [ ] Review DB modules for consistent boundaries and naming
- [ ] Separate persistence concerns from app-specific aggregation helpers
- [ ] Introduce explicit repository/service boundaries where needed
- [ ] Reduce direct DB calls from `MainWindow`
- [ ] Plan transaction/error handling conventions

---

## Phase 6 — Visualizer Boundary Cleanup
- [ ] Define clear interface between app shell and `visualizer/`
- [ ] Reduce duplicated timing/render behavior between Qt preview and GPU renderer where practical
- [ ] Separate render model preparation from drawing implementation
- [ ] Document performance-sensitive areas before major render refactors

---

## Phase 7 — Cross-Cutting Enterprise Standards
- [ ] Logging strategy
- [ ] Error reporting strategy
- [ ] Background task lifecycle strategy
- [ ] Configuration/secrets strategy
- [ ] File/path management strategy
- [ ] Test strategy for UI + non-UI layers
- [ ] Documentation and module ownership strategy

---

## Phase 8 — Incremental Execution Order (Recommended)
- [ ] Slice A: document architecture rules + dependency rules
- [~] Slice B: extract DB/settings/profile coordinators from `MainWindow` — profile/template delegation boundary is in place and persistence Slice 3 internal migration has started
- [~] Slice C: extract YouTube feature coordinator — UI-facing YouTube jobs-table orchestration, selected-job handling, retry/cancel entry routing, profile connect/disconnect entrypoints, timer creation / auto-poll sync, OAuth connect start/cancel worker lifecycle, connect-result bus-event handling for `youtube_connect_select_channel` / `youtube_connect_done`, playlist fetch/cache result handling, upload status/progress/done bus-event handling, merged-output scan/enqueue routing, upload tick / queue-claiming policy, the shared runtime helper cluster (`worker_limit`, `short_job_uid`, `render_terminal_progress`, `is_mp4_ready_for_upload`), the active-upload cancel/runtime-state seam (`worker_jobs_map`, `cancel_runtime_jobs`, `cancel_active_upload`, `complete_runtime_job`), coordinator-owned throttled upload-progress callback creation, OAuth credential loading (`get_upload_credentials`), upload metadata rendering (`render_upload_metadata`), thumbnail path resolution (`resolve_thumbnail_path`), upload warning builder (`build_upload_warnings`), scopes resolution (`resolve_scopes`), processing-failure detection (`is_processing_failed`), exception retry classification (`classify_upload_exception`), upload-start status message builder (`build_upload_start_status_message`), post-upload notification message builder (`build_post_upload_notification_messages`), retry action computation (`compute_retry_action`), profile resolution for upload (`resolve_profile_for_upload`), same-day collision detection (`detect_same_day_collision`), and existing-video retry (`retry_existing_video_upload`) now live behind `features/youtube/coordinator.py`; host-owned seams in `_run_one_youtube_upload_job(...)` are now ~85 lines of tightly-coupled execution flow (debug-point HTTP calls, cancel-state DB updates, direct bus event emissions, DB mark-ready/failed/pending orchestration, and fresh upload execution) — further extraction would over-complicate the architecture
- [~] Slice D: extract progress / auto-video / merge coordinators — auto-video channel preparation (`_try_start_auto_video_channel`) now uses `AutoVideoCoordinator.resolve_channel_plan(...)` which resolves all inputs (ffmpeg, MP3 scan, background image, template, output resolution, worker count) into a single plan object; MP4 merge logic (`_merge_mp4s`, ~156 lines) deleted and replaced by `MergeWorker.merge(...)` with file validation, shuffle with order log, FFmpeg concat demuxer with re-encode fallback
- [ ] Slice E: extract video/template coordinator
- [ ] Slice F: split `views/components.py`
- [ ] Slice G: establish test harness / smoke scripts

---

## Acceptance Criteria
- [ ] `MainWindow` is no longer the primary home for feature business logic
- [ ] Dependency direction is explicit and documented
- [ ] UI code no longer directly coordinates complex workflow state transitions
- [ ] DB/service calls are mediated through clearer application-layer modules
- [ ] Large files are reduced incrementally with no feature regressions
- [ ] New developers can locate ownership of a feature quickly
