# Requirements Document

## Introduction

`main_window.py` is a 7 000+ line God class (`MainWindow`) that directly orchestrates every
domain of the application: UI widget construction, theme helpers, export-batch state management,
database persistence, music generation, image generation, YouTube upload orchestration, calendar
widgets, footer status, and multiple polling timers — all in a single file that also carries
inline debug probes, duplicate import blocks, a known `removed` variable bug, and no central
timer lifecycle.

This refactoring extracts each responsibility into a dedicated, single-purpose module while
preserving all existing runtime behaviour and without introducing new third-party dependencies.
The result must pass the existing manual smoke tests and allow each extracted module to be
tested in isolation.

---

## Glossary

- **MainWindow**: The top-level `QMainWindow` subclass currently in `python_app/app/main_window.py`.
- **Coordinator**: An existing pattern in the codebase (e.g. `YouTubeCoordinator`, `PersistenceCoordinator`) — a plain class that receives `MainWindow` (or a narrow interface) and owns one feature domain.
- **TimerRegistry**: The new centralised object that owns every `QTimer` lifecycle (create, start, stop, teardown).
- **StyleHelper**: The extracted module that owns all widget-styling utilities (`_set_panel_role`, `_apply_cta_button`, `_render_svg_icon`, etc.).
- **WidgetFactory**: The extracted module that owns all reusable widget-factory helpers (`_add_slider_row`, `_add_toggle_row`, `_add_form_row`, `_create_calendar_picker`, etc.).
- **ExportBatch**: The existing `@dataclass` in `main_window.py` that holds per-batch export state.
- **ExportBatchCoordinator**: The new coordinator that owns `ExportBatch` creation, mutation, and orchestration logic extracted from `MainWindow`.
- **DebugProbe**: Any `exec()`-based or inline `urllib.request` block used for debugging YouTube upload jobs in `_run_one_youtube_upload_job`.
- **FooterController**: The new class that owns footer status-bar state and refresh logic.
- **UiBus**: The existing `python_app/app/ui_bus.py` signal bus.
- **DI**: Dependency injection — passing collaborators through the constructor rather than accessing them as ad-hoc attributes.

---

## Requirements

---

### Requirement 1: Extract StyleHelper into a dedicated module

**User Story:** As a senior developer, I want all widget-styling utilities isolated in one place,
so that theme logic is testable without instantiating MainWindow.

#### Acceptance Criteria

1. THE StyleHelper SHALL be implemented as a standalone module at
   `python_app/app/style_helper.py`, containing all methods currently named
   `_set_panel_role`, `_set_label_role`, `_set_button_role`, `_set_field_role`,
   `_apply_cta_button`, `_apply_card_field`, `_refresh_widget_style`, `_set_widget_property`,
   and `_render_svg_icon` from `MainWindow`.
2. THE StyleHelper SHALL expose each utility as a module-level function that accepts the
   target widget and the required token dict as explicit parameters rather than reading them
   from `self`.
3. WHEN `MainWindow` calls any styling utility, THE MainWindow SHALL contain no definition
   of methods matching the names listed in criterion 1; a `grep -n "def _set_panel_role\|def
   _apply_cta_button\|def _render_svg_icon" main_window.py` SHALL return zero matches.
4. THE StyleHelper functions SHALL carry explicit type annotations on every parameter and
   every return value, using built-in generics (`dict[str, str]`) rather than
   `typing.Dict`, matching the Python 3.10+ style used throughout the codebase.
5. IF a `StyleHelper` function receives a `None` widget or a widget whose underlying C++
   object has been deleted (catching `RuntimeError`), THEN THE StyleHelper SHALL return
   immediately without raising an exception.

---

### Requirement 2: Extract WidgetFactory into a dedicated module

**User Story:** As a senior developer, I want all reusable widget-factory helpers in one place,
so that UI construction can be tested and reused without the God class.

#### Acceptance Criteria

1. THE WidgetFactory SHALL be implemented as a standalone module at
   `python_app/app/widget_factory.py`, containing all methods currently prefixed `_add_*`,
   `_create_*`, `_make_panel_section`, `_configure_step_slider`, and `_split_metric_text`,
   `_set_metric_text`, `_create_metric_header` from `MainWindow`.
2. THE WidgetFactory functions SHALL accept the UI token dict and any required callbacks as
   explicit parameters and SHALL NOT require a `MainWindow` instance to operate.
3. WHEN `MainWindow` constructs reusable widgets after the refactoring, THE MainWindow class
   SHALL contain no method definitions whose names match the prefixes `_add_*`, `_create_*`,
   `_make_panel_section`, `_configure_step_slider`, `_split_metric_text`, `_set_metric_text`,
   or `_create_metric_header`; a grep for those names inside the `MainWindow` class body
   SHALL return zero definition matches.
4. THE WidgetFactory functions SHALL carry explicit type annotations on every parameter and
   every return value, with `Any` disallowed as a substitute for a known type.
5. THE `_create_calendar_picker`, `_calendar_picker_value`, and `_set_calendar_picker_value`
   helpers SHALL be included in `WidgetFactory`; THE MainWindow class body SHALL contain no
   definition or inline re-implementation of date-picker construction or value-access logic
   after the refactoring.

---

### Requirement 3: Extract FooterController into a dedicated class

**User Story:** As a senior developer, I want footer status-bar state owned by one object,
so that status updates from any domain flow through a single, testable path.

#### Acceptance Criteria

1. THE FooterController SHALL be implemented as a class at
   `python_app/app/footer_controller.py` that owns the `_global_status_message`,
   `_music_status_message`, and `_music_suno_status_message` string fields.
2. THE FooterController constructor SHALL accept a single `label_accessor: Callable[[], QLabel | None]`
   parameter so that tests can inject a mock callable instead of a real `QLabel`.
3. THE FooterController SHALL expose typed methods `set_status(message: str, *, source: str = "")`,
   `set_music_status(message: str)`, `set_suno_status(message: str)`, and `refresh()` that
   update the footer label widget returned by `label_accessor`. The `refresh()` method SHALL
   apply the following priority and composition rule: if `_music_suno_status_message` is
   non-empty and `_global_status_message` equals `_music_status_message`, THEN the displayed
   text is `"{_music_status_message} · {_music_suno_status_message}"`; otherwise the displayed
   text is `_global_status_message` or `"Ready"` if all three fields are empty.
4. WHEN any domain (music, image, video, YouTube) sets a status message, THE domain SHALL
   call a `FooterController` method rather than setting `MainWindow` attributes directly.
5. THE FooterController SHALL carry complete type annotations on all public methods.
6. IF `label_accessor()` returns `None`, or if calling `setText` raises a `RuntimeError`
   (destroyed C++ object), THEN THE FooterController SHALL silently skip the update without
   re-raising the exception.

---

### Requirement 4: Extract ExportBatchCoordinator

**User Story:** As a senior developer, I want all export-batch state management and
orchestration logic owned by a single coordinator, so that `MainWindow` does not mix
view code with batch lifecycle logic.

#### Acceptance Criteria

1. THE ExportBatchCoordinator SHALL be implemented in the existing
   `python_app/features/video_export/` package and SHALL own the `ExportBatch` dataclass,
   the `_export_batches: dict[str, ExportBatch]` registry, and all methods that create,
   read, or mutate entries in that registry.
2. THE ExportBatch dataclass SHALL be moved to
   `python_app/features/video_export/export_batch.py` and SHALL be the single import point
   for all consumers.
3. WHEN a new export batch is started, THE ExportBatchCoordinator SHALL be the sole object
   that calls `ExportBatch(...)` and inserts the result into the registry; no other module
   SHALL construct an `ExportBatch` directly.
4. WHEN an export batch completes successfully, THE ExportBatchCoordinator SHALL update the
   corresponding `ExportBatch` state and emit `bus.export_event` with `{"type": "export_done",
   "ok": True, ...}`; WHEN an export batch fails, THE ExportBatchCoordinator SHALL emit
   `bus.export_event` with `{"type": "export_done", "ok": False, "error": "<message>", ...}`.
5. WHEN `ExportBatchCoordinator.start_batch(...)` is called with an empty `ffmpeg_path`,
   empty `output_dir`, empty `bg_path`, or empty `logo_path`, THE coordinator SHALL raise
   `ValueError` with a message identifying which parameter is missing before creating any
   `ExportBatch` instance.
6. THE ExportBatchCoordinator SHALL accept `ffmpeg_path: str`, `output_dir: str`,
   `bg_path: str`, `logo_path: str`, and `bus: UiBus` as constructor parameters.
7. THE ExportBatchCoordinator public API, including its constructor, SHALL carry complete
   type annotations on all parameters and return values.

---

### Requirement 5: Centralise timer lifecycle in TimerRegistry

**User Story:** As a senior developer, I want all `QTimer` instances owned and managed by
one registry, so that startup, page-visibility gating, settings-sync, and shutdown are
handled consistently without scattered `_ensure_*` / `_sync_*` helpers.

#### Acceptance Criteria

1. THE TimerRegistry SHALL be implemented as a class at
   `python_app/app/timer_registry.py` and SHALL own every `QTimer` currently created in
   `_ensure_image_timers`, `_ensure_auto_video_timer`, `_ensure_progress_timers`,
   `_ensure_dashboard_timers`, and the `_sync_image_auto_poll_timer`,
   `_sync_auto_video_timer`, `_sync_youtube_auto_poll_timer` methods of `MainWindow`.
2. THE TimerRegistry SHALL expose a `register(name: str, interval_ms: int, callback:
   Callable[[], None], *, page_gate: str | None = None) -> QTimer` method that creates,
   stores, and returns the timer. Calling `register` with a `name` that is already
   registered SHALL raise `ValueError`.
3. WHEN `MainWindow.closeEvent` is called, THE `TimerRegistry.stop_all()` method SHALL stop
   all registered timers, covering at minimum the nine timers named:
   `image_auto_poll`, `image_live_refresh`, `auto_video`, `progress_live_refresh`,
   `dashboard_live_refresh`, `youtube_auto_poll`, `music_suno_poll`, `music_render`, and
   `music_heartbeat`.
4. THE TimerRegistry SHALL expose a `sync(name: str, *, enabled: bool) -> None` method that
   starts the named timer if `enabled` is `True` and it is not already running, or stops it
   if `enabled` is `False` and it is currently running; it SHALL be a no-op if the timer is
   already in the requested state.
5. WHEN a timer was registered with a non-`None` `page_gate`, THE TimerRegistry SHALL wrap
   the original callback so that the callback is invoked only when the current active page
   (supplied via a `set_active_page(page: str) -> None` method on `TimerRegistry`) matches
   `page_gate`; the timer SHALL still fire on its interval but produce no observable side
   effect when the page does not match.
6. THE TimerRegistry SHALL carry complete type annotations on all public methods.

---

### Requirement 6: Remove all inline debug probes from production code

**User Story:** As a senior developer, I want the YouTube upload path free of `exec()` and
inline `urllib.request` debug probes, so that production code does not execute arbitrary
strings or make undocumented network calls.

#### Acceptance Criteria

1. THE `_run_one_youtube_upload_job` method and every other production method in `MainWindow`
   SHALL contain no call to Python's built-in `exec()` function (distinct from Qt's
   `.exec()` dialog method) after the refactoring; a `grep -n "\bexec(" main_window.py`
   SHALL return zero matches outside of string literals and comments.
2. THE MainWindow module SHALL contain no `import json` or `import urllib.request` statements
   inside method bodies after the refactoring; all imports SHALL be at module level.
3. WHERE the application is running with `MG_DEBUG_PROBES=1`, THE `DebugProbeEmitter` SHALL
   emit a `logging.DEBUG`-level record via `logging.getLogger("mg.debug_probe")` containing
   the fields `session_id`, `hypothesis_id`, `location`, `msg`, and `data` as a structured
   dict in the `extra` parameter.
4. THE debug-point regions A, B, C, and D in `_run_one_youtube_upload_job` SHALL each be
   replaced by a single call of the form
   `_probe.emit(hypothesis="A", location="...", msg="...", data={...})`, where `_probe` is a
   `DebugProbeEmitter` instance constructed at module import time reading from
   `.dbg/youtube-upload-issues.env`.
5. THE DebugProbeEmitter SHALL be implemented in
   `python_app/features/youtube/debug_probe.py`; every public method and the constructor
   SHALL carry type annotations on all parameters and return values, with no use of `Any`
   as a substitute for a known type.
6. IF `MG_DEBUG_PROBES` is absent from the environment or set to any value other than the
   string `"1"`, THEN `DebugProbeEmitter.emit(...)` SHALL return immediately without opening
   any file, creating any network connection, or writing to stdout or stderr.

---

### Requirement 7: Eliminate duplicate and inline imports

**User Story:** As a senior developer, I want all imports at module level in the standard
location, so that dependency relationships are explicit and static-analysis tools work
correctly.

#### Acceptance Criteria

1. THE MainWindow module SHALL have all `import` and `from … import` statements at the top
   of the file in PEP 8 order (standard library, then third-party, then local application),
   with no import statement appearing inside any function or method body after the
   refactoring.
2. WHEN any currently inline import is moved to module level, `python -m py_compile
   python_app/app/main_window.py` SHALL exit with code 0 when executed in the project's
   standard virtualenv.
3. THE MainWindow module SHALL contain no two import lines that import the same symbol or
   module (including but not limited to `import time`, `import json`, and
   `import urllib.request`); a scan of the file's top-level import block for any repeated
   module or symbol name SHALL return zero matches.
4. WHEN `flake8 --select=F401,E401` is run on `main_window.py`, `style_helper.py`,
   `widget_factory.py`, `footer_controller.py`, `timer_registry.py`,
   `features/video_export/export_batch.py`, and
   `features/youtube/debug_probe.py`, the tool SHALL report zero violations on each of
   those files.

---

### Requirement 8: Fix the `removed` variable bug in `_delete_music_saved_text`

**User Story:** As a developer, I want `_delete_music_saved_text` to refer to a defined
variable when composing its status message, so that the method does not raise a `NameError`
at runtime.

#### Acceptance Criteria

1. WHEN `_delete_music_saved_text` is called and `music_controller.delete_saved_text`
   returns without raising an exception, THE MainWindow SHALL call
   `self._set_music_status(f"Deleted {deleted_row.get('name', 'item')}")` where
   `deleted_row` is the dict captured from `rows[idx]` before the deletion call;
   `removed` SHALL NOT appear anywhere in the method body.
2. THE fix SHALL preserve the calls to `music_controller.delete_saved_text`,
   `self._refresh_music_saved_text_list(kind)`,
   `self._refresh_music_match_structure_options()`, and
   `self._refresh_music_ui()` in the same relative order as in the original implementation.
3. WHEN `_delete_music_saved_text` is called with `0 ≤ idx < len(rows)` and the deletion
   succeeds, THE method SHALL complete without raising `NameError`, `UnboundLocalError`, or
   `KeyError`.
4. THE corrected method SHALL carry a `kind: str` type annotation on its parameter and a
   `-> None` return annotation.

---

### Requirement 9: Apply dependency injection to all coordinators constructed in `__init__`

**User Story:** As a senior developer, I want coordinators to receive their dependencies
through their constructors rather than reaching into `MainWindow` attributes, so that each
coordinator can be instantiated and tested independently.

#### Acceptance Criteria

1. THE MainWindow `__init__` SHALL pass `db_cfg`, `bus`, `music_data`, and `e_settings` as
   explicit constructor arguments to each of the following coordinators:
   `MusicController`, `ImageController`, `YouTubeCoordinator`, `ExportBatchCoordinator`,
   and `PersistenceCoordinator`.
2. WHEN `db_cfg` changes after initialisation (e.g. after a database reconnection), THE
   MainWindow SHALL call `update_db_cfg(cfg: DbCfg | None)` on each of the following
   coordinators: `MusicController`, `ImageController`, `YouTubeCoordinator`,
   `ExportBatchCoordinator`, and `PersistenceCoordinator`.
3. THE `MusicController`, `ImageController`, `YouTubeCoordinator`,
   `ExportBatchCoordinator`, and `PersistenceCoordinator` constructors SHALL each list
   `db_cfg: DbCfg | None`, `bus: UiBus`, and any other required collaborators as
   individually named, typed parameters; no coordinator constructor SHALL accept a bare
   `**kwargs` in place of these named parameters.
4. THE coordinators SHALL NOT access `MainWindow` instance attributes directly; any value a
   coordinator needs from `MainWindow` (other than via `UiBus` signals or explicitly
   injected constructor arguments) SHALL be passed as an argument to the specific method
   that requires it.
5. WHEN any of the five named coordinators is constructed in a unit test by passing a
   `db_cfg=None`, a stub `bus`, and valid stubs for other required parameters, THE
   constructor SHALL complete without raising `AttributeError`, `ImportError`, or
   `TypeError`.

---

### Requirement 10: Add type annotations to all public and protected methods in `MainWindow`

**User Story:** As a senior developer, I want every method signature to carry type
annotations, so that mypy and IDE tooling can catch mismatches before runtime.

#### Acceptance Criteria

1. THE MainWindow class SHALL have an explicit type annotation on every parameter (excluding
   `self`) and an explicit return-type annotation on every method that currently lacks one
   after the refactoring; `Any` SHALL NOT be used as a substitute for a known type on any
   newly annotated signature.
2. THE modules `style_helper.py`, `widget_factory.py`, `footer_controller.py`,
   `timer_registry.py`, `features/video_export/export_batch.py`, and
   `features/youtube/debug_probe.py` SHALL each have complete type annotations on all
   public and module-level functions and class constructors; `Any` SHALL NOT be used as a
   substitute for a known type.
3. WHEN `mypy --strict python_app/app/main_window.py` is run on the refactored file, THE
   tool SHALL report zero type errors on lines that were modified by this refactoring;
   pre-existing errors on unmodified lines are out of scope.
4. THE type annotations SHALL use built-in generics (`list[str]`, `dict[str, int]`,
   `tuple[str, str]`) rather than `typing.List`, `typing.Dict`, or `typing.Tuple`, matching
   the Python 3.10+ style already present in the file.

---

### Requirement 11: Preserve all existing runtime behaviour

**User Story:** As a QA engineer, I want the refactored application to behave identically to
the original at runtime, so that no user-facing functionality is broken by the refactoring.

#### Acceptance Criteria

1. WHEN the application starts after refactoring, THE MainWindow `__init__` SHALL complete
   all three observable phases in order: (a) all coordinators constructed and assigned,
   (b) all timers registered with `TimerRegistry`, (c) all UI pages built and the initial
   page displayed; a startup log written to the application's own logger SHALL confirm each
   phase before the window becomes visible.
2. WHEN a user triggers any of the following actions — music generation, image generation,
   video export, YouTube upload, template save, settings change — THE application SHALL
   produce the same observable outcomes (status-bar text, database record written, file
   written to `output_dir`, UiBus signal emitted) as before the refactoring.
3. WHEN `MainWindow.closeEvent` fires, THE `TimerRegistry.stop_all()` call SHALL stop
   all nine named timers: `image_auto_poll`, `image_live_refresh`, `auto_video`,
   `progress_live_refresh`, `dashboard_live_refresh`, `youtube_auto_poll`,
   `music_suno_poll`, `music_render`, and `music_heartbeat`.
4. THE `ExportBatch` dataclass fields `batch_key`, `output_dir`, `ffmpeg_path`, `bg_path`,
   `logo_path`, `queue`, `jobs`, `job_state`, `mp3s`, `total_count`, `completed_count`,
   `failed_count`, `outputs_by_mp3`, `running`, and `auto_merge_after` SHALL retain
   identical field names, types, and `field(default_factory=...)` defaults after the move
   to `export_batch.py`.
5. IF any existing coordinator or view mixin imports `ExportBatch` from `main_window`,
   THEN that import SHALL be updated to `from ..features.video_export.export_batch import
   ExportBatch`; `main_window.py` SHALL re-export `ExportBatch` with the comment
   `# deprecated: import from features.video_export.export_batch` until the last consumer
   is updated, at which point the re-export SHALL be removed.
6. WHEN `MainWindow.closeEvent` fires, THE `youtube_coordinator.cancel_runtime_jobs(
   stop_timer=True, clear_running=True)` call SHALL execute before `TimerRegistry.stop_all()`
   to preserve the existing cancellation-token increment behaviour observed in the original
   `_cancel_unfinished_background_jobs` implementation.

---

### Requirement 12: Ensure each extracted module is independently importable and unit-testable

**User Story:** As a senior developer, I want each new module to be importable in isolation,
so that unit tests can be written without standing up the full PyQt6 application.

#### Acceptance Criteria

1. THE `StyleHelper` module SHALL be importable with
   `from python_app.app.style_helper import set_panel_role` in a test environment where
   PyQt6 is installed but no `QApplication` instance has been created; the import SHALL
   complete without instantiating any Qt widget.
2. THE `WidgetFactory` module SHALL be importable and its functions that contain no Qt
   widget constructors, no database calls, and no network calls (e.g. `split_metric_text`,
   `format_music_updated_at`) SHALL be callable without a `QApplication` instance.
3. THE `FooterController` constructor SHALL accept a `label_accessor: Callable[[], QLabel | None]`
   parameter; in tests, passing a callable that returns a `MagicMock()` SHALL allow
   `set_status`, `set_music_status`, `set_suno_status`, and `refresh` to be called and
   their effect on the mock to be asserted without a real `QLabel`.
4. THE `TimerRegistry` SHALL be constructable by passing a `QObject` instance (or `None`)
   as its parent parameter; it SHALL NOT require any attribute specific to `MainWindow` to
   be present on the parent.
5. THE `DebugProbeEmitter` SHALL be constructable and `emit(...)` SHALL be callable with
   `MG_DEBUG_PROBES` absent from the environment; in that state calling `emit(...)` SHALL
   produce: (a) no file system writes, (b) no network connections, (c) no writes to
   stdout or stderr — each verifiable independently in a `pytest` test without mocking the
   network stack.
6. FOR every function in the extracted modules that contains no Qt widget constructors, no
   database calls, and no network calls, THERE SHALL be at least one `pytest` test in
   `python_app/tests/` that (a) calls the function with valid input and asserts on the
   return value or mutated state, and (b) calls the function with an invalid or boundary
   input and asserts that either the expected exception type is raised or the expected
   sentinel value is returned.
