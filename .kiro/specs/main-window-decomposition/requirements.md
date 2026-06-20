# Requirements Document

## Introduction

`MainWindow` in `python_app/app/main_window.py` remains a ~4181-line God class despite prior
extraction of `StyleHelper`, `WidgetFactory`, `FooterController`, and `TimerRegistry`. The
class currently inherits from 14 view mixins and directly owns:

- Coordinator construction and wiring (~300 lines of lambda-accessor boilerplate)
- Signal routing / event dispatch (~200 lines of `_handle_*` and `_on_*` forwarding)
- Audio playback state and control (~100 lines)
- Video template application and spectrum parameter updates (~800 lines of `_update_*`)
- Export orchestration delegation (~150 lines)
- Settings persistence and restoration (~200 lines)
- YouTube OAuth app management (~150 lines)
- Dashboard and Progress page data refresh (~200 lines)
- Music generation UI state glue (~400 lines)
- Initialization ordering that is fragile (attributes accessed before assignment)

This spec decomposes `MainWindow` into a thin shell that delegates to well-defined,
single-responsibility page controllers and an initialization orchestrator, following the
Mediator pattern with explicit lifecycle phases. The result preserves all existing runtime
behaviour while enabling isolated unit testing of each extracted component.

---

## Glossary

- **MainWindow**: The top-level `QMainWindow` subclass in `python_app/app/main_window.py`.
- **PageController**: A class that owns all event handlers, data-refresh logic, and state for one application page (e.g., Video, Music, Image, Dashboard, Progress, Settings, Workflow, Log).
- **InitOrchestrator**: The class responsible for executing `MainWindow.__init__` phases in a deterministic order — creating coordinators, registering timers, building UI, and restoring state.
- **SignalRouter**: The class that owns all UiBus signal connections and dispatches events to the appropriate PageController or Coordinator.
- **AudioController**: The class that owns pygame audio state (play, pause, stop, seek) and exposes a clean interface to the Video page.
- **TemplateController**: The class that owns video template state, parameter updates (`_update_*` methods), and layer/overlay management.
- **Coordinator**: An existing pattern — a plain class that receives dependencies through its constructor and owns one feature domain.
- **UiBus**: The existing `pyqtSignal`-based event bus at `python_app/app/ui_bus.py`.
- **TimerRegistry**: The existing centralised timer lifecycle manager at `python_app/app/timer_registry.py`.
- **FooterController**: The existing footer status-bar controller at `python_app/views/helpers/footer_controller.py`.
- **ViewMixin**: An existing pattern — a class providing `_build_*_page()` methods mixed into `MainWindow`.
- **DbCfg**: The database configuration dataclass from `python_app/database/persistence`.
- **ExportBatch**: The per-batch export state dataclass at `python_app/features/video_export/export_batch.py`.

---

## Requirements

---

### Requirement 1: Extract InitOrchestrator with deterministic lifecycle phases

**User Story:** As a senior developer, I want MainWindow initialization decomposed into a dedicated orchestrator with named phases, so that attribute-order bugs are eliminated and each phase can be tested independently.

#### Acceptance Criteria

1. THE InitOrchestrator SHALL be implemented as a class at `python_app/app/init_orchestrator.py` that accepts a `MainWindow` instance and executes initialization in four sequential phases: Phase A (state defaults), Phase B (coordinator construction), Phase C (UI build), Phase D (timer registration and state restoration).
2. WHEN Phase A executes, THE InitOrchestrator SHALL assign all instance attributes that other phases depend on (`db_cfg`, `bus`, `music_data`, `e_settings`, `template`, `_footer`, `ui`, `_timer_registry`) to their default or initial values before any coordinator constructor runs.
3. WHEN Phase B executes, THE InitOrchestrator SHALL construct all coordinators in a defined order where each coordinator receives only attributes assigned in Phase A or earlier in Phase B; no coordinator constructor SHALL access an attribute that has not yet been assigned.
4. WHEN Phase C executes, THE InitOrchestrator SHALL invoke page-building methods from the view mixins and assemble the primary navigation stack; all widget references stored on `MainWindow` SHALL be assigned during this phase.
5. WHEN Phase D executes, THE InitOrchestrator SHALL register all timers with `TimerRegistry`, call `_apply_settings_to_ui()`, `_restore_runtime_state()`, and `_restore_music_runtime_state()`, and start the initial polling timers.
6. IF any phase raises an exception, THEN THE InitOrchestrator SHALL log the phase name and exception message via `log_line` and re-raise the exception without suppressing the traceback.
7. THE InitOrchestrator SHALL emit a `log_line` entry at the start and end of each phase (e.g., `[STARTUP] Phase A: Begin`, `[STARTUP] Phase A: Complete`) to aid diagnosis of initialization failures.

---

### Requirement 2: Extract VideoPageController for template and spectrum parameter management

**User Story:** As a senior developer, I want the ~800 lines of `_update_*` methods for video template parameters owned by a single VideoPageController, so that the video editing domain is testable without the full MainWindow.

#### Acceptance Criteria

1. THE VideoPageController SHALL be implemented at `python_app/features/video_export/video_page_controller.py` and SHALL own all methods currently prefixed `_update_bg_*`, `_update_logo_*`, `_update_particles_*`, `_update_vignette_*`, `_update_smoke_*`, `_update_text_*`, `_update_layer_*`, `_update_style`, `_update_spectrum_enabled`, `_update_audio_sensitivity`, `_update_audio_smoothing`, `_update_anchor`, `_update_pos_x`, `_update_pos_y`, and `_reset_center` from `MainWindow`.
2. THE VideoPageController constructor SHALL accept typed parameters `template_accessor: Callable[[], dict]`, `template_mutator: Callable[[dict], None]`, `preview_accessor: Callable[[], PreviewConfig]`, and `persist_fn: Callable[[dict], None]`; the controller SHALL NOT hold a reference to `MainWindow`.
3. WHEN any `_update_*` method is called, THE VideoPageController SHALL read the current template via `template_accessor`, apply the parameter change, call `template_mutator` with the updated template, and call `persist_fn` with the settings patch to persist the change.
4. AFTER the extraction, THE MainWindow class body SHALL contain zero method definitions matching the pattern `_update_bg_*`, `_update_logo_*`, `_update_particles_*`, `_update_vignette_*`, `_update_smoke_*`, `_update_text_*`, or `_update_layer_*`.
5. THE VideoPageController SHALL also own `_apply_template_to_controls`, `_apply_style_and_audio_settings`, `_apply_background_settings`, `_apply_effect_settings`, `_apply_overlay_settings`, `_apply_layer_settings`, and `_apply_resolved_template_settings` methods that populate UI controls from a template dict.
6. THE VideoPageController public methods SHALL carry complete type annotations on all parameters and return values.

---

### Requirement 3: Extract AudioController for playback state management

**User Story:** As a senior developer, I want audio playback state (play, pause, stop, seek, duration tracking) owned by a single AudioController, so that playback logic is decoupled from UI widget code.

#### Acceptance Criteria

1. THE AudioController SHALL be implemented at `python_app/app/audio_controller.py` and SHALL own the methods `play_audio`, `toggle_playback`, `pause_audio`, `stop_audio`, `seek_relative`, `seek_to`, `_get_audio_duration`, `_sync_play_button_state`, and the state fields `_audio_paused` and `_seek_dragging`.
2. THE AudioController constructor SHALL accept `preview_accessor: Callable[[], object]` (providing access to the visualizer preview widget) and `ui_update_fn: Callable[[float, float], None]` (for updating seek label and slider); the controller SHALL NOT hold a reference to `MainWindow`.
3. WHEN `play_audio` is called, THE AudioController SHALL initialise pygame audio if not already active, load the selected MP3 via the preview accessor, and begin playback; all pygame state management SHALL be encapsulated within the AudioController.
4. WHEN `seek_to(t_sec)` is called, THE AudioController SHALL clamp `t_sec` to `[0, duration]` and update the pygame playback position accordingly.
5. THE AudioController SHALL expose a `tick()` method that returns `(current_time: float, duration: float)` for the UI timer to call on each render tick; the method SHALL NOT directly modify any widget.
6. AFTER the extraction, THE MainWindow class body SHALL contain zero definitions of `play_audio`, `toggle_playback`, `pause_audio`, `stop_audio`, `seek_relative`, `seek_to`, or `_get_audio_duration`.
7. THE AudioController public methods SHALL carry complete type annotations on all parameters and return values.

---

### Requirement 4: Extract SignalRouter for UiBus event dispatch

**User Story:** As a senior developer, I want all UiBus signal connections and event dispatch logic in a single SignalRouter class, so that the event routing map is explicit, testable, and not scattered across MainWindow.__init__ and handler methods.

#### Acceptance Criteria

1. THE SignalRouter SHALL be implemented at `python_app/app/signal_router.py` and SHALL own all `bus.*.connect(...)` registrations currently in `MainWindow.__init__` and the `_on_music_event` and `_on_export_event` dispatch methods.
2. THE SignalRouter constructor SHALL accept `bus: UiBus` and a `handlers: dict[str, Callable[[dict], None]]` mapping event type strings to handler callables; the router SHALL dispatch incoming events by looking up `event["type"]` in the handlers dict.
3. WHEN a `music_event` signal is received, THE SignalRouter SHALL look up `event["type"]` in the handlers dict and call the corresponding handler; IF no handler is registered for the event type, THEN THE SignalRouter SHALL log a DEBUG-level warning and discard the event.
4. WHEN an `export_event` signal is received, THE SignalRouter SHALL look up `event["type"]` in the handlers dict and call the corresponding handler with the same no-match behaviour as criterion 3.
5. THE SignalRouter SHALL expose a `register(event_type: str, handler: Callable[[dict], None]) -> None` method for late registration of handlers after construction.
6. AFTER the extraction, THE MainWindow class body SHALL contain zero definitions of `_on_music_event` or `_on_export_event` dispatch switch logic; only thin delegating calls to `self._signal_router` SHALL remain.
7. THE SignalRouter SHALL carry complete type annotations on all public methods.

---

### Requirement 5: Extract DashboardPageController

**User Story:** As a senior developer, I want all dashboard data refresh, profile combo syncing, and failure context menu logic owned by a DashboardPageController, so that dashboard behaviour is testable without MainWindow.

#### Acceptance Criteria

1. THE DashboardPageController SHALL be implemented at `python_app/features/progress/dashboard_page_controller.py` and SHALL own `_refresh_dashboard_async`, `_apply_dashboard_model`, `_dashboard_sync_profile_combo`, `_dashboard_selected_profile_id`, `_dashboard_failure_meta_at`, and `_on_dashboard_failures_context_menu`.
2. THE DashboardPageController constructor SHALL accept `db_cfg_accessor: Callable[[], DbCfg | None]`, `bus: UiBus`, `settings_accessor: Callable[[], dict]`, and typed widget accessors for the dashboard table and profile combo.
3. WHEN `_refresh_dashboard_async` is called, THE DashboardPageController SHALL query the database on a background thread and emit the result back to the UI thread via `bus.ui_invoke`; the controller SHALL NOT call `QApplication.processEvents()`.
4. AFTER the extraction, THE MainWindow class body SHALL contain zero definitions of `_refresh_dashboard_async`, `_apply_dashboard_model`, `_dashboard_sync_profile_combo`, or `_on_dashboard_failures_context_menu`.
5. THE DashboardPageController public methods SHALL carry complete type annotations on all parameters and return values.

---

### Requirement 6: Extract ProgressPageController

**User Story:** As a senior developer, I want all progress-table refresh, row context menus, merge-only orchestration, and cancel logic owned by a ProgressPageController, so that progress behaviour is testable without MainWindow.

#### Acceptance Criteria

1. THE ProgressPageController SHALL be implemented at `python_app/features/progress/progress_page_controller.py` and SHALL own `_refresh_progress_table`, `_refresh_progress_table_async`, `_apply_progress_rows`, `_collect_progress_rows`, `_scan_progress_output_dir`, `_progress_row_meta_at`, `_on_progress_table_context_menu`, `_on_progress_cell_double_clicked`, `_progress_download_mp3_for_batch`, `_progress_cancel_row`, `_progress_mark_visible_rows_cancelling`, `_progress_cancel_all_pending_jobs`, `_progress_restart_images`, `_progress_restart_converter`, `_progress_restart_converter_impl`, `_progress_auto_video_prereq_reasons`, `_merge_worker_limit`, `_merge_running_count`, `_enqueue_merge_only_task`, `_drain_merge_only_queue`, `_start_merge_only_thread`, `_progress_restart_merge_only`, and `_progress_restart_merge_only_impl`.
2. THE ProgressPageController constructor SHALL accept `db_cfg_accessor: Callable[[], DbCfg | None]`, `bus: UiBus`, `settings_accessor: Callable[[], dict]`, `merge_worker: MergeWorker`, and typed widget accessors for the progress table.
3. WHEN `_refresh_progress_table_async` is called, THE ProgressPageController SHALL use a cancellation token pattern (incrementing an integer) to discard stale results when a newer refresh has been requested.
4. AFTER the extraction, THE MainWindow class body SHALL contain zero definitions matching the method names listed in criterion 1.
5. THE ProgressPageController public methods SHALL carry complete type annotations on all parameters and return values.

---

### Requirement 7: Extract MusicPageController for music generation UI state

**User Story:** As a senior developer, I want music generation UI state, pool management, ngrok control, and history interaction owned by a MusicPageController, so that music page behaviour is testable without MainWindow.

#### Acceptance Criteria

1. THE MusicPageController SHALL be implemented at `python_app/features/music/music_page_controller.py` and SHALL own all methods prefixed `_on_music_*`, `_refresh_music_*`, `_persist_music_*`, `_music_pool_*`, `_on_music_pool_*`, `_select_music_history_row`, and the music ngrok control methods (`_on_music_ngrok_start`, `_on_music_ngrok_stop`, `_on_music_ngrok_refresh`, `_refresh_music_ngrok_status`).
2. THE MusicPageController constructor SHALL accept `music_coordinator: MusicGenerationCoordinator`, `db_cfg_accessor: Callable[[], DbCfg | None]`, `bus: UiBus`, `settings_accessor: Callable[[], dict]`, `footer: FooterController`, and typed widget accessors for music page widgets.
3. WHEN `_on_music_generate_clicked` is called, THE MusicPageController SHALL delegate to `music_coordinator` for the actual generation work; the controller SHALL own only the UI-level validation, status updates, and thread management.
4. AFTER the extraction, THE MainWindow class body SHALL contain zero definitions of methods matching the pattern `_on_music_*` (excluding `_on_music_event` which belongs to SignalRouter) or `_refresh_music_*`.
5. THE MusicPageController public methods SHALL carry complete type annotations on all parameters and return values.

---

### Requirement 8: Extract YouTubeOAuthController for OAuth app management

**User Story:** As a senior developer, I want YouTube OAuth app CRUD, profile connection/disconnection, and upload enqueueing owned by a dedicated controller, so that YouTube integration is testable without MainWindow.

#### Acceptance Criteria

1. THE YouTubeOAuthController SHALL be implemented at `python_app/features/youtube/oauth_controller.py` and SHALL own `_refresh_youtube_oauth_apps_table`, `_on_youtube_oauth_app_selected`, `_new_youtube_oauth_app`, `_save_youtube_oauth_app`, `_delete_youtube_oauth_app`, `_resolve_youtube_oauth_client`, `_youtube_connect_cancel_event_for`, `_clear_youtube_connect_state`, `_on_music_profile_youtube_connect`, `_on_music_profile_youtube_disconnect`, `_start_youtube_oauth_connect`, `_enqueue_youtube_upload_for_merge`, and `_youtube_scan_for_merged_outputs`.
2. THE YouTubeOAuthController constructor SHALL accept `db_cfg_accessor: Callable[[], DbCfg | None]`, `youtube_coordinator: YouTubeCoordinator`, `settings_accessor: Callable[[], dict]`, and typed widget accessors for the OAuth apps table and form fields.
3. WHEN `_save_youtube_oauth_app` is called, THE YouTubeOAuthController SHALL encrypt the client secret via `dpapi_encrypt_to_base64` before persisting and SHALL decrypt via `dpapi_decrypt_from_base64` when loading for display.
4. AFTER the extraction, THE MainWindow class body SHALL contain zero definitions of `_refresh_youtube_oauth_apps_table`, `_new_youtube_oauth_app`, `_save_youtube_oauth_app`, `_delete_youtube_oauth_app`, or `_resolve_youtube_oauth_client`.
5. THE YouTubeOAuthController public methods SHALL carry complete type annotations on all parameters and return values.

---

### Requirement 9: Reduce MainWindow to a thin composition shell

**User Story:** As a senior developer, I want MainWindow to contain only component wiring, navigation switching, and the `closeEvent` lifecycle — ideally under 500 lines — so that the God class is eliminated.

#### Acceptance Criteria

1. AFTER all page controllers, AudioController, SignalRouter, and InitOrchestrator are extracted, THE MainWindow class body (excluding blank lines and comments) SHALL contain fewer than 500 lines of code as measured by `wc -l` on lines that contain at least one non-whitespace character inside the class body.
2. THE MainWindow class SHALL retain only: the class declaration with mixin inheritance, `__init__` (which delegates to InitOrchestrator), `closeEvent`, `eventFilter`, `_set_primary_page`, `_tick_ui` (delegating to AudioController), property accessors needed by view mixins, and any one-line forwarding methods required for backward compatibility with existing view mixin calls.
3. WHEN a view mixin calls a method that was extracted (e.g., `self._update_bg_brightness`), THE MainWindow SHALL provide a one-line forwarding method `def _update_bg_brightness(self, v: int) -> None: self._video_controller.update_bg_brightness(v)` until the view mixin is updated to call the controller directly; these forwarding methods SHALL carry a `# TODO: remove after view mixin update` comment.
4. THE MainWindow `__init__` SHALL consist of: `super().__init__()`, one call to `InitOrchestrator(self).run()`, and assignment of the result to `self` attributes; no coordinator construction, timer registration, or UI building logic SHALL appear directly in `__init__`.
5. THE MainWindow file SHALL contain zero inline `import` statements inside method bodies after the decomposition.

---

### Requirement 10: Ensure deterministic initialization order prevents AttributeError

**User Story:** As a developer, I want a guarantee that no coordinator or timer callback accesses an attribute before it is assigned, so that the `AttributeError` bugs on `_timer_registry` and `db_cfg` are structurally impossible.

#### Acceptance Criteria

1. THE InitOrchestrator Phase A SHALL assign every attribute that is read by any coordinator constructor in Phase B; the complete list SHALL include at minimum: `db_cfg`, `bus`, `music_data`, `e_settings`, `template`, `ui`, `_footer`, `_timer_registry`, `_ffmpeg_path`, `_output_dir`, `_app_closing`, `_primary_page_index`.
2. WHEN a coordinator constructor in Phase B reads `db_cfg`, THE attribute SHALL already be assigned (either `None` or a valid `DbCfg` instance) by Phase A; the coordinator SHALL handle a `None` value gracefully without raising `AttributeError`.
3. WHEN `TimerRegistry` callbacks fire, THE callbacks SHALL only reference attributes that were assigned in Phase A, B, or C (all of which complete before Phase D starts the timers); no timer callback SHALL access a widget that is built in a later phase than when the timer was registered.
4. THE InitOrchestrator SHALL enforce phase ordering by raising `RuntimeError` if `run()` is called more than once on the same instance (preventing re-entrant initialization).
5. WHEN a new attribute dependency is added in the future, THE InitOrchestrator docstring SHALL document the phase-dependency contract: "Any attribute read in Phase N must be assigned in Phase N-1 or earlier."

---

### Requirement 11: Preserve all existing runtime behaviour

**User Story:** As a QA engineer, I want the decomposed application to behave identically to the original at runtime, so that no user-facing functionality is broken.

#### Acceptance Criteria

1. WHEN the application starts after decomposition, THE MainWindow SHALL complete all four InitOrchestrator phases in order and display the home page within the same observable startup time (no measurable regression beyond 100ms).
2. WHEN a user triggers any of the following actions — music generation, image generation, video export, YouTube upload, template save, settings change, audio playback — THE application SHALL produce the same observable outcomes (status-bar text, database record written, file written, UiBus signal emitted) as before the decomposition.
3. WHEN `MainWindow.closeEvent` fires, THE shutdown sequence SHALL execute in the same order: (a) cancel YouTube runtime jobs, (b) cancel DB-level background jobs, (c) stop music coordinator polling, (d) stop image coordinator polling, (e) stop all timers via `TimerRegistry.stop_all()`, (f) increment cancellation tokens.
4. THE view mixins (`DashboardViewMixin`, `WorkflowViewMixin`, `MusicViewMixin`, `ImageViewMixin`, `VideoViewMixin`, `ProgressViewMixin`, `SettingsViewMixin`, `CoreViewMixin`, `LogViewMixin`) SHALL continue to function without modification in the first phase of decomposition; forwarding methods on MainWindow SHALL bridge the gap until mixins are updated.
5. THE `MusicUiHandlersMixin`, `ImageUiHandlersMixin`, `AutoVideoHandlersMixin`, and `YouTubeUploadHandlersMixin` SHALL continue to function via forwarding methods until their logic is absorbed by the appropriate PageController.

---

### Requirement 12: Enable isolated unit testing of each extracted controller

**User Story:** As a senior developer, I want each new controller to be constructable with mock dependencies in a pytest test, so that I can verify behaviour without a QApplication or database.

#### Acceptance Criteria

1. THE VideoPageController SHALL be constructable by passing callables that return test-fixture dicts for `template_accessor` and mock objects for `preview_accessor`; calling any `_update_*` method with a valid value SHALL complete without raising exceptions.
2. THE AudioController SHALL be constructable with a mock preview accessor and a no-op `ui_update_fn`; calling `play_audio` when pygame is not initialised SHALL raise a well-defined `RuntimeError` rather than an unhandled pygame exception.
3. THE SignalRouter SHALL be constructable with a mock `UiBus` and an empty handlers dict; emitting an event with an unregistered type SHALL log a warning and not raise.
4. THE DashboardPageController and ProgressPageController SHALL be constructable with `db_cfg_accessor` returning `None`; calling their async refresh methods SHALL gracefully skip the database query and return without raising.
5. THE MusicPageController SHALL be constructable with a mock `MusicGenerationCoordinator` and mock widget accessors; calling `_on_music_generate_clicked` with valid inputs SHALL delegate to the coordinator mock.
6. THE YouTubeOAuthController SHALL be constructable with a mock `YouTubeCoordinator` and mock widget accessors; calling `_save_youtube_oauth_app` with test data SHALL call the expected persistence function.
7. FOR EACH extracted controller, THERE SHALL be at least one `pytest` test file in `python_app/tests/` that exercises the constructor and at least two public methods with assertion on observable effects (return values, mock call counts, or state changes).

