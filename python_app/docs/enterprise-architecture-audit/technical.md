## Enterprise Architecture Audit — Technical

### Scope
This document analyzes the current Python desktop app structure with emphasis on architectural boundaries, oversized modules, and the next enterprise-grade restructuring path.

---

## Verified current structure

### Top-level packages under `python_app/`
- `app/` — bootstrap, app shell, theme/resources/logging/widgets, `MainWindow`
- `views/` — page mixins and shared UI components
- `controllers/` — workflow orchestration helpers for music/image flows
- `services/` — external integrations and non-UI logic
- `database/` — DB access and migrations
- `models/` — normalization/domain shaping
- `features/` — current feature facades for YouTube, progress, video export
- `visualizer/` — rendering/export subsystem
- `tools/` — non-runtime maintenance utilities
- `docs/` — planning artifacts

### Existing structure strengths
Verified strengths already present:
1. Packaging is now proper enough to run via `python -m python_app`.
2. `app/` exists as an app-shell package.
3. `views/`, `services/`, `database/`, and `models/` are already separated physically.
4. Feature facades have started under `features/`.
5. Planning docs already exist for multiple features and prior structure work.

These are strong foundations. The problem is not lack of folders; it is incomplete responsibility separation.

---

## Verified hotspots

### 1) `app/main_window.py`
- Approximate size: **10,923 lines**.
- Declares:
  - [MainWindow](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L113-L113)
- Inherits multiple mixins from `views/*`.
- Directly references DB APIs such as `db_list_profiles`, `db_load_music_app_data`, `db_enqueue_youtube_upload_job`, and many more.
- Directly calls external-service functions like `upload_video(...)` and `oauth_connect(...)`.
- Contains timer/thread/process-related logic (multiple timer/thread/subprocess usages detected).

### 2) `views/components.py`
- Approximate size: **1,435 lines**.
- Contains preview/render-related widget logic and multiple reusable UI helpers.
- This file is becoming a second hotspot and should eventually be split into smaller UI-focused modules.

### 3) `visualizer/gpu_render.py`
- Approximate size: **3,158 lines**.
- This is a heavy specialized rendering subsystem.
- It should not be refactored casually together with app-shell decomposition.
- Needs interface cleanup first, not arbitrary file splitting.

### 4) `views/music_view.py`
- Approximate size: **1,602 lines**.
- Indicates that the music feature UI surface is itself large and may need sub-views/section modules later.

---

## Verified architectural behavior

### MainWindow current role
`MainWindow` is still acting as all of the following at once:
- page composition host
- signal/event host
- page action handler
- app state container
- workflow coordinator
- DB integration surface
- service integration surface
- background polling owner
- YouTube upload lifecycle owner
- template/profile management owner

This is the primary enterprise-grade risk in the current codebase.

### View layer current role
`views/*` mixins help separate page construction, but they still rely on host methods implemented by `MainWindow`.
This means page structure moved out, but feature behavior largely did not.

### Controllers current role
`controllers/` exists and is useful, but its role is not yet broad enough to absorb most host-level orchestration.
This is a sign that the application/use-case layer is underdeveloped.

### Features current role
`features/*` currently acts mainly as a façade/re-export surface.
This is good for import clarity, but not yet enough for enterprise ownership boundaries.

---

## Key structural problems

### Problem 1 — Incomplete separation after initial refactor
The project already performed early refactor wins:
- shell package introduced
- theme/logging/resources/widgets extracted
- feature façade imports added

But the core behavior still centralizes in `MainWindow`.

### Problem 2 — Direct DB/service coupling from app shell
Verified by direct DB call usage inside `MainWindow`.
This means the UI host is still tightly coupled to persistence and integration details.

### Problem 3 — Orchestration is not a first-class layer
The application layer that should own:
- use cases
- feature coordination
- background task policy
- state transitions

is mostly implicit and still embedded in host methods.

### Problem 4 — UI mega-files are emerging
Even if `MainWindow` is reduced, files like `views/components.py` and `views/music_view.py` will continue to slow scaling if not addressed after the app-shell split.

### Problem 5 — Runtime artifacts still need hygiene attention
Verified in current tree:
- `python_app/.env`
- `python_app/debug.log`
- `python_app/app/debug.log`
- `python_app/video_templates_local.json`
- temporary template JSON file under root

Not all of these are necessarily wrong for runtime, but enterprise hygiene requires a clear policy for:
- committed vs ignored runtime files
- app-data storage location
- temp file cleanup policy
- debug log location policy

---

## Recommended enterprise target model

### Layering rule
Recommended dependency direction:
- `app/` -> `features/` and app-level wiring only
- `views/` -> host interface / coordinator interface only
- `features/` / `application/` -> `services/`, `database/`, `models/`
- `services/` -> external APIs/tools
- `database/` -> DB only
- `models/` -> pure shaping/validation/defaults
- `visualizer/` -> rendering subsystem behind a clear interface

### Recommended missing layer
Introduce a true application/coordinator layer.

Preferred shapes:
1. `python_app/application/`
   - `music/`
   - `youtube/`
   - `progress/`
   - `video/`
   - `templates/`
2. or richer `features/<feature>/coordinator.py` modules

Either is fine, but one must become the primary owner of orchestration.

### Recommended role of MainWindow after refactor
Target `MainWindow` responsibility:
- own top-level widgets and page shell
- register signals/callbacks
- provide shared dependencies/context
- delegate actions to feature coordinators
- render high-level state changes only

Target `MainWindow` non-responsibilities:
- direct DB transaction logic
- direct service client workflows
- retry/backoff policy
- complex queue handling
- long-running task state machines
- feature-specific persistence rules

---

## Recommended extraction roadmap

### Stage A — Architecture governance
Before moving code again, define:
- allowed dependency directions
- package ownership map
- naming conventions for coordinators/use-cases
- extraction validation checklist

### Stage B — MainWindow coordinator extraction
Most valuable early slices:
1. DB settings + migration coordinator
2. profile/template coordinator
3. YouTube account/OAuth coordinator
4. YouTube queue/upload coordinator
5. progress page action coordinator
6. video workspace/template state coordinator

These slices match current major risk zones without requiring a full rewrite.

### Stage C — UI file decomposition
After MainWindow starts shrinking:
- split `views/components.py`
- split `views/music_view.py` into section builders if needed
- standardize shared widget modules

### Stage D — Visualizer boundary hardening
Do separately from app-shell cleanup:
- define DTO/runtime payloads into visualizer
- isolate preview/export shared contracts
- avoid blending renderer refactor with UI host refactor

---

## Enterprise standards to add

### 1) Module ownership map
Each feature/package should answer:
- owner layer
- allowed dependencies
- entrypoints
- main workflows

### 2) Error-handling conventions
Current app likely mixes UI messages, logs, and exception handling styles.
Define a consistent strategy.

### 3) Background task conventions
Threads, timers, polling, and subprocess lifecycles need explicit standards.
Especially important because `MainWindow` currently owns many of these behaviors.

### 4) Runtime data policy
Clarify where these belong:
- local templates
- debug logs
- temp files
- cache files
- exported artifacts
- credentials/config

### 5) Test strategy
At minimum, introduce:
- smoke validation checklist
- non-UI logic tests for extracted coordinators/services
- DB contract tests where practical
- renderer interface tests at the boundary level

---

## Recommended next execution slice

### Slice 1 (best immediate next step)
Do not start by moving random methods.
Start by creating architecture governance artifacts:
- package ownership map
- dependency rules
- coordinator naming/placement standard
- prioritized extraction map for `MainWindow`

### Slice 2
Extract the lowest-risk, highest-value coordinator:
- DB settings + profile/template management

### Slice 3
Extract the YouTube feature coordination layer
because it is both high-risk and currently heavily coupled to `MainWindow`.

---

## Conclusion
The codebase is not structurally broken, but it is in a **high architectural drift zone**.

Good news:
- foundational package separation already exists
- documentation culture already exists
- feature façade direction already started

Main risk:
- behavior ownership still lives mostly inside one enormous host class

For enterprise-grade evolution, the next step is **not** a rewrite.
It is a controlled transition from:
- big host methods
into
- feature coordinators + explicit layer boundaries.
