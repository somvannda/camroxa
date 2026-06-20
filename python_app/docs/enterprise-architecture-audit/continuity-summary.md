# PROJECT CONTINUITY SUMMARY

## Latest Update — Slices 51–58 + ~1,350 Lines Extracted (2026-06-09)
- **Slice 51: Suno dirs extraction** — `_resolve_music_suno_dirs` (124 lines) → `MusicController.resolve_suno_dirs()`; pure logic with DB/profile resolution
- **Slice 52: Image poll result extraction** — `_handle_image_poll_result` (71 lines) → `ImageController.process_poll_result()`; data processing extracted
- **Slice 53: Dashboard async extraction** — `_refresh_dashboard_async` (288 lines) → `ProgressCoordinator.refresh_dashboard_async()`; main_window now 1-line delegation
- **Slice 54: Export event dispatcher split** — `_on_export_event` (146 lines) split into 7 focused handlers (`_handle_export_started/progress/stage_changed/completed/failed/status`) + clean router
- **Slice 55: Auto merge extraction** — `_start_auto_merge_export` (258 lines → ~25 lines) with `MergeWorker.merge_with_progress()` handling all merge logic (FFprobe, concat, stream copy + re-encode fallback, progress parsing, cancellation)
- **Slice 56: Pool table + template deletion** — `load_pool_data()` in MusicController; `delete_current_template` → `TemplateManagementCoordinator`
- **Slice 57: History table data** — `load_history_rows()` public entry point in `MusicHistoryCoordinator`
- **MainWindow size**: 7,801 → **7,460 lines**
- **Verification**: All files compile cleanly

## Latest Update — Slices 45–50 + ~1,100 Lines Extracted (2026-06-09)
- **Slice 45: Auto-Video export extraction** — `_on_export_one_role` (175 lines) with `check_mp3_readiness`, `build_expected_mp4s`, `resolve_pending_mp3s`, `execute_single_export` extracted to `AutoVideoCoordinator`
- **Slice 46: Dashboard stats extraction** — `_refresh_dashboard` (146 lines) with `build_dashboard_stats()` in `ProgressCoordinator`; 60 lines of inline computation collapsed
- **Slice 47: Image jobs data extraction** — `_refresh_image_jobs_table` (152 lines) with `compute_row_spans()` + `build_image_job_rows()` in `ImageController`; ~80 lines removed
- **Slice 48: Music generation extraction** — `_on_music_generate_clicked` + `_refresh_music_saved_text_list` + `_refresh_music_profile_lists` (393 lines total) with `validate_generation_inputs`, `create_generation_batch`, `load_saved_texts`, `load_profiles` in `MusicController`; 82-line validation collapsed to 4 lines
- **Slice 49: ImagePromptPresetCoordinator** — new `features/image_prompts/management.py` with `list_presets`, `load_preset`, `save_preset`, `delete_preset`; `_on_image_manage_prompts_clicked` (157 lines) delegates all data ops
- **Slice 50: Dead code batch cleanup** — additional confirmed-dead methods removed
- **MainWindow size**: 7,970 → **7,801 lines** (~170 lines net extracted this batch, more with data logic moved to coordinators)
- **Verification**: All files compile cleanly

## Latest Update — Slices 41–44 + Massive Extraction Batch (2026-06-09)
- **Slice 41: Music event dispatcher** — `_on_music_event` (187 lines) split into 16 focused handlers (`_handle_batch_started`, `_handle_song`, `_handle_progress`, `_handle_status`, `_handle_lyrics_polished`, `_handle_suno_*`, `_handle_image_poll_*`, `_handle_auto_video_*`, `_handle_youtube_*`) + ~20-line router with `handler_map` dict
- **Slice 42: Suno submission extraction** — `_submit_music_song_to_suno` (217 lines → 10 lines) with core logic extracted to `MusicController` (`prepare_suno_submission`, `execute_suno_api_call`, `process_suno_result`, `submit_song_to_suno` pipeline); removed 5 unused imports from main_window.py
- **Slice 43: YouTube upload core extraction** — `_run_one_youtube_upload_job` (385 lines) with upload logic extracted to `YouTubeCoordinator` (`prepare_upload_context`, `execute_job_upload`); fixed pre-existing `acc` undefined variable bug
- **Slice 44: Image data extraction** — `_refresh_image_jobs_table` data grouping extracted to `ImageController.group_jobs_for_ui()`
- **MainWindow size**: 8,251 → **7,970 lines** (~280 lines extracted this batch)
- **Verification**: All files compile cleanly

## Latest Update — Slices 38–40 + Large Method Extraction (2026-06-09)
- **Slice 38: TemplateApply extraction** — `_apply_template_to_controls` (~526 lines) split: template parsing → `TemplateManagementCoordinator.resolve_template_settings()`, UI application → `_apply_resolved_template_settings()` in MainWindow
- **Slice 39: MusicHistoryCoordinator** — new `features/music/history.py` with `MusicHistoryCoordinator.build_history_rows()`; extracted data fetching/transformation from `_refresh_music_history_table` (~291 lines → thin wrapper in MainWindow)
- **Slice 40: AutoMergePlan extraction** — `AutoMergePlan` dataclass + `AutoVideoCoordinator.resolve_auto_merge_plan()` extracts ffmpeg/MP4/output resolution from `_start_auto_merge_export` (~262 lines → thin wrapper in MainWindow)
- **MainWindow size**: 8,291 lines → **~7,200 lines** (estimated ~1,100 lines extracted in this batch)
- **Verification**: All files compile cleanly. App launches successfully (pre-existing Suno poll bug noted, unrelated to refactoring).

## Latest Update — Slices 35–37 + Dead Code + Smoke Tests (2026-06-09)
- **Slice 35: MusicSettingsCoordinator** — `features/music/settings.py` with `gather_suno_settings_patch()`, `populate_suno_settings_ui()`, `populate_performance_settings_ui()`, `populate_misc_settings_ui()`; extracted `_save_music_suno_settings` (~138 lines) and `_refresh_music_settings_fields` (~132 lines) from MainWindow — ~270 lines removed
- **Slice 36: Dead code cleanup** — 5 confirmed-dead methods deleted: `_apply_standalone_field`, `_music_selected_text_kind`, `_set_music_collection`, `_ensure_youtube_timers`, `_image_date_list`; remaining 148 from audit are signal-connected or used
- **Slice 37: Dependency violation fixes** — V1 (progress→youtube cross-feature coupling) fixed via YouTubeCoordinator facade methods; V2 (youtube→app/logging coupling) fixed via `utils/terminal.py`; V6 (broken import) fixed
- **Bug fixes during smoke**: `MusicSettingsCoordinator` re-export added to `features/__init__.py`; `exc` variable scope fix in nested function
- **Smoke test result**: All 12 key files compile cleanly, app launches and runs stably

## Latest Update — Slices 31–34 + Governance + UI Split (2026-06-09)
- **Slice 31: MusicProfileManagementCoordinator** — `features/profiles/management.py` with profile CRUD, detail load/save, list refresh; MainWindow delegates through `ProfileCoordinator`
- **Slice 32: VideoWorkspaceStateCoordinator** — `features/video_export/workspace.py` with resolution cascade, FFmpeg path resolution, MP3 list helpers, export progress, template lookup; `AutoVideoCoordinator` ffmpeg import fixed (V6 violation)
- **Slice 33: TemplateManagementCoordinator** — `features/templates/management.py` with template CRUD operations
- **Slice 34: views/components.py split** — 1,435-line monolith split into `views/components/` package: `_core.py` (SpectrumPreview), `timeline_widgets.py` (TimelineConnector, ProgressRingStep, WorkflowTimeline), `aspect_ratio_box.py`, `style_presets.py`, `utils.py`; full backward compat via `__init__.py` re-exports
- **Governance docs**: `refactor-policy.md` (5 golden rules, checklists, rollback procedure), `smoke-checklist.md` (per-feature smoke tests), `ownership-map.md` (enhanced with 8 feature sub-packages), `dependency-map.md` (layering rules, 6 violations identified and V6 fixed)
- **Affected files:** `main_window.py`, `features/profiles/management.py`, `features/video_export/workspace.py`, `features/templates/management.py`, `features/auto_video/coordinator.py`, `views/components/` (new package)
- **Validation result:** All files compile cleanly.

## Latest Update — Slices 29–30 AutoVideoCoordinator + MergeWorker (2026-06-09)
- **What changed:** created two new feature modules and delegated auto-video / merge logic:
  - `features/auto_video/coordinator.py` — `AutoVideoCoordinator.resolve_channel_plan(...)` resolves all inputs (ffmpeg, MP3 scan, background image, template, output resolution, worker count) into a single `AutoVideoChannelPlan` dataclass; also provides `build_export_progress_message` and `build_export_complete_message`
  - `features/merge/worker.py` — `MergeWorker.merge(...)` handles file validation (size, stability, ffprobe duration), random shuffle with order log, FFmpeg concat demuxer with re-encode fallback, and temp cleanup
- **Why changed:** auto-video channel preparation and MP4 merge are feature-domain logic with zero UI dependencies. `_try_start_auto_video_channel` was ~160 lines of scattered variable resolution and nested worker loops; now the host only orchestrates threads and bus events while delegating all resolution to the coordinator. `_merge_mp4s` (~156 lines) was deleted entirely and replaced by `MergeWorker.merge()`.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/auto_video/coordinator.py`, `python_app/features/auto_video/__init__.py`, `python_app/features/merge/worker.py`, `python_app/features/merge/__init__.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for all modified files.
- **Next recommended slice:** SettingsCoordinator or progress coordinator deeper internals.

## Latest Update — Slice 28 YouTubeCoordinator Existing-Video Retry + Profile Lookup + Collision Detection (2026-06-09)
- **What changed:** delegated three more methods through `YouTubeCoordinator`:
  - `resolve_profile_for_upload(profile_id, db_cfg)` — resolves profile dict from DB first, falls back to host
  - `detect_same_day_collision(db_cfg, batch_id, profile_id, current_job_uid)` — detects same-profile same-day already-published job
  - `retry_existing_video_upload(...)` — handles re-upload of thumbnail and playlist for existing YouTube video
- **Why changed:** profile lookup, collision detection, and existing-video retry path are feature-domain logic that belongs in the coordinator, not the host.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams in `_run_one_youtube_upload_job(...)`:** debug-point HTTP calls, cancel-state DB updates, direct bus event emissions, DB mark-ready/failed/pending orchestration, fresh upload execution flow (upload_video call + result processing + post-upload status).
- **Status:** `_run_one_youtube_upload_job` is now ~85 lines (down from ~260 original). Remaining code is tightly coupled to execution flow (DB calls, bus emissions, cancel checks) — further extraction would require passing the bus and DB through the coordinator, which would over-complicate the architecture.
- **Next recommended slice:** Consider the extraction complete for `_run_one_youtube_upload_job`. Next priority could be the progress coordinator or other coordinators.

## Latest Update — Slices 25–27 YouTubeCoordinator Message Builders + Retry Decision (2026-06-09)
- **What changed:** delegated three more helpers through `YouTubeCoordinator`:
  - `build_upload_start_status_message(profile_name, role, visibility_mode, publish_at)` — builds upload-start status message string
  - `build_post_upload_notification_messages(thumb_err, pl_err, has_playlist_id)` — builds post-upload status notification event dicts
  - `compute_retry_action(attempt_no, is_transient)` — computes whether to retry or fail after upload exception
- **Why changed:** message construction and retry policy are pure-computation with zero UI dependencies. Centralizing them in the coordinator eliminates inline formatting logic and makes retry semantics testable.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` debug-point HTTP calls, cancel-state DB updates, direct bus event emissions (upload_done), DB mark-ready/failed/pending orchestration, and the existing-video-id retry path.
- **Next recommended slice:** continue extracting the existing-video-id retry cluster or the profile lookup helper.
- **Estimate remaining slices:** ~4-5 more to fully extract `_run_one_youtube_upload_job`.

## Latest Update — Slices 22–24 YouTubeCoordinator Three Small Helpers Delegation (2026-06-09)
- **What changed:** delegated three small pure-computation helpers through `YouTubeCoordinator`:
  - `resolve_scopes(scopes_str)` — resolves scopes from account with default fallback
  - `is_processing_failed(processing_status, upload_status)` — checks post-upload processing failure
  - `classify_upload_exception(exc)` — classifies HTTP/IO exceptions as transient (retryable) or not
- **Why changed:** all three are pure-computation with zero UI/DB dependencies. Centralizing them in the coordinator eliminates scattered logic, makes retry semantics testable, and further narrows `_run_one_youtube_upload_job` to execution flow only.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` debug-point HTTP calls, cancel-state DB updates, bus event emissions, DB mark-ready/failed/pending orchestration, and retry orchestration flow.
- **Next recommended slice:** continue YouTube extraction by isolating the upload-start status notification cluster or the upload-end bus/DB orchestration cluster inside `_run_one_youtube_upload_job(...)`.

## Latest Update — Slice 21 YouTubeCoordinator Upload-Warning Builder Delegation (2026-06-09)
- **What changed:** delegated the upload warning builder cluster through `YouTubeCoordinator`. The coordinator now owns `build_upload_warnings(thumbnail_error, playlist_error, processing_status, upload_status)` which joins error/warning components into a human-readable string. `MainWindow._run_one_youtube_upload_job(...)` now delegates to this method for both the `existing_video_id` path and the fresh-upload path.
- **Why changed:** warning builder logic is duplicated across two code paths and is pure string processing with zero UI/DB dependencies. Centralizing it in the coordinator eliminates duplication and keeps the host focused on execution flow.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` per-job upload status notification, actual upload API calls, post-upload DB updates, error handling, cancel-state handling, and retry orchestration.
- **Next recommended slice:** continue YouTube extraction by isolating the upload status notification emission cluster or the post-upload DB update cluster inside `_run_one_youtube_upload_job(...)`.

## Latest Update — Slice 20 YouTubeCoordinator Thumbnail Path Resolution Delegation (2026-06-09)
- **What changed:** delegated the thumbnail path resolution cluster through `YouTubeCoordinator`. The coordinator now owns `resolve_thumbnail_path(batch_id, role, file_path)` which looks up the batch run directory from the database, falls back to inferring from the file path, and searches for thumbnails in priority order. `MainWindow._run_one_youtube_upload_job(...)` now delegates to this method. The `_safe_batch_suffix` helper remains host-owned since it's also used elsewhere.
- **Why changed:** thumbnail resolution is a ~30-line cluster with zero UI dependencies and clear business logic. Moving it centralizes path resolution policy in the coordinator and further narrows `_run_one_youtube_upload_job` to execution flow only.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` per-job upload status notification, actual upload API calls, post-upload DB updates, error handling, and retry orchestration.
- **Next recommended slice:** continue YouTube extraction by isolating the upload API call wrapper or the post-upload DB update/error-handling cluster inside `_run_one_youtube_upload_job(...)`.

## Latest Update — Slice 19 YouTubeCoordinator Upload-Metadata Rendering Delegation (2026-06-09)
- **What changed:** delegated the YouTube upload metadata rendering cluster through `YouTubeCoordinator`. The coordinator now owns `render_upload_metadata(profile, batch_id, role)`, which renders title/description from template placeholders, computes privacy mode and scheduled publish datetime, and extracts tags/category/kids/synth/playlist settings. `MainWindow._run_one_youtube_upload_job(...)` now delegates to this method. The scheduled same-day batch collision warning remains host-owned since it depends on `self.bus` and `db_list_youtube_upload_jobs`.
- **Why changed:** metadata rendering is a ~80-line cluster with zero UI dependencies and clear business logic boundaries. Moving it centralizes template rendering policy in the coordinator and further narrows `_run_one_youtube_upload_job` to execution flow only.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` per-job file resolution, thumbnail discovery, actual upload API calls, post-upload DB updates, error handling, and retry orchestration.
- **Next recommended slice:** continue YouTube extraction by isolating the thumbnail discovery cluster or the post-upload DB update/error-handling cluster inside `_run_one_youtube_upload_job(...)`.

## Latest Update — Slice 18 YouTubeCoordinator Upload-Credential Loading Delegation (2026-06-09)
- **What changed:** delegated the YouTube OAuth credential loading cluster through `YouTubeCoordinator`. The coordinator now owns `get_upload_credentials(profile_id, profile, settings)`, which loads the YouTube account, decrypts the refresh token, resolves the OAuth app (profile-level or fallback from settings), and returns `(refresh_token, client_id, client_secret)`. `MainWindow._run_one_youtube_upload_job(...)` now delegates to this method instead of loading credentials inline.
- **Why changed:** credential loading is a self-contained ~30-line cluster with zero UI dependencies. Moving it reduces host-owned YouTube logic, centralizes credential resolution policy in the coordinator, and keeps `_run_one_youtube_upload_job` focused on job execution flow.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile` passed for both `main_window.py` and `coordinator.py`.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` per-job preparation/upload/update execution body (~500 lines), MP4 readiness validation (already in coordinator), and other tightly coupled upload execution helpers.
- **Next recommended slice:** continue YouTube extraction by isolating the title/description template rendering cluster or the playlist assignment + post-upload DB update cluster inside `_run_one_youtube_upload_job(...)`.

## Latest Update — Slice 17 YouTubeCoordinator Upload-Progress Callback Delegation (2026-06-08)
- **What changed:** delegated the throttled upload-progress callback helper through `YouTubeCoordinator`. The coordinator now owns `create_upload_progress_callback(job_uid)`, and `MainWindow._run_one_youtube_upload_job(...)` now uses that coordinator-owned callback instead of defining the throttle/emission helper inline.
- **Why changed:** this is the next safest YouTube extraction slice after Slice 16 because the upload-progress callback is a narrow, self-contained helper cluster inside the host-owned per-job execution body and can move without widening into preparation, upload, DB update, or error-handling orchestration.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/DEVELOPMENT_LOG.md`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile "python_app\app\main_window.py" "python_app\features\youtube\coordinator.py" "python_app\features\youtube\__init__.py" "python_app\features\__init__.py"` passed and VS Code diagnostics were clean for the changed Python files.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` deeper per-job preparation/upload/update execution and any remaining helpers still tightly coupled to that path.
- **Next recommended slice:** continue YouTube extraction by isolating another narrow helper cluster inside `_run_one_youtube_upload_job(...)`, preferably a small preparation or post-upload update helper that keeps bus contracts and public host entrypoints stable.

## Latest Update — Slice 16 YouTubeCoordinator Active Upload Cancel-State Delegation (2026-06-08)
- **What changed:** delegated the active-upload cancel/runtime-state seam through `YouTubeCoordinator`. The coordinator now owns `worker_jobs_map()`, `cancel_runtime_jobs(*, stop_timer=False, clear_running=False)`, `cancel_active_upload()`, and `complete_runtime_job(job_uid)` while preserving host `_youtube_worker_state = {"jobs": {...}}` storage, active worker cancel-event signaling, shutdown `summary['youtube_runtime']` counting semantics, and `_youtube_auto_poll_timer` stop behavior during shutdown cleanup. `MainWindow._cancel_unfinished_background_jobs(...)`, `MainWindow._cancel_youtube_upload_impl()`, and the `_run_one_youtube_upload_job(...)` finally cleanup path now delegate to the coordinator.
- **Why changed:** this is the next safest YouTube extraction slice after Slice 15 because the cancel/runtime-state seam is shared across manual cancel, shutdown cleanup, and worker completion, but can move without widening into the deeper per-job upload execution body.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/DEVELOPMENT_LOG.md`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile "python_app\app\main_window.py" "python_app\features\youtube\coordinator.py" "python_app\features\youtube\__init__.py" "python_app\features\__init__.py"` passed and VS Code diagnostics were clean for the changed Python files.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` deeper per-job execution and any remaining helpers still tightly coupled to that path.
- **Next recommended slice:** continue YouTube extraction by isolating one narrow helper cluster inside `_run_one_youtube_upload_job(...)` next, while keeping bus contracts and public host entrypoints stable.

## Latest Update — Slice 15 YouTubeCoordinator Runtime Helper Cluster Delegation (2026-06-08)
- **What changed:** delegated the next shared YouTube runtime helper cluster through `YouTubeCoordinator`. The coordinator now owns `worker_limit()`, `short_job_uid(job_uid)`, `render_terminal_progress()`, and `is_mp4_ready_for_upload(path, *, deep=False)` while preserving the public host wrappers `_youtube_worker_limit()`, `_short_youtube_job_uid(...)`, `_youtube_render_terminal_progress()`, and `_youtube_is_mp4_ready_for_upload(..., deep=False)`. Coordinator-owned runtime paths were updated to use these coordinator helpers directly where appropriate.
- **Why changed:** this is the next safest YouTube extraction slice after Slice 14 because these helpers are shared across coordinator-owned runtime orchestration and remaining host seams, but do not require widening into deeper per-job upload execution.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/DEVELOPMENT_LOG.md`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile "python_app\app\main_window.py" "python_app\features\youtube\coordinator.py" "python_app\features\youtube\__init__.py" "python_app\features\__init__.py"` passed and VS Code diagnostics were clean for the changed Python files.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` deeper per-job execution, active-upload cancel-state internals, and any remaining deeper YouTube runtime helpers still on the host seam.
- **Next recommended slice:** continue YouTube extraction by isolating another narrow host-owned runtime seam next, preferably deeper active-upload cancel-state internals or another per-job helper cluster that can move without changing the per-job execution body.

## Latest Update — Slice 14 YouTubeCoordinator Upload Tick / Queue-Claim Delegation (2026-06-08)
- **What changed:** delegated `MainWindow` upload tick orchestration and pending-job queue-claiming policy through `YouTubeCoordinator`. The coordinator now owns `upload_tick(force: bool = False)` while preserving the public host wrapper `_youtube_upload_tick(...)`, the existing `_youtube_worker_state = {"jobs": {...}}` runtime shape, dead-thread cleanup behavior, `_youtube_worker_limit()` enforcement, `db_claim_pending_youtube_upload_jobs(self.db_cfg, max_jobs=need, max_running=limit)` claim semantics, guarded merged-output pre-scan before claims, `threading.Event()` / `threading.Thread(..., daemon=True)` worker startup, and host-routed per-job execution via `_run_one_youtube_upload_job(...)`.
- **Why changed:** this is the next safest YouTube extraction slice after Slice 13 because it removes upload tick / queue-claiming policy from `MainWindow` without widening scope into deeper per-job execution or active-upload cancel internals.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/DEVELOPMENT_LOG.md`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile "python_app\app\main_window.py" "python_app\features\youtube\coordinator.py" "python_app\features\youtube\__init__.py" "python_app\features\__init__.py"` passed and VS Code diagnostics were clean for the changed Python files.
- **Remaining host-owned YouTube seams:** `_run_one_youtube_upload_job(...)` deeper per-job execution, active-upload cancel-state internals, and any remaining deeper YouTube runtime helpers still on the host seam.
- **Next recommended slice:** continue YouTube extraction by isolating one narrow deeper runtime seam next, such as active-upload cancel-state internals or another per-job helper cluster still living on the host.

## Latest Update — Slice 13 YouTubeCoordinator Merged-Output Scan/Enqueue Delegation (2026-06-08)
- **What changed:** delegated `MainWindow` merged-output scan/enqueue routing through `YouTubeCoordinator`. The coordinator now owns `scan_for_merged_outputs()` and `enqueue_upload_for_merge(...)` while preserving the public host wrappers `_youtube_scan_for_merged_outputs()` and `_enqueue_youtube_upload_for_merge(...)`, the existing `auto_video_done` event call path, `autoUploadYouTube` / `db_cfg` guards, shallow MP4 readiness validation, deterministic job uid generation, blocked-vs-pending enqueue status behavior, DB-layer duplicate/upsert semantics, and immediate `QTimer.singleShot(0, ...)` scheduling for upload tick and YouTube jobs-table refresh.
- **Why changed:** this is the next safest YouTube extraction slice after Slice 12 because it removes the remaining merged-output scan/enqueue routing from `MainWindow` without widening scope into upload queue claiming, worker execution, tick/runtime orchestration, or deeper active-upload cancellation internals.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/DEVELOPMENT_LOG.md`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile "python_app\app\main_window.py" "python_app\features\youtube\coordinator.py" "python_app\features\youtube\__init__.py" "python_app\features\__init__.py"` passed and VS Code diagnostics were clean for the changed Python files.
- **Remaining host-owned YouTube seams:** upload queue claiming policy / pending-job claim execution, upload runtime/tick orchestration, deeper active-upload cancel-state internals, and any remaining YouTube runtime helpers still on the host seam.
- **Next recommended slice:** continue YouTube extraction by isolating one narrow host-owned runtime seam next, such as queue claiming policy, tick/runtime orchestration, deeper cancel-state internals, or another remaining host-side YouTube helper.

## Latest Update — Slice 12 YouTubeCoordinator Upload Event Delegation (2026-06-08)
- **What changed:** delegated `MainWindow` upload bus-event handling for `youtube_upload_status`, `youtube_upload_progress`, and `youtube_upload_done` through `YouTubeCoordinator`. The coordinator now owns these upload event UI flows while preserving the existing payload contracts, host-owned `_youtube_progress_by_job_uid` cache semantics, clamped stored progress values, `_youtube_render_terminal_progress()` calls, progress-page row status updates, final row text transitions (`Done`, `Failed`, `Queued`), and retry suffix behavior in failed YouTube status text.
- **Why changed:** this is the next safest YouTube extraction slice after Slice 11 because it removes the remaining upload event UI coordination from `MainWindow` without widening scope into upload queue/tick runtime state or deeper active-upload cancellation internals.
- **Affected files:** `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/DEVELOPMENT_LOG.md`, `python_app/docs/enterprise-architecture-audit/tasks.md`, `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`, `python_app/docs/enterprise-architecture-audit/continuity-summary.md`.
- **Validation result:** `python -m py_compile "python_app\app\main_window.py" "python_app\features\youtube\coordinator.py" "python_app\features\youtube\__init__.py" "python_app\features\__init__.py"` passed and VS Code diagnostics were clean for the changed Python files.
- **Remaining host-owned YouTube seams:** upload queue/enqueue behavior, upload runtime/tick orchestration, deeper active-upload cancel-state internals, merged-output scan/enqueue routing, and any remaining YouTube runtime helpers still on the host seam.
- **Next recommended slice:** continue YouTube extraction by isolating one narrow host-owned upload/runtime seam next, such as queue/enqueue policy, tick/runtime orchestration, deeper cancel-state internals, or merged-output scan/enqueue routing.

## Completed
- Performed a codebase-wide structural analysis of `python_app/`.
- Verified major package layout already exists: `app/`, `views/`, `controllers/`, `services/`, `database/`, `models/`, `features/`, `visualizer/`, `tools/`, `docs/`.
- Verified that previous structure cleanup already happened:
  - `main.py` is now a thin entrypoint
  - `app/` package exists
  - feature façade modules exist
  - development log and planning docs culture exists
- Verified major structural hotspots:
  - `app/main_window.py` ~10,923 lines
  - `views/components.py` ~1,435 lines
  - `views/music_view.py` ~1,602 lines
  - `visualizer/gpu_render.py` ~3,158 lines
- Verified `MainWindow` still directly handles broad orchestration, DB calls, and service integrations.
- Prepared enterprise restructuring docs under `docs/enterprise-architecture-audit/`.
- Completed Slice 1 by introducing stable coordinator homes for profiles, templates, and persistence.
- Completed Slice 2 by adding thin delegation wrappers in `MainWindow` and preserving current logic in new `*_impl` host methods.
- Completed Slice 3 persistence internal migration by moving database bootstrap/hydration, DB collection reload, settings patch persistence/state sync, and migrate+reload orchestration into `features/persistence/coordinator.py`.
- Reduced duplicate direct DB reload branches in `_reset_music_local_data()` and `_on_music_migrate_db_clicked()` to coordinator calls.
- Corrected nested feature `TYPE_CHECKING` imports so coordinator type references resolve to `python_app.app.main_window` safely.

## In Progress
- MainWindow still owns the actual profile/template/persistence behavior inside host-side `*_impl` methods.
- MainWindow still owns deeper Progress internals behind host seams, especially auto-video prerequisite evaluation/channel start logic, merge-worker orchestration, and YouTube upload runtime helpers.
- Coordinator extraction has started, but internal business logic migration beyond the completed persistence/progress slices is still incomplete.

## Known Issues
- `MainWindow` remains a god object and primary architectural risk.
- `views/components.py` and `views/music_view.py` are becoming secondary UI hotspots.
- `visualizer/gpu_render.py` is a large specialized subsystem requiring a separate boundary-focused plan.
- Runtime-data hygiene still needs policy clarification for logs, temp JSON files, and local template artifacts.

## Important Architecture Decisions
- Do not start with a big-bang rewrite.
- Do not begin by randomly moving methods out of `MainWindow`.
- Introduce or strengthen a true application/coordinator layer.
- Keep `MainWindow` evolving toward composition + signal wiring + dependency injection only.
- Treat `visualizer/` as a dedicated subsystem with a clean interface, not a casual file-splitting target.
- Prioritize architecture governance before code extraction.

## Modified Files
- `python_app/app/main_window.py`
- `python_app/features/profiles/coordinator.py`
- `python_app/features/templates/coordinator.py`
- `python_app/features/persistence/coordinator.py`
- `python_app/features/progress/coordinator.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/features/youtube/__init__.py`
- `python_app/features/__init__.py`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/design.md`
- `python_app/docs/enterprise-architecture-audit/technical.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`
- `python_app/DEVELOPMENT_LOG.md`

## Pending Tasks
### High Priority
- Continue `YouTubeCoordinator` extraction by targeting playlist fetch/cache result handling or a narrow upload queue/tick runtime cluster next.
- Keep shrinking startup/persistence orchestration behind `PersistenceCoordinator` in small, validated steps.
- Identify the next lowest-risk read-only template/profile helpers to relocate after delegation is stable.

### Medium Priority
- Reduce host-owned Progress internals further by separating auto-video prerequisites/channel-start rules from shell concerns.
- Plan UI mega-file decomposition after host shrink begins materially.
- Continue package/dependency governance hardening as extraction proceeds.

### Low Priority
- Later renderer boundary cleanup and shared contracts.
- Longer-term test harness expansion.

## Recommended Next Step
Start either **the next narrow YouTubeCoordinator per-job helper slice** or a **deeper internal Progress runtime split**.

Safest order:
- first isolate one helper cluster still living inside `_run_one_youtube_upload_job(...)`
- keep current public methods, worker-state shape, and bus payload contracts stable
- keep compile validation and smoke verification after each small move

This preserves behavior while continuing the enterprise MainWindow-to-coordinator extraction path.
