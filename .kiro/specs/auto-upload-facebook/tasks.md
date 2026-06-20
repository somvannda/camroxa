# Implementation Plan: Auto Upload Facebook

## Overview

This plan implements automated Facebook page video/reel uploads via Playwright browser automation, plus a manual upload flow triggered from the Progress page context menu. The implementation proceeds from database schema and data layer, through the core feature module (coordinator, session manager, browser automation, selector registry), to UI integration, diagnostics, resilience features, and the manual upload orchestrator with Merge_Choice_Dialog. Each task builds incrementally on the previous, using the established coordinator dependency injection pattern.

## Tasks

- [ ] 1. Database schema and data layer
  - [ ] 1.1 Create database migration for Facebook upload tables
    - Add `db_migrate_facebook_tables` function in `python_app/features/facebook_upload/db.py`
    - Create `facebook_accounts` table with columns: uid, label, browser_profile_path, session_status, created_at, updated_at
    - Create `facebook_pages` table with columns: uid, account_uid (FK CASCADE), page_name, page_url, is_active, last_verified_at
    - Create `facebook_upload_jobs` table with all status-tracking columns per design
    - Use CREATE TABLE IF NOT EXISTS for idempotence
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ] 1.2 Implement Facebook account CRUD functions
    - Implement `db_add_facebook_account`, `db_remove_facebook_account`, `db_list_facebook_accounts`, `db_update_account_session_status`
    - Ensure account removal cascades to associated pages (ON DELETE CASCADE)
    - Each function opens/closes its own DB connection in a finally block
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [ ] 1.3 Implement Facebook page CRUD functions
    - Implement `db_upsert_facebook_pages`, `db_list_facebook_pages`, `db_list_active_facebook_pages`, `db_set_page_active`
    - _Requirements: 3.2, 3.3, 3.4_

  - [ ] 1.4 Implement Facebook upload job queue functions
    - Implement `db_enqueue_facebook_upload_job`, `db_pick_next_pending_job` (FIFO by created_at), `db_mark_job_uploading`, `db_mark_job_completed`, `db_mark_job_failed`, `db_mark_job_failed_permanent`
    - Implement `db_mark_jobs_blocked_session`, `db_unblock_session_jobs`, `db_retry_job`, `db_list_facebook_upload_jobs`, `db_count_daily_uploads`
    - _Requirements: 5.3, 5.4, 6.1, 8.1, 8.3, 8.5, 12.5, 16.5_

  - [ ]* 1.5 Write property tests for database layer
    - **Property 2: Account storage round-trip** — Add N accounts, list returns N with matching fields
    - **Property 3: Account removal cascades to pages** — Remove account, zero pages remain
    - **Property 6: Jobs are always created with pending status** — New jobs have status "pending" and attempt_count 0
    - **Property 7: FIFO queue ordering** — Pick returns job with earliest created_at
    - **Property 19: Migration idempotence** — Running migration twice produces no errors
    - **Validates: Requirements 2.2, 2.3, 2.4, 5.4, 6.1, 14.4**

- [ ] 2. Module structure and coordinator skeleton
  - [ ] 2.1 Create feature module directory structure
    - Create `python_app/features/facebook_upload/` directory
    - Create `__init__.py` with public interface declarations per design (including ManualUploadOrchestrator, ManualUploadResult, ReelPrerequisiteResult)
    - Create empty module files: `coordinator.py`, `db.py`, `browser_automation.py`, `session_manager.py`, `selector_registry.py`, `diagnostic.py`, `dom_snapshot.py`, `selector_hints.py`, `record_replay.py`, `manual_page_entry.py`, `manual_upload.py`
    - Create `snapshots/` subdirectory with `.gitkeep`
    - _Requirements: 15.1, 15.2, 15.4_

  - [ ] 2.2 Implement FacebookUploadCoordinator skeleton with dependency injection
    - Define `FacebookUploadHostPort` dataclass with settings_accessor, db_cfg_accessor, logger, event_bus, defer_call, timer_factory
    - Implement coordinator lifecycle: `start()`, `stop()`, `on_app_start()` (resets autoUploadFacebook to false)
    - Implement toggle management: `set_auto_upload_enabled()`, `is_auto_upload_enabled()`
    - Implement fault isolation: top-level try/except in all public methods, disabled state handling
    - _Requirements: 1.5, 11.1, 11.2, 15.3, 15.5_

  - [ ] 2.3 Implement RateLimiter class embedded in coordinator
    - Implement `wait_if_needed()`, `record_completion()`, `compute_delay()` with base_delay + random jitter
    - Enforce minimum 60 seconds for rate limit setting
    - Add randomized jitter of 0–30 seconds to configured delay
    - _Requirements: 6.2, 13.2, 16.4_

  - [ ]* 2.4 Write property tests for coordinator core logic
    - **Property 1: Toggle persistence round-trip** — Write/read autoUploadFacebook returns same value
    - **Property 8: Rate limiter delay enforcement** — Computed delay in [D, D+30] range
    - **Property 9: Job status transitions preserve queue on pause** — Disabling toggle leaves all jobs pending
    - **Property 16: Exception containment** — Any exception in on_auto_video_done does not propagate
    - **Property 18: Rate limit setting minimum enforcement** — Persisted value is max(60, V)
    - **Validates: Requirements 1.2, 1.3, 6.2, 6.5, 11.1, 13.2, 16.4**

- [ ] 3. Checkpoint - Verify data layer and coordinator skeleton
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Session management and browser automation core
  - [ ] 4.1 Implement SessionManager
    - Implement `validate_session()` that launches a Playwright persistent context and checks for authenticated-state indicators
    - Implement `create_context()` for headless mode and `launch_visible_session()` for manual login
    - Implement `close_context()` with safe cleanup
    - Return `SessionStatus` enum (VALID, EXPIRED, UNKNOWN)
    - _Requirements: 4.1, 4.2, 4.4, 4.5, 4.6_

  - [ ] 4.2 Implement SelectorRegistry with YAML config loading
    - Implement `load()` to parse `selectors.yaml` into `SelectorConfig` dataclass
    - Implement `get_action()` to retrieve `ActionSelectors` for a named action
    - Implement `resolve_element()` with multi-strategy fallback in priority order (role → text → test_id → label → CSS → XPath)
    - Implement `resolve_element_with_report()` returning which strategy succeeded
    - Log which strategy resolved and at what priority index
    - On total failure: raise `SelectorResolutionError` with failure context
    - _Requirements: 7.2, 7.5_

  - [ ] 4.3 Create default selectors.yaml configuration file
    - Create `python_app/features/facebook_upload/selectors.yaml` with all action definitions per design
    - Include actions: navigate_to_reel_upload, detect_upload_page_ready, file_input, caption_input, publish_button, upload_success_indicator, page_switcher, page_list_items
    - Each action has multiple ordered strategies with method, value, and description
    - _Requirements: 7.2_

  - [ ] 4.4 Implement BrowserAutomation upload_reel flow
    - Implement `upload_reel()` method following the step-by-step flow: validate session → navigate → detect page state → file input → wait processing → caption → publish → detect success
    - Use `SelectorRegistry.resolve_element()` for all element lookups
    - Implement `_detect_page_state()` using URL patterns and content signals
    - Implement `_wait_for_state()` for state-based waiting
    - Implement human-like typing with randomized inter-keystroke delays (30–120ms)
    - Add randomized delays (1–3s) between UI interactions
    - Return `UploadResult` with success/failure details
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 16.1, 16.2, 16.3_

  - [ ]* 4.5 Write property tests for selector registry and automation timing
    - **Property 20: Anti-detection timing bounds** — Interaction delays in [1.0, 3.0]s, keystroke delays in [30, 120]ms, jitter in [0, 30]s
    - **Property 22: Selector resolution priority ordering** — First successful strategy stops resolution
    - **Property 23: Selector config round-trip** — Serialize YAML → deserialize produces equivalent config
    - **Validates: Requirements 7.2, 7.5, 16.1, 16.2, 16.4**

- [ ] 5. Job creation, queue processing, and retry logic
  - [ ] 5.1 Implement job creation from pipeline events
    - Implement `on_auto_video_done()` handler in coordinator
    - In "merged_reel" mode: create one job per active page using the merged reel file
    - In "individual_reels" mode: create one job per individual reel file per active page
    - Implement fallback: if merged_reel mode but reelOutput is empty, fall back to individual files
    - Emit warning if no active pages are configured
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 10.2, 10.3, 10.5_

  - [ ] 5.2 Implement caption template resolution
    - Implement template resolution with placeholders: {track_name}, {batch_date}, {profile_name}, {role}
    - Enforce 2200 character max with ellipsis truncation
    - Store resolved caption in job record at creation time
    - _Requirements: 9.2, 9.3, 9.5_

  - [ ] 5.3 Implement Upload Worker thread with queue processing
    - Implement `process_queue_tick()` that picks next pending job and processes it
    - Start/stop worker thread based on autoUploadFacebook toggle
    - Enforce single worker thread to prevent concurrent browser sessions
    - Integrate RateLimiter between consecutive uploads
    - Update job status through lifecycle: pending → uploading → completed/failed
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 5.4 Implement retry logic with exponential backoff and error classification
    - Implement `classify_error()` function mapping exceptions to "transient", "session", "permanent"
    - Implement backoff schedule: attempt 1→2min, 2→5min, 3→15min, 4→60min, >4→failed_permanent
    - On session failure: mark all account jobs as "blocked_session"
    - On session restore: transition "blocked_session" jobs back to "pending"
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ] 5.5 Implement daily upload limit enforcement
    - Check `db_count_daily_uploads()` before processing a job for a page
    - If limit reached, skip/pause processing for that page and emit status message
    - Configurable via `facebookDailyUploadLimit` setting (default 10)
    - _Requirements: 16.5, 16.6_

  - [ ] 5.6 Implement create_manual_jobs method on coordinator
    - Add `create_manual_jobs(file_paths, batch_id, profile_id, role, caption, hashtags)` method
    - Create one job per file_path per active Facebook page with status "pending"
    - Resolve caption template if caption is empty
    - Return (total_jobs_created, list_of_target_page_names)
    - Does not start upload worker — worker picks up pending jobs on its own tick
    - _Requirements: 17.8, 17.9, 17.10, 17.11_

  - [ ]* 5.7 Write property tests for job creation and retry logic
    - **Property 4: Job creation count in merged_reel mode** — N active pages → N jobs created
    - **Property 5: Job creation count in individual_reels mode** — M files × N pages → M×N jobs
    - **Property 10: Retry backoff schedule** — Attempt count maps to correct delay
    - **Property 11: Session failure blocks all account jobs** — Session expiry → all jobs blocked
    - **Property 12: Session restoration unblocks jobs** — Session valid → jobs back to pending
    - **Property 13: Error classification completeness** — Every exception maps to one valid category
    - **Property 14: Caption template resolution** — No unresolved placeholders in output
    - **Property 15: Caption length enforcement** — Result always ≤ 2200 chars
    - **Property 21: Daily upload limit enforcement** — At limit, no more jobs processed for page
    - **Property 30: Manual upload single-file job creation per page** — 1 file × N pages → N jobs
    - **Property 31: Manual upload multi-file job creation** — M files × N pages → M×N jobs
    - **Validates: Requirements 5.1, 5.2, 8.1, 8.2, 8.3, 8.4, 8.5, 9.2, 9.3, 9.5, 16.5, 17.8, 17.9, 17.10**

- [ ] 6. Checkpoint - Verify core upload pipeline
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. DOM snapshots, selector hints, and diagnostics
  - [ ] 7.1 Implement DOMSnapshot module
    - Implement `capture()` that takes screenshot (PNG) + extracts simplified DOM tree on failures
    - Implement `simplify_dom()` to strip scripts, styles, SVG, hidden elements; retain only structural/semantic info
    - Implement `list_snapshots()` and `cleanup_old_snapshots(keep_last=50)`
    - Save files as `snapshots/{action_name}_{timestamp}.png` and `snapshots/{action_name}_{timestamp}_dom.html`
    - _Requirements: 7.5_

  - [ ] 7.2 Implement SelectorHints module
    - Implement `find_similar_elements()` that analyzes DOM when selectors fail
    - Score candidates by: ARIA role match (+0.3), text similarity via Levenshtein (+0.3), same tag (+0.2), DOM position (+0.2)
    - Filter candidates with confidence > 0.4
    - Return `HintsReport` with scored `SelectorHint` entries
    - _Requirements: 7.5_

  - [ ] 7.3 Wire DOMSnapshot and SelectorHints into BrowserAutomation
    - Update `SelectorRegistry.resolve_element()` to invoke DOMSnapshot and SelectorHints on total failure
    - Implement `_handle_resolution_failure()` in BrowserAutomation
    - Include hints in UploadResult error details and job error_message
    - Log high-confidence hints (>0.7) at WARNING level
    - _Requirements: 7.5_

  - [ ] 7.4 Implement DiagnosticMode
    - Implement `run_full_diagnostic()` that walks through upload flow visibly, logging each step
    - For each step: try all selector strategies, capture screenshot, record page URL/state
    - Return `DiagnosticReport` with steps, broken_steps, and human-readable recommendations
    - Implement `run_page_discovery_diagnostic()` for page discovery path testing
    - _Requirements: 13.5_

  - [ ] 7.5 Implement selector health check (dry-run validation)
    - Implement `run_selector_health_check()` in BrowserAutomation
    - Navigate to upload page, validate every configured selector without interacting
    - Return one `StepResult` per action in selectors.yaml
    - _Requirements: 13.5_

  - [ ]* 7.6 Write property tests for diagnostics modules
    - **Property 24: DOM snapshot capture on resolution failure** — All strategies fail → PNG + DOM file captured with correct naming
    - **Property 25: Selector hint confidence bounds** — All scores in [0.0, 1.0], only > 0.4 included
    - **Property 28: Health check covers all configured actions** — N actions in config → N StepResults returned
    - **Validates: Requirements 7.5, 13.5**

- [ ] 8. Record/Replay mode and manual page entry
  - [ ] 8.1 Implement RecordReplayMode
    - Implement `start_recording()` that launches visible browser and captures all user interactions via CDP events
    - Implement `_attach_interaction_listeners()` for click, fill, file_upload, navigate events
    - Implement `_map_interactions_to_actions()` using step detection heuristics
    - Implement `_generate_selector_config()` to produce strategies from recorded element attributes (priority: role → text → test_id → label → CSS → XPath)
    - Implement `apply_recording()` with backup of existing selectors.yaml before overwrite
    - _Requirements: 15.2_

  - [ ] 8.2 Implement ManualPageEntry
    - Implement `validate_page_url()` against accepted Facebook page URL patterns
    - Implement `normalize_page_url()` and `derive_page_name()`
    - Implement `add_page_manually()` with duplicate detection and DB storage
    - _Requirements: 3.1_

  - [ ] 8.3 Implement page discovery with multi-path navigation
    - Implement `discover_pages()` in BrowserAutomation using PageDiscoveryStrategy
    - Try primary URL (/pages/switching), then fallback URLs in sequence
    - Extract page names and URLs using selector_registry strategies
    - Wire into coordinator's `discover_pages()` method
    - _Requirements: 3.1, 3.2, 3.5_

  - [ ]* 8.4 Write property tests for record/replay and manual page entry
    - **Property 26: Record/Replay generates valid selector config** — Mapped interactions → at least one strategy per action
    - **Property 27: Manual page URL validation** — Valid Facebook URLs accepted, all others rejected with error message
    - **Validates: Requirements 3.1, 15.2**

- [ ] 9. Checkpoint - Verify diagnostics, record/replay, and page management
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. UI integration — Automation Card and status display
  - [ ] 10.1 Add Auto Upload Facebook toggle to Automation Card
    - Add "Auto Upload Facebook" toggle button positioned after the existing "Auto-Upload" (YouTube) toggle
    - Wire callback to persist `autoUploadFacebook` in Music_Settings
    - Restore toggle state from settings on page load, default to false
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 10.2 Add Facebook upload status label to Music page
    - Add status label showing current state (idle, uploading, waiting for rate limit, error)
    - Subscribe to `facebook_upload_status` events from the UI bus
    - Subscribe to `facebook_upload_done` events for completion/failure notifications
    - _Requirements: 12.1, 12.2, 12.4_

  - [ ] 10.3 Add Facebook Jobs view
    - Create view displaying all upload jobs with columns: status, page name, file name, attempts, created time, error message
    - Add "Retry" button per failed job that resets status to pending and clears attempt count
    - Accessible from the Music page
    - _Requirements: 12.3, 12.5_

- [ ] 11. UI integration — Settings page
  - [ ] 11.1 Add Facebook Accounts section to Settings page
    - Add account management UI: add (label + browser profile path), remove, list accounts
    - Display session health status per account (valid, expired, unknown)
    - Show warning indicator when browser profile path does not exist on disk
    - Add "Verify Session" button that launches browser visibly for manual login
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 4.4, 4.6, 13.4_

  - [ ] 11.2 Add Facebook Pages section to Settings page
    - Add page discovery trigger button per account
    - Display discovered pages with checkboxes for active/inactive toggle
    - Add manual page URL entry field with validation feedback
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 11.3 Add Facebook Post Defaults and configuration fields to Settings page
    - Add caption template field with placeholder documentation
    - Add default hashtags field
    - Add upload mode selector (merged_reel / individual_reels)
    - Add rate limit delay field (minimum 60 seconds, default 120)
    - Add timeout settings (nav: 60s, upload: 300s, confirm: 30s)
    - Add daily upload limit field (default 10)
    - Add "Test Upload" button that triggers selector health check dry-run
    - _Requirements: 9.1, 9.4, 10.1, 10.4, 13.1, 13.2, 13.3, 13.5_

- [ ] 12. Wire coordinator into application lifecycle
  - [ ] 12.1 Integrate FacebookUploadCoordinator into MainWindow/application startup
    - Instantiate coordinator with proper host port (settings_accessor, db_cfg_accessor, logger, event_bus, defer_call, timer_factory)
    - Call `on_app_start()` during application initialization (resets toggle to false)
    - Subscribe to `auto_video_done` events to trigger `on_auto_video_done()`
    - Call `start()` / `stop()` during application lifecycle
    - _Requirements: 1.5, 5.1, 11.3, 15.3_

  - [ ] 12.2 Implement status event emission
    - Emit `facebook_upload_status` event on job status changes (uploading, waiting, error, idle)
    - Emit `facebook_upload_done` event on terminal job transitions with fields: jobUid, ok, error, pageId
    - _Requirements: 12.2, 12.4_

  - [ ]* 12.3 Write property test for status event emission
    - **Property 17: Status event emission on terminal transitions** — Completed/failed_permanent jobs emit facebook_upload_done with required fields
    - **Validates: Requirements 12.2, 12.4**

- [ ] 13. Fault isolation and browser crash recovery
  - [ ] 13.1 Implement fault isolation boundaries
    - Ensure coordinator runs in its own background thread, isolated from pipeline, YouTube, and UI threads
    - Ensure no shared locks, database connections, or file handles with other pipeline stages
    - Implement disabled state: if initialization fails, all public methods become no-ops
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ] 13.2 Implement browser crash recovery
    - Catch `BrowserClosedError` and terminated process detection
    - On crash: close context safely, mark current job as failed (transient), continue queue after retry delay
    - _Requirements: 11.5_

  - [ ]* 13.3 Write unit tests for fault isolation
    - Test unrecoverable init error → feature disabled, app continues
    - Test browser crash → job marked transient, processing continues
    - Test exception in on_auto_video_done → no propagation to caller
    - _Requirements: 11.1, 11.2, 11.5_

- [ ] 14. Checkpoint - Verify core pipeline and fault isolation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Manual Facebook Upload — ManualUploadOrchestrator and MergeChoiceDialog
  - [ ] 15.1 Implement ManualUploadOrchestrator class
    - Create `python_app/features/facebook_upload/manual_upload.py`
    - Define `ManualUploadRequest`, `ReelPrerequisiteResult`, and `ManualUploadResult` dataclasses
    - Implement `validate_prerequisites()` that checks outDir exists, at least one MP3, background image, and valid reel template
    - Implement `find_existing_reel_mp4s()` that finds `*_REEL.mp4` files > 50KB in outDir
    - Implement `should_show_merge_dialog()` returning True when reel count > 1
    - _Requirements: 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.10_

  - [ ] 15.2 Implement ManualUploadOrchestrator.execute() background thread logic
    - Implement `execute()` that spawns a daemon thread for reel generation + merge + job creation
    - Implement `_generate_reels_on_thread()` using existing `_export_reel_videos` pipeline via AutoVideoCoordinator.resolve_reel_plan
    - Implement `_merge_reels_on_thread()` using existing MergeWorker.merge with FFmpeg
    - Dispatch `on_complete` callback to UI thread via `event_bus.ui_invoke.emit()`
    - Handle errors gracefully: catch all exceptions, return ManualUploadResult with error_message
    - _Requirements: 17.5, 17.6, 17.8, 17.9, 17.14_

  - [ ] 15.3 Implement MergeChoiceDialog UI component
    - Create `MergeChoiceDialog(QDialog)` with two radio buttons: "Merge into one reel video" and "Post individual reels separately"
    - Include descriptive labels for each option explaining behavior
    - Return `selected_choice` as "merge" or "individual" on accept, or None on cancel
    - Set minimum width 400px, modal, default to "merge" selection
    - _Requirements: 17.7_

  - [ ] 15.4 Integrate manual upload into ProgressPageController context menu
    - Add "Upload Reel to Facebook" action to `_on_progress_table_context_menu()` after the YouTube actions section
    - Disable action when: no outDir set, no active Facebook pages, or role not in {"OK", "ALT"}
    - Implement `_progress_upload_reel_to_facebook(meta)` handler per design flow
    - Implement `_has_active_facebook_pages()` helper using `db_list_active_facebook_pages`
    - Implement `_get_manual_upload_orchestrator()` with lazy instantiation
    - Implement `_show_merge_choice_dialog(reel_count)` helper
    - Show informational message directing to Settings when no active pages configured
    - Show warning with missing prerequisites list when validation fails
    - Show confirmation message with job count and page names on success
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.7, 17.11, 17.12, 17.13_

  - [ ]* 15.5 Write property tests for ManualUploadOrchestrator
    - **Property 29: Reel prerequisite validation completeness** — valid=True iff all three prerequisites present; missing list accurate
    - **Property 30: Manual upload single-file job creation per page** — 1 file × N pages → N jobs
    - **Property 31: Manual upload multi-file job creation** — M files × N pages → M×N jobs
    - **Property 32: Manual upload confirmation message accuracy** — Result contains correct job count and all page names
    - **Property 33: Upload action disable conditions** — Disabled iff outDir empty OR no active pages OR role not OK/ALT
    - **Validates: Requirements 17.3, 17.4, 17.8, 17.9, 17.10, 17.11, 17.12**

- [ ] 16. Final checkpoint - Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design uses Python with Playwright, Hypothesis for PBT, and pytest as test runner
- Runtime dependencies to add: `pyyaml`, `rapidfuzz`, `beautifulsoup4`
- All Playwright browser interactions use persistent contexts from user-configured profile directories
- Requirement 17 (Manual Upload) reuses existing reel generation and merge pipelines — no duplication of complex video processing logic

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "1.4", "2.2", "2.3"] },
    { "id": 2, "tasks": ["1.5", "2.4", "4.1", "4.2", "4.3"] },
    { "id": 3, "tasks": ["4.4", "4.5", "5.1", "5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "5.5", "5.6"] },
    { "id": 5, "tasks": ["5.7", "7.1", "7.2"] },
    { "id": 6, "tasks": ["7.3", "7.4", "7.5"] },
    { "id": 7, "tasks": ["7.6", "8.1", "8.2", "8.3"] },
    { "id": 8, "tasks": ["8.4", "10.1", "10.2", "10.3"] },
    { "id": 9, "tasks": ["11.1", "11.2", "11.3"] },
    { "id": 10, "tasks": ["12.1", "12.2"] },
    { "id": 11, "tasks": ["12.3", "13.1", "13.2"] },
    { "id": 12, "tasks": ["13.3", "15.1"] },
    { "id": 13, "tasks": ["15.2", "15.3"] },
    { "id": 14, "tasks": ["15.4"] },
    { "id": 15, "tasks": ["15.5"] }
  ]
}
```
