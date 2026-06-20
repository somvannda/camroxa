## Enterprise Architecture Audit — Design

### Objective
Evolve the Python desktop application from a large host-driven codebase into a team-scalable enterprise-grade application structure without breaking existing business flows.

### What Boss asked for
- Analyze the whole application/codebase
- Focus especially on the oversized `app/main_window.py`
- Prepare a cleaner enterprise-grade structure before continuing more feature growth

---

## Verified current developer-experience pain

### 1) MainWindow is still a god object
Verified:
- `MainWindow` lives in [app/main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py)
- It is ~10,923 lines long
- It inherits multiple view mixins and still owns broad application behavior

This creates the following pain:
- hard to navigate
- hard to review safely
- hard to assign team ownership
- too easy to mix UI, orchestration, DB, and external integration logic

### 2) The app shell still owns too much responsibility
Even after earlier cleanup, the host layer still appears to do all of these:
- bootstrap-connected state ownership
- UI event handling
- feature workflow orchestration
- direct DB access
- service integration calls
- timer/thread coordination
- template/profile persistence
- YouTube upload lifecycle handling

### 3) Multiple other large files still represent scaling risk
Verified hotspots:
- [views/components.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/components.py) ~1,435 lines
- [visualizer/gpu_render.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/visualizer/gpu_render.py) ~3,158 lines
- [views/music_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/music_view.py) ~1,602 lines

This means the structural problem is broader than just `MainWindow`.

---

## Target experience for an enterprise-grade app
A new engineer should be able to answer quickly:
- Where does a feature live?
- Which layer owns the behavior?
- Where is UI-only code?
- Where is workflow/application logic?
- Where are DB calls?
- Where are integrations?
- What can be changed safely without breaking unrelated pages?

The codebase should feel:
- predictable
- modular
- layered
- team-friendly
- testable
- safe for incremental refactor

---

## Target architectural shape

### 1) App Shell
`python_app/app/`

Owns only:
- application bootstrap
- window composition
- dependency wiring
- high-level signal registration
- shared application state injection

Should not remain the main home of feature business logic.

### 2) View Layer
`python_app/views/`

Owns:
- widget creation
- layout structure
- lightweight display/state syncing
- reusable controls/widgets

Should not own:
- DB queries
- workflow state machines
- cross-feature orchestration
- long-running task policy

### 3) Application / Coordinator Layer
Recommended explicit layer to grow next.

Could live under one of these shapes:
- `python_app/application/`
- or `python_app/features/<feature>/coordinator.py`

Owns:
- use-cases
- orchestration
- background job flow
- feature state transitions
- cross-service coordination
- validation before calling DB/services

This is the missing layer currently absorbed by `MainWindow`.

### 4) Services Layer
`python_app/services/`

Owns:
- external integrations
- API clients
- ffmpeg helpers
- OAuth helpers
- provider-specific logic

Must stay reusable and UI-independent.

### 5) Data Layer
`python_app/database/`

Owns:
- persistence
- migrations
- feature-specific DB queries
- storage adapters

Should not be called everywhere from UI host code.

### 6) Domain / Models
`python_app/models/`

Owns:
- normalization
- config shaping
- domain data defaults
- stable structures for templates/settings/profiles/jobs

### 7) Feature Modules
`python_app/features/`

Current feature facades are a useful start, but they are still thin.
Next evolution should make features real ownership boundaries, not just import surfaces.

Example target:
- `features/youtube/`
  - coordinator
  - view bridge
  - db adapter
  - service adapter
  - models/contracts
- `features/video/`
- `features/progress/`
- `features/music/`
- `features/image/`
- `features/templates/`

---

## UX principle for refactor work
Refactor should be mostly invisible to end users.

### Must preserve
- page flows
- keyboard/mouse behavior
- current templates/profiles
- queue operations
- progress page actions
- export and upload behavior

### Must improve for developers
- file ownership clarity
- smaller diffs
- easier regression isolation
- safer feature growth

---

## Design principles for the restructure

### Principle 1 — No god classes
Any class coordinating multiple concerns must be split by responsibility.

### Principle 2 — Dependency direction must be obvious
Preferred direction:
- views -> coordinators/application layer
- coordinators -> services/database/models
- services -> external systems
- database -> storage only

### Principle 3 — Separate reusable visual logic from workflow logic
Preview widgets and render widgets belong in UI/render layers.
Task scheduling and business rules do not.

### Principle 4 — Feature ownership beats file convenience
Code should live where future developers expect it, not where it was easiest to add quickly.

### Principle 5 — Incremental extraction only
No big-bang rewrite.
Everything should be moved in small validated slices.

---

## Recommended restructure priorities

### Priority A — Stabilize architecture rules
Before more feature work, define:
- layer boundaries
- ownership rules
- allowed dependencies
- extraction priorities

### Priority B — Decompose MainWindow by feature coordination
This gives the biggest maintainability win with the least UI churn.

### Priority C — Split reusable UI mega-files
Especially `views/components.py`.

### Priority D — Introduce a stronger application layer
This is the long-term protection against architecture drift.

### Priority E — Clean visualizer boundary separately
The visualizer is a subsystem and should be treated carefully, not mixed into app-shell refactor blindly.

---

## Success definition
This effort succeeds when:
- `MainWindow` becomes a composition host, not a logic warehouse
- each major feature has obvious ownership
- adding a new feature no longer encourages editing 10k-line files
- future engineers can extend YouTube, Progress, Video, Music, Image, or Template flows in isolation
- architectural drift slows down instead of accelerating
