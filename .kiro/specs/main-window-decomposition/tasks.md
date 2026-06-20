# Implementation Plan: MainWindow Decomposition

## Overview

Decompose the ~4181-line `MainWindow` God class into a thin composition shell delegating to single-responsibility controllers and an initialization orchestrator. The implementation proceeds bottom-up: extract leaf controllers first (no dependencies on other new controllers), then wire them together via SignalRouter and InitOrchestrator, and finally slim MainWindow to a thin shell with forwarding methods.

## Tasks

- [x] 1. Extract InitOrchestrator with deterministic lifecycle phases
  - [x] 1.1 Create `python_app/app/init_orchestrator.py` with the `InitOrchestrator` class
    - Implement the class with `__init__(self, host: "MainWindow")` and `run()` method
    - Implement `_phase_a_state_defaults` assigning all Phase A attributes (`db_cfg`, `bus`, `music_data`, `e_settings`, `template`, `ui`, `_footer`, `_timer_registry`, `_ffmpeg_path`, `_output_dir`, `_app_closing`, `_primary_page_index`, `_audio_paused`, `_seek_dragging`)
    - Implement `_phase_b_coordinators` constructing all coordinators in defined order
    - Implement `_phase_c_ui_build` invoking view mixin page-building methods
    - Implement `_phase_d_timers_and_restore` registering timers and restoring state
    - Add `log_line` calls at start/end of each phase
    - Add try/except per phase that logs phase name + exception and re-raises
    - Add `RuntimeError` guard on double `run()` calls
    - Add docstring documenting the phase-dependency contract
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 10.1, 10.4, 10.5_

  - [ ]* 1.2 Write property tests for InitOrchestrator
    - **Property 2: Phase exception handling preserves diagnostics**
    - **Property 3: Phase lifecycle logging brackets every phase**
    - **Property 10: InitOrchestrator single-run guard**
    - **Validates: Requirements 1.6, 1.7, 10.4**

  - [ ]* 1.3 Write unit tests for InitOrchestrator
    - Test constructor and phase call order
    - Test RuntimeError on double run()
    - Test log_line output for each phase
    - Test exception handling with traceback preservation
    - _Requirements: 1.6, 1.7, 10.4_

- [x] 2. Extract AudioController for playback state management
  - [x] 2.1 Create `python_app/app/audio_controller.py` with the `AudioController` class
    - Implement constructor accepting `preview_accessor` and `ui_update_fn` callables
    - Move `play_audio`, `toggle_playback`, `pause_audio`, `stop_audio`, `seek_relative`, `seek_to`, `_get_audio_duration`, `_sync_play_button_state` from MainWindow
    - Implement `tick()` method returning `(current_time, duration)` without modifying widgets
    - Add state fields `_audio_paused` and `_seek_dragging`
    - Ensure `seek_to` clamps to `[0, duration]`
    - Raise `RuntimeError` when `play_audio` is called with uninitialized pygame
    - Add complete type annotations on all public methods
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 2.2 Write property tests for AudioController
    - **Property 5: Audio seek clamping**
    - **Property 6: Audio tick purity**
    - **Validates: Requirements 3.4, 3.5**

  - [ ]* 2.3 Write unit tests for AudioController
    - Test play/pause/stop sequences with mocked pygame
    - Test RuntimeError on uninitialized pygame
    - Test seek_to clamping with edge values
    - Test tick() returns tuple without widget calls
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 12.2_

- [x] 3. Extract SignalRouter for UiBus event dispatch
  - [x] 3.1 Create `python_app/app/signal_router.py` with the `SignalRouter` class
    - Implement constructor accepting `bus: UiBus` and `handlers: dict[str, Callable[[dict], None]]`
    - Implement `_on_music_event` and `_on_export_event` dispatch methods
    - Implement `_dispatch` method that looks up `event["type"]` in handlers dict
    - Implement `register(event_type, handler)` for late registration
    - Log DEBUG-level warning for unregistered event types
    - Add complete type annotations on all public methods
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7_

  - [ ]* 3.2 Write property tests for SignalRouter
    - **Property 7: Signal dispatch correctness**
    - **Validates: Requirements 4.3, 4.4, 4.5, 12.3**

  - [ ]* 3.3 Write unit tests for SignalRouter
    - Test registration and dispatch of known event types
    - Test DEBUG log for unregistered event type
    - Test late registration via `register()` method
    - Test construction with empty handlers dict
    - _Requirements: 4.3, 4.4, 4.5, 12.3_

- [x] 4. Extract VideoPageController for template and spectrum parameters
  - [x] 4.1 Create `python_app/features/video_export/video_page_controller.py` with the `VideoPageController` class
    - Implement constructor accepting `template_accessor`, `template_mutator`, `preview_accessor`, `persist_fn`, and `widget_accessors`
    - Move all `_update_bg_*`, `_update_logo_*`, `_update_particles_*`, `_update_vignette_*`, `_update_smoke_*`, `_update_text_*`, `_update_layer_*`, `_update_style`, `_update_spectrum_enabled`, `_update_audio_sensitivity`, `_update_audio_smoothing`, `_update_anchor`, `_update_pos_x`, `_update_pos_y`, `_reset_center` from MainWindow
    - Move `_apply_template_to_controls`, `_apply_style_and_audio_settings`, `_apply_background_settings`, `_apply_effect_settings`, `_apply_overlay_settings`, `_apply_layer_settings`, `_apply_resolved_template_settings` from MainWindow
    - Each update method: read template via accessor, apply change, call mutator, call persist_fn
    - Add complete type annotations on all public methods
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6_

  - [ ]* 4.2 Write property tests for VideoPageController
    - **Property 4: Template update pipeline invariant**
    - **Validates: Requirements 2.3, 12.1**

  - [ ]* 4.3 Write unit tests for VideoPageController
    - Test specific update methods with concrete slider values
    - Test apply methods populate controls correctly
    - Test construction with mock callables
    - _Requirements: 2.3, 2.5, 12.1_

- [x] 5. Checkpoint — Core controllers extracted
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Extract DashboardPageController
  - [x] 6.1 Create `python_app/features/progress/dashboard_page_controller.py` with the `DashboardPageController` class
    - Implement constructor accepting `db_cfg_accessor`, `bus`, `settings_accessor`, and `widget_accessors`
    - Move `_refresh_dashboard_async`, `_apply_dashboard_model`, `_dashboard_sync_profile_combo`, `_dashboard_selected_profile_id`, `_dashboard_failure_meta_at`, `_on_dashboard_failures_context_menu` from MainWindow
    - Ensure `_refresh_dashboard_async` uses `bus.ui_invoke` for thread-safe UI updates
    - Handle `db_cfg_accessor()` returning `None` gracefully (skip DB query)
    - Add complete type annotations on all public methods
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 6.2 Write unit tests for DashboardPageController
    - Test construction with `db_cfg_accessor` returning `None`
    - Test profile combo sync with mock widgets
    - Test failure meta extraction
    - _Requirements: 5.4, 5.5, 12.4_

- [x] 7. Extract ProgressPageController
  - [x] 7.1 Create `python_app/features/progress/progress_page_controller.py` with the `ProgressPageController` class
    - Implement constructor accepting `db_cfg_accessor`, `bus`, `settings_accessor`, `merge_worker`, and `widget_accessors`
    - Move all methods listed in Requirement 6.1 from MainWindow
    - Implement cancellation token pattern: increment `_refresh_token` on each call, discard stale results
    - Handle `db_cfg_accessor()` returning `None` gracefully
    - Implement merge queue orchestration (`_drain_merge_only_queue`, `_start_merge_only_thread`, etc.)
    - Add complete type annotations on all public methods
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 7.2 Write property tests for ProgressPageController
    - **Property 8: Stale refresh cancellation**
    - **Validates: Requirements 6.3**

  - [ ]* 7.3 Write unit tests for ProgressPageController
    - Test cancellation token discards stale results
    - Test context menu actions with mock widgets
    - Test merge orchestration with mock merge_worker
    - Test graceful skip when db_cfg is None
    - _Requirements: 6.3, 6.4, 12.4_

- [x] 8. Extract MusicPageController
  - [x] 8.1 Create `python_app/features/music/music_page_controller.py` with the `MusicPageController` class
    - Implement constructor accepting `music_coordinator`, `db_cfg_accessor`, `bus`, `settings_accessor`, `footer`, and `widget_accessors`
    - Move all `_on_music_*` methods (except `_on_music_event`), `_refresh_music_*`, `_persist_music_*`, `_music_pool_*`, `_on_music_pool_*`, `_select_music_history_row`, and ngrok methods from MainWindow
    - Ensure `_on_music_generate_clicked` delegates to `music_coordinator` for actual generation
    - Handle `db_cfg_accessor()` returning `None` gracefully
    - Add complete type annotations on all public methods
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 8.2 Write unit tests for MusicPageController
    - Test generate clicked delegates to coordinator mock
    - Test construction with mock dependencies
    - Test ngrok start/stop with mock coordinator
    - _Requirements: 7.3, 7.4, 12.5_

- [x] 9. Extract YouTubeOAuthController
  - [x] 9.1 Create `python_app/features/youtube/oauth_controller.py` with the `YouTubeOAuthController` class
    - Implement constructor accepting `db_cfg_accessor`, `youtube_coordinator`, `settings_accessor`, `widget_accessors`, and optional `persist_fn`
    - Move `_refresh_youtube_oauth_apps_table`, `_on_youtube_oauth_app_selected`, `_new_youtube_oauth_app`, `_save_youtube_oauth_app`, `_delete_youtube_oauth_app`, `_resolve_youtube_oauth_client`, `_youtube_connect_cancel_event_for`, `_clear_youtube_connect_state`, `_on_music_profile_youtube_connect`, `_on_music_profile_youtube_disconnect`, `_start_youtube_oauth_connect`, `_enqueue_youtube_upload_for_merge`, `_youtube_scan_for_merged_outputs` from MainWindow
    - Ensure `_save_youtube_oauth_app` encrypts secret via `dpapi_encrypt_to_base64` before persisting
    - Ensure loading decrypts via `dpapi_decrypt_from_base64`
    - Handle `db_cfg_accessor()` returning `None` gracefully
    - Add complete type annotations on all public methods
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 9.2 Write property tests for YouTubeOAuthController
    - **Property 9: Secret encryption round-trip**
    - **Validates: Requirements 8.3**

  - [ ]* 9.3 Write unit tests for YouTubeOAuthController
    - Test save/delete CRUD operations with mocked DB
    - Test encryption call on save
    - Test decryption call on load for display
    - Test construction with mock dependencies
    - _Requirements: 8.3, 8.4, 12.6_

- [x] 10. Checkpoint — All page controllers extracted
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Reduce MainWindow to thin composition shell
  - [x] 11.1 Refactor `MainWindow.__init__` to delegate to InitOrchestrator
    - Replace all initialization logic in `__init__` with `super().__init__()` + `InitOrchestrator(self).run()`
    - Remove all coordinator construction, timer registration, and UI building from `__init__`
    - _Requirements: 9.4, 10.1_

  - [x] 11.2 Remove extracted methods from MainWindow and add forwarding methods
    - Remove all `_update_*` method bodies from MainWindow (delegate to `self._video_controller`)
    - Remove `play_audio`, `toggle_playback`, `pause_audio`, `stop_audio`, `seek_relative`, `seek_to`, `_get_audio_duration` (delegate to `self._audio_controller`)
    - Remove `_on_music_event`, `_on_export_event` dispatch logic (delegate to `self._signal_router`)
    - Remove dashboard, progress, music, youtube method bodies (delegate to respective controllers)
    - Add one-line forwarding methods with `# TODO: remove after view mixin update` comments
    - Remove all inline imports from method bodies
    - _Requirements: 2.4, 3.6, 4.6, 5.4, 6.4, 7.4, 8.4, 9.1, 9.2, 9.3, 9.5_

  - [x] 11.3 Retain only shell methods on MainWindow
    - Keep `closeEvent` with proper shutdown sequence (cancel YouTube jobs → cancel DB jobs → stop music polling → stop image polling → stop all timers → increment cancellation tokens)
    - Keep `eventFilter`, `_set_primary_page`, `_tick_ui` (delegating to AudioController)
    - Keep property accessors needed by view mixins
    - Verify MainWindow class body < 500 non-blank lines
    - _Requirements: 9.1, 9.2, 9.4, 11.3_

- [x] 12. Wire InitOrchestrator Phase B to construct all extracted controllers
  - [x] 12.1 Update InitOrchestrator `_phase_b_coordinators` to construct new controllers
    - Construct `AudioController` with appropriate accessors
    - Construct `VideoPageController` with template accessors and persist function
    - Construct `SignalRouter` with UiBus and handlers dict from event routing map
    - Construct `DashboardPageController`, `ProgressPageController`, `MusicPageController`, `YouTubeOAuthController` with their respective dependencies
    - Assign all controllers to `self._host` attributes
    - _Requirements: 1.3, 10.1, 10.2_

  - [ ]* 12.2 Write property tests for Phase A attribute availability
    - **Property 1: Phase ordering guarantees attribute availability**
    - **Property 11: Timer callback safety**
    - **Validates: Requirements 1.2, 1.3, 10.1, 10.2, 10.3**

  - [ ]* 12.3 Write property tests for graceful None db_cfg degradation
    - **Property 12: Graceful degradation with None db_cfg**
    - **Validates: Requirements 12.4**

- [x] 13. Final checkpoint — Full decomposition verified
  - Ensure all tests pass, ask the user if questions arise.
  - Verify MainWindow class body < 500 non-blank lines
  - Verify no `_update_bg_*`, `_update_logo_*`, `_update_particles_*`, `_update_vignette_*`, `_update_smoke_*`, `_update_text_*`, `_update_layer_*` methods remain on MainWindow
  - Verify no `play_audio`, `toggle_playback`, `pause_audio`, `stop_audio`, `seek_relative`, `seek_to`, `_get_audio_duration` remain on MainWindow
  - Verify no `_on_music_event` or `_on_export_event` dispatch switch logic remains on MainWindow
  - Verify all view mixins and handler mixins continue functioning via forwarding methods
  - _Requirements: 9.1, 9.2, 11.1, 11.2, 11.3, 11.4, 11.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Forwarding methods on MainWindow are temporary — they will be removed in a follow-up pass when view mixins are updated to call controllers directly
- The extraction order (InitOrchestrator → AudioController → SignalRouter → VideoPageController → page controllers → shell reduction) ensures each step builds on the previous without orphaned code

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.2", "2.3", "3.2", "3.3", "4.1"] },
    { "id": 2, "tasks": ["4.2", "4.3", "6.1", "7.1", "8.1", "9.1"] },
    { "id": 3, "tasks": ["6.2", "7.2", "7.3", "8.2", "9.2", "9.3"] },
    { "id": 4, "tasks": ["11.1", "11.2", "12.1"] },
    { "id": 5, "tasks": ["11.3", "12.2", "12.3"] }
  ]
}
```
