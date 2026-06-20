## Project Structure Refactor (Python App) - Technical

### Existing Architecture (Verified)
- Composition + many host methods live in: [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py)
- UI mixins: `python_app/views/*` (example: [core_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/core_view.py))
- Controllers: `python_app/controllers/*` (example: [music_controller.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py))
- Services: `python_app/services/*` (example: [youtube_uploader.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/youtube_uploader.py))
- Database modules: `python_app/database/*` (example: [youtube_db.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py))
- Models/template schema: `python_app/models/*` (example: [spectrum_model.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/models/spectrum_model.py))

### Current Structural Issues (Verified)
1) Monolithic `main.py`
- `main.py` acts as:
  - entrypoint
  - composition root
  - UI host implementation
  - workflow coordinator
  - feature glue (YouTube, progress, export, images, etc.)
- This makes dependency direction easy to violate and makes refactors risky.

2) Runtime package includes non-runtime artifacts
- Previously, runtime artifacts and one-off tooling scripts lived inside `python_app/` root.
- Current status:
  - Runtime artifacts are ignored (`**/__pycache__/`, `*.py[cod]`) and removed.
  - Maintenance scripts were moved into `python_app/tools/`.

3) Ambiguous data file location
- Source of truth is `python_app/video_templates_local.json`.
- Code reads/writes via [local_templates_path](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/persistence.py#L646-L689).

4) Import correctness risk
- Controller imports that rely on current working directory can break packaging and tooling.

---

## Target Technical Design

### A) Minimal-Churn Module Extraction
Goal: reduce `main.py` without rewriting the app architecture.

Create `python_app/app/`:
- `app/ui_bus.py`
  - `UiBus(QObject)` with `pyqtSignal` definitions
- `app/main_window.py`
  - contains the `MainWindow` class and imports view mixins
- `app/bootstrap.py`
  - `run()` creates QApplication, initializes MainWindow, starts timers

Keep `python_app/main.py`:
- becomes a thin entrypoint: imports `run()` and executes it

### B) Dependency Direction
- `views` should call host methods / controllers, not `database` directly.
- `controllers` may call `database` and `services`.
- `services` should not import `views` or PyQt widgets.
- `database` should not import `views` or controllers.

---

## File Structure Plan

### New
- `python_app/app/`
  - `__init__.py`
  - `bootstrap.py`
  - `main_window.py`
  - `ui_bus.py`
- `python_app/tools/` (move-only)
  - `extract_components.py`
  - `extract_views.py`
  - `remove_components.py`
  - `remove_methods.py`
  - `refactor_imports.py`

### Move / Modify
- `python_app/main.py`
  - reduce to entrypoint + minimal bootstrapping
- `.gitignore`
  - ignore runtime artifacts and temp files

### Remove from source control (runtime-generated)
- `python_app/debug.log`
- `python_app/database/video_templates_local.json.*.tmp`

---

## Migration Strategy (Incremental)

1) Hygiene first (M1)
- remove artifacts + add ignore rules
- move scripts to tools

2) Import correctness (M2)
- fix wrong imports discovered during compileall
- confirm app runs from repo root (`python -m python_app`)

3) Extract app shell (M3)
- create `app/` package
- move UiBus first, then MainWindow class next
- keep method names unchanged to avoid breaking view mixins

4) Optional feature module grouping (M4)
- only after M3 is stable
- create a `python_app/features/` namespace that becomes the canonical import surface for feature flows (YouTube/progress/export)
- keep the existing `views/`, `services/`, and `database/` modules in place (no behavior changes, minimal churn)
- update `MainWindow` to import via `features/*` so feature boundaries are explicit in the app shell

### M4 Detailed Plan (Verified Targets)
Goal: make feature boundaries explicit without rewriting host methods yet.

Create:
- `python_app/features/`
  - `progress/view.py` re-exports [ProgressViewMixin](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/progress_view.py)
  - `video_export/view.py` re-exports [VideoViewMixin](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/video_view.py)
  - `video_export/export.py` re-exports [ExportJob / ExportSettings](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/video_export.py)
  - `youtube/db.py` re-exports [youtube_db](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py) APIs used by the app shell
  - `youtube/oauth.py` re-exports [oauth_connect](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/youtube_oauth.py)
  - `youtube/uploader.py` re-exports [upload_video / list_playlists](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/youtube_uploader.py)

Non-goals in M4 (defer):
- moving host methods out of [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py)
- refactoring feature workflows, threading, or DB schema

---

## Risk Assessment
- High risk: moving large chunks of `main.py` without a safety net (avoid big-bang).
- Medium risk: import path changes (mitigate via `compileall` + smoke run).
- Low risk: moving scripts + ignoring artifacts.

---

## Testing Strategy (Practical)
- `python -m compileall -q python_app`
- Launch app: `python -m python_app`
- Smoke flows:
  - switch pages
  - save profile
  - YouTube connect/disconnect and retry
  - progress page refresh
  - export + merge trigger (one small batch)
