## Project Structure Refactor (Python App) - Tasks

### Goal
Bring `python_app/` to a clean, standard, maintainable structure while preserving behavior:
- Reduce `main.py` responsibilities (composition root only)
- Make module boundaries clear (UI vs controllers vs services vs database)
- Remove runtime-unrelated scripts/artifacts from the runtime package
- Prevent regressions with incremental, reversible steps

### Scope
- Python app only: `python_app/**`
- Shared renderer code used by Python app: `visualizer/**` (only if required by imports)

### Out of Scope
- Electron/React app (`src/**`)
- Worker/concurrency optimization (we will do after structure is clean)

---

## M0 - Inventory and Guardrails
- [x] Document current architecture, critical entrypoints, and dependency directions.
- [x] Add a refactor checklist for "no behavior change" validation.

Acceptance
- Written docs exist and reference real code locations.
- Clear "do not break" flows are listed (launch, profile save, progress, export, upload).

---

## M1 - Repo Hygiene (No Behavior Change)
- [x] Remove committed runtime artifacts from repo:
  - `python_app/debug.log`
  - `python_app/database/video_templates_local.json.*.tmp`
- [x] Add `.gitignore` rules so these do not come back.
- [x] Move maintenance scripts out of runtime package root:
  - `extract_*.py`, `remove_*.py`, `refactor_imports.py`
  - Target location: `python_app/tools/`

Acceptance
- App runs unchanged.
- No runtime artifacts remain tracked in source.
- No Electron/React files remain in active root (archived under `archive/electron-app/`).

---

## M2 - Import Correctness / Packaging Safety
- [x] Fix incorrect imports that depend on working directory or sys.path quirks.
- [x] Standardize internal imports to use package-relative paths.

Acceptance
- `python -m compileall -q python_app` succeeds.
- Running from repo root works: `python -m python_app`.

---

## M3 - Split `main.py` into a Small App Shell (Incremental)
- [x] Introduce `python_app/app/` package:
  - [x] `app/bootstrap.py`
  - [x] `app/main_window.py` (MainWindow moved)
  - [x] `app/ui_bus.py`
- [x] Move UI helper widgets out of `MainWindow` module scope:
  - `app/widgets.py` (e.g., `AppDateEdit`, `PopoutPreviewWindow`)
- [x] Move theme/style building out of `MainWindow`:
  - `app/theme.py` (`build_ui_tokens`, `build_app_stylesheet`)
- [x] Centralize resource path resolution:
  - `app/resources.py` (assets/icons paths)
- [x] Centralize debug logging:
  - `app/logging.py`
- [x] Move code from `main.py` into the new modules in small slices:
  - Keep `main.py` as a thin entrypoint that calls `bootstrap.run()`
- [x] Ensure `views/*` mixins still work with `MainWindow` host methods (no large redesign yet).

Acceptance
- App still starts and works with the same UI.
- `main.py` becomes a small entrypoint (imports minimal).

---

## M4 - Make Feature Modules Explicit (Optional but Recommended)
- [x] Group large feature flows into modules without changing logic:
  - `features/youtube/` (db + services facades used by the app shell)
  - `features/progress/` (view facade used by the app shell)
  - `features/video_export/` (view + export service facades used by the app shell)
- [x] Update `MainWindow` imports to reference `features/*` so feature boundaries are explicit.

Acceptance
- Navigation of code becomes easier (feature folders reduce cross-file hunting).

---

## M5 - Verification + Documentation
- [x] Smoke test critical flows (automated where possible):
  - Launch app (non-interactive)
  - Switch pages (Home, Workflow, Progress, Music, Settings) via `_set_primary_page(...)`
  - Image/Video pages depend on OpenGL/GLSL 3.30+ and should be validated manually on the target machine
  - Save profile and YouTube retry require configured DB credentials and should be validated manually per environment
- [x] Update `python_app/DEVELOPMENT_LOG.md` with refactor entry and migration notes.

Acceptance
- No functional regressions observed.
- Docs explain new structure and where code moved.
