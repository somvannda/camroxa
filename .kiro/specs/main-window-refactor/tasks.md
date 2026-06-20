# Implementation Plan: `main_window.py` God-Class Refactor

## Overview

Incrementally decompose the 7 000+ line `MainWindow` God class into focused, single-purpose
modules while preserving all existing runtime behaviour and without introducing new
third-party dependencies. Each slice is independently mergeable. Property-based tests use
`hypothesis`; all other tests use `pytest`.

---

## Tasks

- [x] 1. Extract `StyleHelper` module
  - [x] 1.1 Create `python_app/app/style_helper.py` with all module-level styling functions
    - Implement `refresh_widget_style`, `set_widget_property`, `set_panel_role`,
      `set_label_role`, `set_button_role`, `set_field_role`, `apply_cta_button`,
      `apply_card_field`, and `render_svg_icon` as module-level functions
    - Each function accepts target widget and token `dict[str, str]` as explicit parameters
    - Every function must guard against `None` widget and catch `RuntimeError` for
      destroyed C++ objects, returning immediately without raising
    - Add complete type annotations on every parameter and return value using Python 3.10+
      built-in generics; no `Any`, no `typing.Dict`/`typing.List`
    - _Requirements: 1.1, 1.2, 1.4, 1.5_

  - [x] 1.2 Replace `MainWindow` styling method definitions with delegation calls
    - Replace every `def _set_panel_role(...)`, `def _apply_cta_button(...)`,
      `def _render_svg_icon(...)`, etc. inside the class body with calls to the
      module-level `style_helper` functions, forwarding `self.ui` as the token dict
    - After replacement, `grep -n "def _set_panel_role\|def _apply_cta_button\|def _render_svg_icon" main_window.py` must return zero matches
    - _Requirements: 1.1, 1.3_

  - [ ]* 1.3 Write unit tests for `StyleHelper` in `python_app/tests/test_style_helper.py`
    - Test each function with a `MagicMock` widget; verify delegation and no exception raised
    - Test `None` widget guard — function must return `None` without raising
    - Test `RuntimeError` guard — mock raises `RuntimeError` on Qt call; function must not
      propagate the error
    - _Requirements: 1.5, 12.6_

- [x] 2. Extract `WidgetFactory` module
  - [x] 2.1 Create `python_app/app/widget_factory.py` with all widget-factory functions
    - Implement `split_metric_text`, `format_music_updated_at`, `create_metric_header`,
      `add_slider_row`, `configure_step_slider`, `add_toggle_row`, `add_form_row`,
      `make_panel_section`, `set_metric_text`, `create_calendar_picker`,
      `calendar_picker_value`, and `set_calendar_picker_value` as module-level functions
    - Functions accepting Qt widgets or callbacks receive the UI token dict and callbacks
      as explicit parameters; no `MainWindow` import required
    - Pure-computation helpers (`split_metric_text`, `format_music_updated_at`) must be
      callable without a `QApplication` instance
    - Add complete type annotations; `Any` is disallowed as a substitute for a known type
    - _Requirements: 2.1, 2.2, 2.4, 2.5_

  - [x] 2.2 Replace `MainWindow` widget-factory method definitions with delegation calls
    - Replace all `_add_*`, `_create_*`, `_make_panel_section`, `_configure_step_slider`,
      `_split_metric_text`, `_set_metric_text`, and `_create_metric_header` method
      definitions inside the class body with calls to `widget_factory` module functions
    - After replacement, a grep for those method definition names inside the `MainWindow`
      class body must return zero matches
    - Update all view mixins that call these helpers to call the factory functions directly
    - _Requirements: 2.3, 2.5_

  - [ ]* 2.3 Write unit tests for `WidgetFactory` in `python_app/tests/test_widget_factory.py`
    - Test `split_metric_text` and `format_music_updated_at` without a `QApplication` instance
    - Test `create_calendar_picker` and `add_slider_row` with `qtbot` fixture
    - Test boundary inputs (empty string, large values) for pure-computation helpers
    - _Requirements: 2.2, 12.2, 12.6_

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass; run `python -m py_compile python_app/app/main_window.py` and
    confirm exit code 0. Ask the user if questions arise.

- [x] 4. Extract `FooterController` class
  - [x] 4.1 Create `python_app/app/footer_controller.py` with the `FooterController` class
    - Implement constructor accepting `label_accessor: Callable[[], QLabel | None]`
    - Own `_global_status_message`, `_music_status_message`, `_music_suno_status_message`
      as instance string fields initialised to `""`
    - Implement `set_status(message: str, *, source: str = "") -> None`,
      `set_music_status(message: str) -> None`, `set_suno_status(message: str) -> None`,
      `refresh() -> None`
    - `refresh()` applies the documented composition rule:
      if `_music_suno_status_message` is non-empty AND `_global_status_message == _music_status_message`,
      display `"{_music_status_message} · {_music_suno_status_message}"`;
      otherwise display `_global_status_message` or `_music_status_message` if global is empty,
      or `"Ready"` if all three are empty
    - `refresh()` guards against `None` from `label_accessor()` and catches `RuntimeError`
      on `setText` (destroyed C++ object), silently skipping the update
    - Add complete type annotations on all public methods
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

  - [x] 4.2 Wire `FooterController` into `MainWindow`
    - In `MainWindow.__init__`, construct
      `self._footer = FooterController(lambda: getattr(self, "footer_left_label", None))`
    - Replace all direct writes to `self._global_status_message`, `self._music_status_message`,
      and `self._music_suno_status_message` throughout `MainWindow` and all domain methods
      with calls to `self._footer.set_status(...)`, `self._footer.set_music_status(...)`,
      and `self._footer.set_suno_status(...)` respectively
    - _Requirements: 3.4_

  - [ ]* 4.3 Write property test `test_footer_composition_rule` in `python_app/tests/test_footer_controller.py`
    - **Property 1: FooterController composition rule is always respected**
    - For any combination of `_global_status_message`, `_music_status_message`, and
      `_music_suno_status_message` strings, verify the displayed text satisfies the
      documented composition rule after calling setters and `refresh()`
    - Use `@given(st.text(), st.text(), st.text())` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 1`
    - **Validates: Requirements 3.3**

  - [ ]* 4.4 Write unit tests for `FooterController` in `python_app/tests/test_footer_controller.py`
    - Test construction; test concrete composition scenarios
    - Test `None` label guard — `refresh()` must not raise
    - Test `RuntimeError` guard on `setText` — must not propagate
    - _Requirements: 3.6, 12.3, 12.6_

- [x] 5. Move `ExportBatch` dataclass and create `ExportBatchCoordinator`
  - [x] 5.1 Create `python_app/features/video_export/export_batch.py` with the `ExportBatch` dataclass
    - Move `ExportBatch` verbatim with identical field names, types, and
      `field(default_factory=...)` defaults: `batch_key`, `output_dir`, `ffmpeg_path`,
      `bg_path`, `logo_path`, `queue`, `jobs`, `job_state`, `mp3s`, `total_count`,
      `completed_count`, `failed_count`, `outputs_by_mp3`, `running`, `auto_merge_after`
    - Add `from __future__ import annotations` and correct imports
    - _Requirements: 4.2, 11.4_

  - [x] 5.2 Add deprecation re-export shim in `main_window.py` for `ExportBatch`
    - Add `from .features.video_export.export_batch import ExportBatch  # noqa: F401`
      with the comment `# deprecated: import from features.video_export.export_batch`
    - Update all existing consumers of `ExportBatch` (coordinators, mixins) to import
      from the new location `from ..features.video_export.export_batch import ExportBatch`
    - _Requirements: 4.2, 11.5_

  - [x] 5.3 Implement `ExportBatchCoordinator` in `python_app/features/video_export/coordinator.py`
    - Add `ExportBatchCoordinator` class with constructor accepting `ffmpeg_path: str`,
      `output_dir: str`, `bg_path: str`, `logo_path: str`, `bus: UiBus`
    - Implement `start_batch(mp3s: list[str], *, auto_merge_after: bool = False) -> str`:
      raises `ValueError` (naming the offending parameter) if any required path is empty or
      whitespace before creating any `ExportBatch`; on success inserts batch into
      `_export_batches: dict[str, ExportBatch]` and returns `batch_key`
    - Implement `complete_batch(batch_key: str, *, ok: bool, error: str = "") -> None`:
      emits `bus.export_event` with `{"type": "export_done", "ok": True/False, "batchKey": ..., ...}`
    - Implement `get_batch(batch_key: str) -> ExportBatch | None`
    - Implement `update_db_cfg(cfg: DbCfg | None) -> None`
    - Add complete type annotations on all public methods and constructor
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 5.4 Write property test `test_export_batch_coordinator_event_shape` in `python_app/tests/test_export_batch_coordinator.py`
    - **Property 2: ExportBatchCoordinator emits correct payload shape on completion and failure**
    - For any `batch_key` and completion outcome, verify `bus.export_event.emit` is called
      exactly once with a dict containing `"type": "export_done"`, `"ok": bool(ok)`,
      and — when `ok=False` — an `"error"` key matching the supplied error string
    - Use `@given(st.text(), st.booleans(), st.text())` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 2`
    - **Validates: Requirements 4.4**

  - [ ]* 5.5 Write property test `test_start_batch_empty_param_raises` in `python_app/tests/test_export_batch_coordinator.py`
    - **Property 3: `start_batch` raises ValueError for any empty required parameter**
    - For any combination of `(ffmpeg_path, output_dir, bg_path, logo_path)` where at
      least one is empty or whitespace-only, verify `ValueError` is raised before any
      `ExportBatch` is created (internal registry remains empty)
    - Use `@given(...)` generating four-tuples with at least one empty/whitespace element
    - Tag: `Feature: main-window-refactor, Property 3`
    - **Validates: Requirements 4.5**

  - [ ]* 5.6 Write unit tests for `ExportBatch` and `ExportBatchCoordinator` in `python_app/tests/test_export_batch.py` and `test_export_batch_coordinator.py`
    - Test `ExportBatch` construction and field defaults from new location
    - Test `start_batch` with all valid paths — verify batch inserted and key returned
    - Test import-only smoke test confirming new module path works
    - _Requirements: 4.1, 4.2, 4.7, 12.6_

- [x] 6. Checkpoint — Ensure all tests pass
  - Run the full test suite; confirm `py_compile` succeeds on all modified files. Ask the
    user if questions arise.

- [x] 7. Centralise timer lifecycle in `TimerRegistry`
  - [x] 7.1 Create `python_app/app/timer_registry.py` with the `TimerRegistry` class
    - Implement constructor `__init__(self, parent: QObject | None = None) -> None`
      initialising `_timers: dict[str, QTimer] = {}` and `_active_page: str = ""`
    - Implement `register(name: str, interval_ms: int, callback: Callable[[], None], *, page_gate: str | None = None) -> QTimer`:
      creates `QTimer(parent)`, connects callback (wrapped with page-gate guard when
      `page_gate` is not `None`), stores in `_timers`, raises `ValueError` if name already
      registered
    - Page-gate guard: wrapper checks `self._active_page == page_gate` before invoking
      the original callback; timer still fires on its interval
    - Implement `stop_all() -> None`: calls `timer.stop()` on every active timer;
      each stop is wrapped in `try/except Exception`
    - Implement `sync(name: str, *, enabled: bool) -> None`: idempotent start/stop; no-op
      if timer already in requested state; logs DEBUG warning if name not registered
    - Implement `set_active_page(page: str) -> None`
    - Add complete type annotations on all public methods
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.6, 12.4_

  - [x] 7.2 Register all nine timers in `MainWindow.__init__` via `TimerRegistry`
    - After UI build, construct `self._timer_registry = TimerRegistry(parent=self)` and
      register all nine timers with their names, intervals, callbacks, and page gates
      as specified in the design table
    - Remove `_ensure_image_timers`, `_ensure_auto_video_timer`,
      `_ensure_progress_timers`, `_ensure_dashboard_timers` method definitions
    - Replace `_sync_image_auto_poll_timer`, `_sync_auto_video_timer`,
      `_sync_youtube_auto_poll_timer` calls with `self._timer_registry.sync(name, enabled=bool_expr)`
    - _Requirements: 5.1, 5.3_

  - [x] 7.3 Update `MainWindow.closeEvent` to use `TimerRegistry.stop_all()`
    - Call `self.youtube_coordinator.cancel_runtime_jobs(stop_timer=True, clear_running=True)`
      first, then `self._timer_registry.stop_all()`, then `super().closeEvent(ev)`
    - Preserve the existing cancellation-token increment behaviour
    - _Requirements: 5.3, 11.3, 11.6_

  - [ ]* 7.4 Write property test `test_timer_registry_duplicate_raises` in `python_app/tests/test_timer_registry.py`
    - **Property 4: TimerRegistry raises ValueError for duplicate timer names**
    - For any timer name registered once, a second `register(name, ...)` call must always
      raise `ValueError` regardless of interval, callback, or page_gate
    - Use `@given(st.text(min_size=1), st.integers(min_value=100))` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 4`
    - **Validates: Requirements 5.2**

  - [ ]* 7.5 Write property test `test_timer_registry_sync_idempotent` in `python_app/tests/test_timer_registry.py`
    - **Property 5: `TimerRegistry.sync` is idempotent**
    - For any registered timer name and `enabled` value, calling `sync(name, enabled=enabled)`
      twice must leave the timer in the same state (`isActive() == enabled`) as calling it once
    - Use `@given(st.booleans())` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 5`
    - **Validates: Requirements 5.4**

  - [ ]* 7.6 Write property test `test_timer_registry_page_gate` in `python_app/tests/test_timer_registry.py`
    - **Property 6: Page-gate suppresses callback when page does not match**
    - For any `page_gate` string and `active_page` string, manually firing the timer's
      timeout must invoke the callback if and only if `active_page == page_gate`
    - Use `@given(st.text(), st.text())` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 6`
    - **Validates: Requirements 5.5**

  - [ ]* 7.7 Write unit tests for `TimerRegistry` in `python_app/tests/test_timer_registry.py`
    - Test `register` success; verify returned `QTimer` has correct interval
    - Test `stop_all` stops all active timers
    - Test all nine named timers registered without error
    - Test `sync` with unregistered name — must not raise, must log DEBUG
    - _Requirements: 5.1, 5.3, 5.6, 12.4, 12.6_

- [x] 8. Remove inline debug probes and introduce `DebugProbeEmitter`
  - [x] 8.1 Create `python_app/features/youtube/debug_probe.py` with `DebugProbeEmitter`
    - Implement constructor `__init__(self, env_file: str) -> None` storing `_env_file`
      and `_logger = logging.getLogger("mg.debug_probe")`
    - Implement `emit(*, hypothesis: str, location: str, msg: str, data: dict[str, object]) -> None`:
      returns immediately when `os.environ.get("MG_DEBUG_PROBES") != "1"` (no file, network,
      or stdout/stderr access)
    - When `MG_DEBUG_PROBES == "1"`: read `session_id` and `hypothesis_id` from `_env_file`
      (silently ignores missing file and parse errors); call `self._logger.debug(msg, extra={...})`
      with all five structured fields; wrap logging call in `try/except`
    - Add a module-level singleton
      `_probe = DebugProbeEmitter(".dbg/youtube-upload-issues.env")`
    - Add complete type annotations; no `Any`
    - _Requirements: 6.3, 6.4, 6.5, 6.6, 12.5_

  - [x] 8.2 Replace `exec()`/`urllib.request` debug blocks in `_run_one_youtube_upload_job`
    - Replace the four `exec()`/`urllib.request` debug regions (A, B, C, D) with
      `_probe.emit(hypothesis="A/B/C/D", location="...", msg="...", data={...})` calls
    - After replacement, `grep -n "\bexec(" main_window.py` must return zero matches
      outside string literals and comments
    - _Requirements: 6.1, 6.4_

  - [ ]* 8.3 Write property test `test_debug_probe_no_side_effects` in `python_app/tests/test_debug_probe.py`
    - **Property 7: `DebugProbeEmitter.emit` produces no side effects when probe flag is absent or not "1"**
    - For any `hypothesis`, `location`, `msg`, `data` arguments, verify that when
      `MG_DEBUG_PROBES` is absent or not `"1"`: (a) no file system writes, (b) no network
      connections, (c) no writes to stdout or stderr
    - Use `@given(st.text(), st.text(), st.text(), st.dictionaries(st.text(), st.text()))` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 7`
    - **Validates: Requirements 6.6, 12.5**

  - [ ]* 8.4 Write property test `test_debug_probe_structured_log_fields` in `python_app/tests/test_debug_probe.py`
    - **Property 8: `DebugProbeEmitter.emit` always records all five structured fields when probes are enabled**
    - For any `hypothesis`, `location`, `msg`, `data` dict, when `MG_DEBUG_PROBES=1`,
      verify the `LogRecord` received by the `"mg.debug_probe"` logger contains all five
      fields: `session_id`, `hypothesis_id`, `location`, `msg`, and `data`, with `location`
      and `msg` matching the values passed to `emit`
    - Use `@given(st.text(), st.text(), st.text(), st.dictionaries(st.text(), st.text()))` with `settings(max_examples=100)`
    - Tag: `Feature: main-window-refactor, Property 8`
    - **Validates: Requirements 6.3**

  - [ ]* 8.5 Write unit tests for `DebugProbeEmitter` in `python_app/tests/test_debug_probe.py`
    - Test `emit` with `MG_DEBUG_PROBES` absent — no stdout/stderr pollution
    - Test `emit` with a missing `.env` file — no exception raised
    - Test `emit` with a malformed `.env` file — no exception raised
    - _Requirements: 6.6, 12.5, 12.6_

- [x] 9. Checkpoint — Ensure all tests pass
  - Run the full test suite; run `grep -n "\bexec(" python_app/app/main_window.py` and
    confirm zero matches. Ask the user if questions arise.

- [x] 10. Consolidate all imports to module level
  - [x] 10.1 Move all inline and duplicate imports to the module-level import block in `main_window.py`
    - Move all `import` / `from … import` statements inside method bodies (including
      `import json`, `import urllib.request` inside `_run_one_youtube_upload_job`) to the
      top of the file
    - Remove duplicate import lines (e.g. multiple `import time`, `import json`)
    - Arrange remaining imports in PEP 8 order: standard library → third-party → local
    - _Requirements: 7.1, 7.3_

  - [ ] 10.2 Verify compile and linting gates on all affected files
    - Run `python -m py_compile python_app/app/main_window.py` — must exit code 0
    - Run `flake8 --select=F401,E401` on `main_window.py`, `style_helper.py`,
      `widget_factory.py`, `footer_controller.py`, `timer_registry.py`,
      `features/video_export/export_batch.py`, `features/youtube/debug_probe.py` —
      must report zero violations on each file
    - _Requirements: 7.2, 7.4_

- [x] 11. Fix the `removed` variable bug in `_delete_music_saved_text`
  - [x] 11.1 Rewrite `_delete_music_saved_text` to capture `deleted_row` before deletion
    - Capture `deleted_row = dict(rows[idx])` before calling
      `self.music_controller.delete_saved_text(kind, removed_id)`
    - Replace the status call with
      `self._set_music_status(f"Deleted {deleted_row.get('name', 'item')}")`
    - Ensure `removed` does not appear anywhere in the method body after the fix
    - Preserve the call order:
      `delete_saved_text` → `_refresh_music_saved_text_list` →
      `_refresh_music_match_structure_options` → `_refresh_music_ui`
    - Add `kind: str` parameter annotation and `-> None` return annotation
    - _Requirements: 8.1, 8.2, 8.4_

  - [ ]* 11.2 Write property test `test_delete_music_saved_text_no_name_error` in `python_app/tests/test_delete_music_saved_text.py`
    - **Property 9: `_delete_music_saved_text` never raises NameError, UnboundLocalError, or KeyError after the fix**
    - For any `rows` list of dicts (including dicts with and without a `"name"` key)
      and valid index `0 ≤ idx < len(rows)`, verify the method completes without raising
      `NameError`, `UnboundLocalError`, or `KeyError` when `delete_saved_text` returns
      successfully
    - Use `@given(st.lists(st.dictionaries(st.text(), st.text()), min_size=1))`
      to generate varied row lists; derive valid indices from list length
    - Tag: `Feature: main-window-refactor, Property 9`
    - **Validates: Requirements 8.3**

  - [ ]* 11.3 Write unit tests for the bug fix in `python_app/tests/test_delete_music_saved_text.py`
    - Test correct status message contains the item's `"name"` field value
    - Test fallback to `"item"` when `"name"` key is absent from `deleted_row`
    - Test that `removed` never appears in the executed code path (inspect source)
    - Verify call order via `MagicMock` call tracking
    - _Requirements: 8.1, 8.2, 8.3, 12.6_

- [x] 12. Apply dependency injection to all coordinators
  - [x] 12.1 Update `MusicController`, `ImageController`, `YouTubeCoordinator`, and `PersistenceCoordinator` constructors
    - Add individually named, typed constructor parameters: `db_cfg: DbCfg | None`,
      `bus: UiBus`, and any other required collaborators (no bare `**kwargs`)
    - Remove the `host: "MainWindow"` field from each coordinator
    - Add `update_db_cfg(cfg: DbCfg | None) -> None` method to each coordinator
    - Coordinators must not access `MainWindow` instance attributes directly; values
      must be passed via constructor args or method arguments
    - _Requirements: 9.3, 9.4_

  - [x] 12.2 Update `MainWindow.__init__` to pass explicit constructor arguments to all coordinators
    - Pass `db_cfg=self.db_cfg`, `bus=self.bus`, `music_data=self.music_data`,
      `e_settings=self.e_settings`, and all other required collaborators explicitly to
      `MusicController`, `ImageController`, `YouTubeCoordinator`,
      `ExportBatchCoordinator`, and `PersistenceCoordinator`
    - _Requirements: 9.1_

  - [x] 12.3 Call `update_db_cfg` on all coordinators after database reconnection
    - Locate the database reconnection handler in `MainWindow` and add
      `coordinator.update_db_cfg(cfg)` calls for all five coordinators after a successful
      reconnect
    - _Requirements: 9.2_

  - [ ]* 12.4 Write unit tests for DI constructors in `python_app/tests/test_di_constructors.py`
    - For each of the five coordinators, construct with `db_cfg=None`, a stub `bus`,
      and valid stubs for other required parameters; verify no `AttributeError`,
      `ImportError`, or `TypeError` is raised
    - _Requirements: 9.5, 12.6_

- [x] 13. Add type annotations to all public and protected `MainWindow` methods
  - [x] 13.1 Annotate every currently unannotated method parameter and return type in `MainWindow`
    - Add explicit type annotations on every parameter (excluding `self`) and every
      return-type annotation that is currently missing
    - Use built-in generics (`list[str]`, `dict[str, int]`, `tuple[str, str]`) — no
      `typing.List`, `typing.Dict`, `typing.Tuple`
    - `Any` must not be used as a substitute for a known type on any newly annotated
      signature
    - _Requirements: 10.1, 10.4_

  - [x] 13.2 Verify `mypy --strict` on all new and modified modules
    - Run `mypy --strict` on `style_helper.py`, `widget_factory.py`,
      `footer_controller.py`, `timer_registry.py`,
      `features/video_export/export_batch.py`, and `features/youtube/debug_probe.py`
    - Zero type errors on lines modified by this refactoring in `main_window.py`;
      pre-existing errors on unmodified lines are out of scope
    - _Requirements: 10.3_

- [ ] 14. Checkpoint — Ensure all tests pass and static analysis gates are green
  - Run the full test suite; run all static analysis gates:
    `py_compile`, `flake8 --select=F401,E401`, `mypy --strict` on all new modules.
    Ensure all tests pass. Ask the user if questions arise.

- [x] 15. Add startup phase logging and verify runtime behaviour preservation
  - [x] 15.1 Add startup phase log messages to `MainWindow.__init__`
    - After all coordinators are constructed and assigned, log phase (a) confirmation
    - After all timers are registered with `TimerRegistry`, log phase (b) confirmation
    - After all UI pages are built and the initial page is displayed, log phase (c) confirmation
    - Use the application's own logger; all three log lines must appear before the window
      becomes visible
    - _Requirements: 11.1_

  - [x] 15.2 Verify `closeEvent` sequence is correct
    - Confirm `MainWindow.closeEvent` calls `youtube_coordinator.cancel_runtime_jobs(stop_timer=True, clear_running=True)`
      before `self._timer_registry.stop_all()` before `super().closeEvent(ev)`
    - _Requirements: 11.3, 11.6_

- [x] 16. Final checkpoint — Ensure all tests pass
  - Run the full test suite one last time. Run all static analysis gates.
    Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP iteration
- Each task references specific requirements for full traceability
- Migration slices (1–10) are independently mergeable; the task order follows the design's
  recommended slice sequence
- Checkpoints ensure incremental validation at each major boundary
- Property tests (Properties 1–9) use `hypothesis` with `settings(max_examples=100)`;
  unit tests use `pytest` with `MagicMock` and `qtbot` where Qt is required
- Static analysis gates (`py_compile`, `flake8 --select=F401,E401`, `mypy --strict`)
  must pass on all seven named files before any slice is merged

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "4.1", "5.1", "7.1", "8.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "4.2", "5.2", "5.3", "7.2", "8.2", "11.1"] },
    { "id": 2, "tasks": ["1.3", "2.3", "4.3", "4.4", "5.4", "5.5", "5.6", "7.3", "8.3", "8.4", "8.5", "11.2", "11.3"] },
    { "id": 3, "tasks": ["7.4", "7.5", "7.6", "7.7", "10.1", "12.1"] },
    { "id": 4, "tasks": ["10.2", "12.2", "12.3"] },
    { "id": 5, "tasks": ["12.4", "13.1"] },
    { "id": 6, "tasks": ["13.2", "15.1"] },
    { "id": 7, "tasks": ["15.2"] }
  ]
}
```
