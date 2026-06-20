# Dependency Rules & Forbidden Directions

## Purpose
Create explicit dependency rules so the codebase stops drifting back into `MainWindow`-centric architecture.

---

## Approved Dependency Direction

### Preferred flow
- `app/` -> `features/`, `views/`, `models/`
- `views/` -> coordinator/host interfaces, `models/`, UI helpers
- `features/` -> `services/`, `database/`, `models/`, selected `views/` bridge contracts if needed
- `controllers/` -> `services/`, `database/`, `models/`
- `services/` -> `models/`, `utils/`, external libraries
- `database/` -> `models/`, DB libraries
- `models/` -> stdlib only where practical
- `visualizer/` -> rendering libs, DTO/config inputs, `models/` if kept narrow

### Mental model
- UI sends intent downward.
- Coordinators orchestrate.
- Services integrate.
- Database persists.
- Models shape data.

---

## Forbidden Directions

### Rule A
`views/` must not import or call `database/` directly.

### Rule B
`views/` must not import provider/service modules like YouTube/Suno/export service implementations directly for feature workflows.

### Rule C
`services/` must not import Qt widgets/pages or assume UI message-box behavior.

### Rule D
`database/` must not import `views/` or depend on page-specific UI concerns.

### Rule E
`models/` must not call DB, network APIs, or Qt.

### Rule F
`visualizer/` must not query the DB or depend on `MainWindow` internals.

### Rule G
`app/main_window.py` must not remain the final home of feature orchestration once a coordinator exists for that feature.

### Rule H
One feature module should not reach deeply into another feature's internals; cross-feature interaction should happen through a stable coordinator/facade boundary.

---

## Practical Rules for New Code

### When adding a new user action
Ask:
1. Is it pure UI layout? -> `views/`
2. Is it orchestration/use-case logic? -> `features/` or future application layer
3. Is it provider/tool integration? -> `services/`
4. Is it persistence? -> `database/`
5. Is it data normalization? -> `models/`

### When touching `MainWindow`
Allowed:
- connect signal to coordinator
- delegate to feature host
- update top-level window state
- manage app-shell composition

Not allowed long-term:
- implement entire feature workflow inline
- perform direct DB-heavy business flows
- own retry/polling policy for a feature that has a coordinator home

---

## Transitional Exceptions
Because the app is mid-refactor, the following are temporarily tolerated:
- `views/*` mixins depending on host methods implemented by `MainWindow`
- `controllers/` existing as partial orchestration helpers
- `MainWindow` directly calling some DB/service functions while extraction is incomplete

These are tolerated only as migration-state exceptions, not target architecture.

---

## Enforcement Strategy

### Immediate manual enforcement
During every change, review:
- Did this add new DB calls to a view or host method?
- Did this add new provider logic to `MainWindow`?
- Did this place orchestration in the wrong layer?

### Near-term enforcement
Add lightweight review checklist items:
- no new direct DB access from views
- no new provider workflow logic in views
- no new orchestration dumped into `MainWindow`
- no new UI assumptions inside services

### Longer-term enforcement
Potential future automation:
- import-lint rules
- architecture tests
- grep-based CI guardrails for forbidden imports

---

## Known Current Violations to Reduce
- `MainWindow` directly calling DB APIs
- `MainWindow` directly invoking external service workflows
- host methods acting as application layer
- view mixins depending on broad host behavior rather than narrow interfaces

These violations should be removed incrementally, not all at once.
