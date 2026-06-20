## Project Structure Refactor (Python App) - Design

### Product Goal (Developer Experience)
Make the Python app codebase feel like a standard, team-scalable project:
- Easy to find code by responsibility and feature
- Clear boundaries that prevent "god modules"
- Predictable locations for UI, workflow logic, data access, and integrations
- Safer changes with smaller diffs and clearer ownership

### Guiding Rules (Aligned with Boss rules)
- No fake behavior: refactor must not silently change logic.
- Preserve existing architecture patterns unless replacing them deliberately.
- Avoid duplicate systems: reuse existing `controllers/`, `services/`, `database/`.
- Keep files focused: reduce oversized `main.py` via incremental extraction.
- Keep UI functional: no UI-only changes without matching logic.

---

## Current UX Pain (Developer UX)
- `python_app/main.py` is the primary place to implement almost everything, which makes:
  - navigation hard
  - regressions more likely
  - code review difficult
- Runtime package root contains non-runtime scripts and artifacts, which:
  - confuses new contributors
  - increases accidental imports and coupling

---

## Target Structure (High-Level)

### 1) App Shell
`python_app/app/`
- owns app startup and the main window composition
- defines the UiBus and app-level signals
- wires controllers, services, and views

### 2) UI Layer
`python_app/views/`
- PyQt views and mixins (keep existing patterns)
- shared widgets/helpers stay in `views/components.py`
- goal is "UI should not directly talk to DB"; it should call host methods / controller APIs

### 3) Workflow Layer
`python_app/controllers/`
- orchestration: threads, polling, job triggering, pipeline state machines

### 4) Integration Layer
`python_app/services/`
- external dependencies: YouTube, Suno, ffmpeg, DPAPI, image APIs
- services should be reusable and not depend on PyQt widgets

### 5) Data Layer
`python_app/database/`
- feature DB modules (youtube_db, image_db, music_db)
- migrations and persistence utilities

### 6) Domain / Models
`python_app/models/`
- templates, settings normalization, typed data objects

### 7) Tools (Non-Runtime)
`python_app/tools/`
- refactor/extract/remove scripts
- never imported by runtime code

---

## Interaction / Behavior Requirements (No Regressions)
- App startup still uses the same entrypoint command.
- Existing signals/events work unchanged (`UiBus` emit patterns).
- Progress page continues to show updated pipeline status.
- YouTube retry and terminal logging continues to work.
- No change to DB schema or existing migrations as part of structure work (unless needed for correctness).

---

## Accessibility / UI Considerations
- This refactor is mostly internal. UI changes should be avoided.
- If any UI changes are required for wiring (e.g., imports), they must preserve:
  - keyboard behavior
  - current styling
  - current user flows
