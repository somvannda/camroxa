# Coordinator / Application Layer Conventions

## Purpose
Define where orchestration code should live after it is extracted from `MainWindow`, and how those modules should behave.

---

## Why this layer is needed
Current verified problem:
- `MainWindow` still acts as the application layer for many features.
- `controllers/` exist but are not yet the primary home for feature coordination.
- `features/*` currently exist but are still thin in several areas.

To become enterprise-grade, orchestration must become a first-class concept.

---

## Recommended placement

### Preferred placement for this codebase
Use `features/<feature>/` as the primary ownership boundary for orchestration.

Examples:
- `features/youtube/coordinator.py`
- `features/progress/coordinator.py`
- `features/video_export/coordinator.py`
- future `features/music/coordinator.py`
- future `features/image/coordinator.py`
- future `features/templates/coordinator.py`
- future `features/profiles/coordinator.py`

### Why this is preferred over a generic `application/` folder right now
- Your repo already has a `features/` direction started.
- It is easier for future developers to find behavior by feature.
- It supports incremental extraction from `MainWindow` without forcing a larger package rewrite first.

A generic `application/` package can still be introduced later if orchestration becomes cross-feature and large enough.

---

## Coordinator Responsibilities
A coordinator may:
- receive user intents from app shell/view bridges
- validate state and inputs
- call one or more services/database modules
- decide workflow sequencing
- decide retry/recovery policy for the feature
- shape UI-facing result payloads/events
- coordinate timers/polling/background jobs if that feature owns them

A coordinator must not:
- build Qt widget trees
- directly draw UI
- contain low-level DB implementation details
- contain raw provider client implementation details already owned by services

---

## Suggested file pattern per feature

### Minimum pattern
- `features/<feature>/__init__.py`
- `features/<feature>/coordinator.py`

### Better pattern as feature grows
- `features/<feature>/coordinator.py`
- `features/<feature>/contracts.py`
- `features/<feature>/db.py`
- `features/<feature>/service.py` or adapter wrappers
- `features/<feature>/view.py` for view bridge helpers only

Use only what the feature needs.

---

## Naming conventions

### Class names
Use explicit names such as:
- `YouTubeCoordinator`
- `ProgressCoordinator`
- `VideoTemplateCoordinator`
- `ProfileCoordinator`
- `MusicGenerationCoordinator`

Avoid vague names like:
- `Manager`
- `Handler`
- `Helper`

unless the responsibility is truly narrow and technical.

### Method names
Coordinator methods should be intent-based, for example:
- `start_upload(...)`
- `retry_upload(...)`
- `refresh_progress(...)`
- `save_profile(...)`
- `load_template(...)`
- `enqueue_music_jobs(...)`

Avoid names that leak implementation details unless needed.

---

## Coordinator interaction style

### From MainWindow / app shell
Preferred:
- app shell receives UI signal
- app shell delegates to feature coordinator
- coordinator returns result / emits event / calls callback bridge
- app shell updates top-level state only when needed

### From views
Views should not know the coordinator internals.
They should talk through:
- host callbacks
- narrow bridge methods
- signals/events

### Between coordinators
If cross-feature coordination is required:
- prefer a stable public method/facade
- do not reach into another coordinator's internal helpers

---

## State ownership guidance

### UI state
Belongs in views or app shell when purely presentational.

### Workflow state
Belongs in the coordinator if it affects sequencing, retry policy, pending/running/failed state, or task lifecycle.

### Persisted state
Belongs in DB modules and domain models, accessed through coordinator workflows.

---

## Error-handling conventions
Coordinator should:
- catch integration/persistence failures where a user-facing decision is needed
- convert low-level exceptions into actionable app outcomes
- log technical details without forcing services to know the UI layer

Service modules should not decide message-box behavior.
Database modules should not decide user-facing recovery wording.

---

## Background task conventions
If a feature owns polling or workers, the coordinator should become the main policy owner for:
- when polling starts/stops
- concurrency limits
- retry policy
- state transitions
- cancellation semantics

This is especially important for:
- YouTube upload queue
- progress refresh actions
- music/image generation workflows
- export lifecycle

---

## Migration rule from MainWindow
When extracting logic:
1. keep existing public UI behavior unchanged
2. move orchestration logic first
3. leave small UI glue in `MainWindow`
4. do not move raw widget construction into coordinator
5. remove direct DB/service calls from host once coordinator path exists

---

## First recommended coordinators for this codebase
1. `ProfileCoordinator`
2. `VideoTemplateCoordinator`
3. `YouTubeCoordinator`
4. `ProgressCoordinator`
5. `MusicGenerationCoordinator`
6. `ImageGenerationCoordinator`

These align directly with current high-coupling zones in `MainWindow`.
