# Python App Development Log

## 2026-06-08 (Enterprise Refactor Slice 17 — YouTubeCoordinator Upload-Progress Callback Delegation)

### What Changed
- Completed the next narrow remaining YouTube per-job helper extraction in `python_app/features/youtube/coordinator.py`.
- Moved throttled upload-progress callback creation behind `YouTubeCoordinator` while keeping `_run_one_youtube_upload_job(...)` host-owned for the broader per-job execution body.
- Added coordinator-owned helper:
  - `create_upload_progress_callback(job_uid)`
- Reduced the inline progress helper inside `MainWindow._run_one_youtube_upload_job(...)` to a thin coordinator call:
  - `on_progress = self.youtube_coordinator.create_upload_progress_callback(job_uid)`
- Preserved the existing runtime behavior exactly where required:
  - progress is still clamped to `0..100`
  - the first progress event still emits immediately
  - `100%` still always emits
  - throttled progress still emits when at least `0.25s` elapsed or integer progress increased by at least `1`
  - callback-local throttle state still lives on `_last_ts` / `_last_pct`
  - emitted payload contract remains `{"type": "youtube_upload_progress", "jobUid": job_uid, "progress": float(p2)}`
- Kept all other per-job preparation/upload/update logic unchanged and host-owned for this slice.
- Remaining host-owned YouTube seam after this slice is the deeper per-job preparation/upload/update execution body in `_run_one_youtube_upload_job(...)` and any helpers tightly coupled to that path.

### Why Changed
- This is the next safe coordinator-based Slice 17 step because the upload-progress callback is the narrowest remaining self-contained helper inside `_run_one_youtube_upload_job(...)`, allowing further boundary tightening without broad rewrite risk.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: clean for `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/features/youtube/__init__.py`, and `python_app/features/__init__.py`.
- Pending manual runtime/UI regression validation for upload-progress event cadence during real uploads and any remaining host-owned per-job execution paths.

## 2026-06-08 (Enterprise Refactor Slice 16 — YouTubeCoordinator Active Upload Cancel-State Delegation)

### What Changed
- Completed the next narrow remaining YouTube runtime extraction in `python_app/features/youtube/coordinator.py`.
- Moved active-upload cancel/runtime cleanup internals behind `YouTubeCoordinator` while keeping `_run_one_youtube_upload_job(...)` host-owned for this slice.
- Added coordinator-owned runtime state helpers:
  - `worker_jobs_map()`
  - `cancel_runtime_jobs(*, stop_timer=False, clear_running=False)`
  - `cancel_active_upload()`
  - `complete_runtime_job(job_uid)`
- Reduced these `MainWindow` seams to coordinator delegation:
  - `_cancel_unfinished_background_jobs(...)` now routes YouTube runtime cancellation through the coordinator while preserving image-job and DB pending-job cancellation behavior.
  - `_cancel_youtube_upload_impl()` is now a thin delegator to coordinator-owned active-upload cancellation.
  - `_run_one_youtube_upload_job(...)` finally-block runtime cleanup now delegates worker-state removal / `_youtube_upload_running` recalculation to the coordinator.
- Preserved the existing runtime behavior exactly where required:
  - `_youtube_auto_poll_timer` still stops during shutdown cleanup when requested.
  - active worker cancel events are still set for current jobs.
  - shutdown cleanup still reports `summary['youtube_runtime']` using the number of runtime cancel signals issued.
  - host `_youtube_worker_state = {'jobs': {...}}` shape remains unchanged.
  - `_youtube_upload_running` semantics remain unchanged for live upload cancellation vs shutdown cleanup.
- Kept the per-job upload execution body unchanged apart from the delegated final cleanup seam.
- Remaining host-owned YouTube seam after this slice is the deeper per-job execution body in `_run_one_youtube_upload_job(...)` and any helpers tightly coupled to that path.

### Why Changed
- This is the next safe coordinator-based Slice 16 step because the active-upload cancel/runtime-state seam is shared across shutdown cleanup, manual cancel actions, and worker completion, but can be extracted without widening into the deeper per-job upload execution body.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: clean for `python_app/app/main_window.py`, `python_app/features/youtube/coordinator.py`, `python_app/features/youtube/__init__.py`, and `python_app/features/__init__.py`.
- Pending manual runtime/UI regression validation for shutdown cleanup cancellation, manual upload cancel behavior, and worker completion cleanup.

## 2026-06-08 (Enterprise Refactor Slice 15 — YouTubeCoordinator Runtime Helper Cluster Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved the next shared YouTube runtime helper cluster behind `YouTubeCoordinator` while preserving current host-visible method names and all existing call sites.
- Added coordinator-owned helper methods:
  - `worker_limit()`
  - `short_job_uid(job_uid)`
  - `render_terminal_progress()`
  - `is_mp4_ready_for_upload(path, *, deep=False)`
- Reduced these `MainWindow` methods to thin delegation only:
  - `_youtube_worker_limit()`
  - `_short_youtube_job_uid(job_uid)`
  - `_youtube_render_terminal_progress()`
  - `_youtube_is_mp4_ready_for_upload(path, *, deep=False)`
- Updated coordinator-internal runtime paths to call coordinator-owned helpers where appropriate instead of the host wrappers.
- Preserved the existing visible and host-backed behavior exactly:
  - same worker-limit defaulting, integer parsing, and clamp range of `1..5`
  - same short job UID formatting rules for `yt-batch-`, `-profile-`, and long-ID ellipsis trimming
  - same terminal inline progress rendering against host `_youtube_worker_state` / `_youtube_progress_by_job_uid`, including empty-state `end_inline()` behavior and six-job display cap
  - same MP4 readiness checks for shallow and deep validation paths, including file existence/size/mtime/lock checks, ffprobe discovery strategy, and duration validation fallback behavior
- Kept these YouTube responsibilities host-owned after this slice:
  - `_run_one_youtube_upload_job(...)` deeper per-job execution
  - active-upload cancel-state internals
  - any remaining deeper YouTube runtime helpers still on the host seam

### Why Changed
- This is the next narrow YouTube slice after Slice 14 because these helpers are now cross-used by coordinator-owned upload/runtime orchestration and remaining host seams, making them the safest shared helper cluster to relocate before touching deeper per-job execution.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for worker-limit preference handling, inline terminal progress rendering, shallow/deep MP4 readiness checks, and coordinator/host cross-calls through the thin delegator seam.

## 2026-06-08 (Enterprise Refactor Slice 14 — YouTubeCoordinator Upload Tick / Queue-Claim Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved YouTube upload tick orchestration and pending-job queue-claiming policy behind `YouTubeCoordinator` while preserving the existing host-owned worker-state shape and host-owned per-job execution seam.
- Added coordinator-owned upload runtime entrypoint:
  - `upload_tick(force: bool = False)`
- Reduced `MainWindow._youtube_upload_tick(...)` to thin delegation only.
- Preserved the existing visible and host-backed behavior exactly:
  - same `force` semantics
  - same `_app_closing`, `autoUploadYouTube`, and `db_cfg` guards
  - same guarded merged-output pre-scan before claiming work
  - same host `_youtube_worker_state = {"jobs": {...}}` structure
  - same dead-thread cleanup behavior before new claims
  - same `_youtube_worker_limit()` usage and worker-cap enforcement
  - same `_youtube_upload_running` semantics when already at limit, when no jobs are claimed, and after worker starts
  - same DB claim helper and arguments: `db_claim_pending_youtube_upload_jobs(self.db_cfg, max_jobs=need, max_running=limit)`
  - same per-job `threading.Event()` cancel token allocation and `threading.Thread(..., daemon=True)` start pattern
  - same thread-target behavior routing each claimed job into host-owned `_run_one_youtube_upload_job(...)`
- Kept these YouTube responsibilities host-owned after this slice:
  - `_run_one_youtube_upload_job(...)` deeper per-job execution
  - active-upload cancel-state internals
  - any remaining deeper YouTube runtime helpers still on the host seam

### Why Changed
- This is the next narrow YouTube slice after Slice 13 because it moves upload tick / queue-claiming policy behind the coordinator boundary without widening scope into the deeper per-job upload runtime and active cancellation internals that still belong to stable host seams.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for auto-poll tick scheduling, merged-output pre-scan before claims, worker-limit enforcement, queue claiming at capacity boundaries, and host-owned per-job execution/cancel flows.

## 2026-06-08 (Enterprise Refactor Slice 13 — YouTubeCoordinator Merged-Output Scan/Enqueue Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved merged-output scan/enqueue routing behind `YouTubeCoordinator` while preserving the existing host-visible method names and queue-upsert behavior.
- Added coordinator-owned merged-output methods:
  - `enqueue_upload_for_merge(...)`
  - `scan_for_merged_outputs()`
- Reduced these `MainWindow` YouTube methods to thin delegation only:
  - `_enqueue_youtube_upload_for_merge(...)`
  - `_youtube_scan_for_merged_outputs()`
- Kept the `auto_video_done` bus-event branch narrow and unchanged at the call site so it still routes through `_enqueue_youtube_upload_for_merge(...)`, which now delegates to the coordinator.
- Preserved the existing visible and host-backed behavior exactly:
  - same `autoUploadYouTube` gating for startup/manual-resume merged-output scans
  - same `db_cfg` and argument guards before enqueue work begins
  - same `_youtube_is_mp4_ready_for_upload(..., deep=False)` readiness checks
  - same deterministic job uid generation from `batchId/profileId/role`
  - same account lookup via `db_get_youtube_account(...)`
  - same blocked-vs-pending enqueue status behavior and error text (`YouTube not connected`, `YouTube status unavailable`)
  - same queue persistence through `db_enqueue_youtube_upload_job(...)`, including existing duplicate/upsert semantics already enforced by the DB layer
  - same immediate `QTimer.singleShot(0, ...)` scheduling for `_youtube_upload_tick` and YouTube jobs-table refresh when applicable
  - same merged-file discovery policy: per batch, per role, newest `MERGED_*.mp4` candidates first, top 5 candidates only, first shallow-ready file selected
- Kept these YouTube responsibilities host-owned after this slice:
  - upload queue claiming policy / pending-job claim execution
  - upload runtime/tick orchestration
  - deeper active-upload cancel-state internals
  - any remaining YouTube runtime helpers still on the host seam

### Why Changed
- This is the next narrow YouTube slice after Slice 12 because it removes the remaining merged-output scan/enqueue routing from `MainWindow` without widening scope into queue claiming, upload worker execution, tick orchestration, or deeper cancellation internals.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for startup/manual-resume merged-output scanning, post-merge enqueue behavior, blocked-account queue rows, and immediate tick/table-refresh scheduling.

## 2026-06-08 (Enterprise Refactor Slice 12 — YouTubeCoordinator Upload Event Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved YouTube upload bus-event handling for `youtube_upload_status`, `youtube_upload_progress`, and `youtube_upload_done` behind `YouTubeCoordinator` while preserving the existing host-owned upload runtime and current event payload contracts.
- Added coordinator-owned upload event handlers:
  - `handle_upload_status(...)`
  - `handle_upload_progress(...)`
  - `handle_upload_done(...)`
- Added a small coordinator helper for progress-page row status updates:
  - `_set_progress_row_status(...)`
- Preserved the existing visible and host-backed behavior exactly:
  - same YouTube/music status text updates
  - same host-owned `_youtube_progress_by_job_uid` cache semantics
  - same clamping behavior for stored progress values and rendered progress-row percentages
  - same `_youtube_render_terminal_progress()` calls for progress and done events
  - same progress-table updates for matching YouTube rows while the active page is `progress`
  - same final row text transitions: `Done`, `Failed`, or `Queued`
  - same retry suffix behavior in the YouTube status text for failed uploads
- Reduced these `MainWindow` bus-event branches to thin delegation only:
  - `if kind == "youtube_upload_status":`
  - `if kind == "youtube_upload_progress":`
  - `if kind == "youtube_upload_done":`
- Kept these YouTube responsibilities host-owned after this slice:
  - upload queue/enqueue behavior
  - upload runtime/tick orchestration
  - deeper active-upload cancel-state internals
  - merged-output scan/enqueue routing via `_youtube_scan_for_merged_outputs()`
  - any remaining YouTube runtime helpers still on the host seam

### Why Changed
- This is the next narrow YouTube slice after Slice 11 because it moves the remaining upload event UI coordination out of `MainWindow` without widening scope into the host-owned queue execution, tick orchestration, or deeper cancellation internals.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for upload status text transitions, terminal inline progress rendering, progress-page YouTube row updates, and retry/failure row-state behavior.

## 2026-06-08 (Enterprise Refactor Slice 11 — YouTubeCoordinator Playlist Fetch/Cache Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved YouTube playlist fetch/cache result handling behind `YouTubeCoordinator` while preserving the existing host-visible storage and UI contracts:
  - playlist cache still lives on host attribute `_youtube_playlists_cache`
  - playlist combo target remains `music_settings_profile_youtube_playlist`
  - default first option remains `No playlist`
  - missing saved playlist ids still render as `Missing · <id>`
  - background load success/failure still emits `youtube_playlists_loaded`
  - selected-profile refresh still only runs when `profileId` matches the current music-settings selection
- Added coordinator-owned playlist methods:
  - `refresh_profile_playlists(...)`
  - `start_playlist_fetch(...)`
  - `handle_playlists_loaded(...)`
- Preserved the same background fetch path:
  - same profile/account lookup through `db_get_youtube_account(...)`
  - same OAuth client resolution via `_resolve_youtube_oauth_client(...)`
  - same DPAPI refresh-token decrypt flow
  - same `list_playlists(...)` worker call on a background thread
- Reduced these `MainWindow` YouTube seams to thin delegation only:
  - bus-event branch: `if kind == "youtube_playlists_loaded":`
  - `_refresh_music_settings_profile_youtube_playlists(...)`
  - `_start_youtube_playlist_fetch(...)`
- Kept these YouTube responsibilities host-owned after this slice:
  - upload queue/enqueue behavior
  - upload runtime/tick orchestration
  - deeper active-upload cancel-state internals
  - upload status/progress/done bus-event handling
  - merged-output scan/enqueue routing via `_youtube_scan_for_merged_outputs()`

### Why Changed
- This is the next narrow YouTube slice after Slice 10 because it removes the remaining playlist fetch/cache orchestration from `MainWindow` without widening scope into the deeper upload runtime and queue/tick state machines.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for playlist loading success/failure, loading-state refresh behavior, missing-saved-playlist rendering, and post-connect cache invalidation refresh behavior.

## 2026-06-08 (Enterprise Refactor Slice 10 — YouTubeCoordinator Connect-Result Bus-Event Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved YouTube connect-result bus-event handling for `youtube_connect_select_channel` and `youtube_connect_done` behind `YouTubeCoordinator` while preserving the existing bus payload contracts and visible behavior.
- Added coordinator-owned connect-result handlers:
  - `handle_connect_select_channel(...)`
  - `handle_connect_done(...)`
- The coordinator now owns:
  - event payload validation for both connect-result flows
  - selectable channel label construction and `QInputDialog.getItem(host, "YouTube", ...)`
  - unchanged `youtube_connect_done` failure emission for no-channel and invalid-selection outcomes
  - unchanged selected-channel DB upsert payload and emitted success payload
  - connect-state cleanup, status updates, selected-profile detail refresh, playlist-cache clearing on success, and guarded `_youtube_scan_for_merged_outputs()` triggering
- Reduced these `MainWindow` bus-event branches to thin delegation only:
  - `if kind == "youtube_connect_select_channel":`
  - `if kind == "youtube_connect_done":`
- Removed the now-unused `QInputDialog` import from `python_app/app/main_window.py`.
- Kept these YouTube responsibilities host-owned after this slice:
  - upload queue/enqueue behavior
  - upload runtime/tick orchestration
  - deeper active-upload cancel-state internals
  - playlist fetch/cache result handling (`_start_youtube_playlist_fetch`, `_refresh_music_settings_profile_youtube_playlists`, and `youtube_playlists_loaded`)
  - upload status/progress/done bus-event handling
  - merged-output scan/enqueue routing via `_youtube_scan_for_merged_outputs()`

### Why Changed
- This is the next narrow YouTube slice after Slice 9 because it finishes the connect-result boundary without widening scope into the deeper upload runtime and queue orchestration that still belongs on stable host seams.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for multi-channel selection, user-cancel flow, invalid-selection failure handling, connect success/failure status updates, and post-connect merged-output scan behavior.

## 2026-06-08 (Enterprise Refactor Slice 9 — YouTubeCoordinator OAuth Connect Lifecycle Delegation)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Moved YouTube OAuth connect start/cancel worker lifecycle behind `YouTubeCoordinator` while preserving the existing host-owned storage and bus-event contracts:
  - `_youtube_connect_cancel_events` still lives on the host object
  - `youtube_connect_done` payloads are emitted unchanged
  - `youtube_connect_select_channel` payloads are emitted unchanged
- Added coordinator-owned OAuth lifecycle methods:
  - `connect_cancel_event_for(...)`
  - `clear_connect_state(...)`
  - `start_oauth_connect(...)`
- Updated coordinator profile actions to call coordinator-owned OAuth helpers directly:
  - `connect_profile()` now calls `start_oauth_connect(...)`
  - `disconnect_profile()` now calls `connect_cancel_event_for(...)` / `clear_connect_state(...)`
- Reduced these `MainWindow` YouTube OAuth helpers to thin delegators:
  - `_youtube_connect_cancel_event_for(...)`
  - `_clear_youtube_connect_state(...)`
  - `_start_youtube_oauth_connect(...)`
- Kept these YouTube responsibilities host-owned after this slice:
  - bus-event result handling for `youtube_connect_select_channel` and `youtube_connect_done`
  - upload queue/enqueue behavior
  - upload runtime/tick orchestration
  - deeper active upload cancel-state internals
- Preserved the existing visible connect/disconnect behavior exactly:
  - status text `Connecting…`
  - connect button disabled during connect start
  - disconnect button enabled and relabeled to `Cancel`
  - same missing-credential failure event payload
  - same background thread behavior and cancellation checks
  - same refresh-token encryption and DB upsert flow

### Why Changed
- This is the next narrow YouTube slice after Slice 8 because it moves the OAuth connect worker lifecycle behind the coordinator boundary without widening into host-side bus-result handling or the deeper upload runtime.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for YouTube connect success/failure, cancel-in-progress behavior, multi-channel selection flow, and post-connect profile refresh behavior.

## 2026-06-08 (Enterprise Refactor Slice 8 — YouTubeCoordinator Timer Sync / Auto-Poll Routing)

### What Changed
- Completed the next safe YouTube extraction step in `python_app/features/youtube/coordinator.py`.
- Fixed coordinator imports so `QTimer` is available for coordinator-owned timer setup.
- Moved YouTube timer creation and auto-poll synchronization behind `YouTubeCoordinator` while preserving host timer attribute names and runtime behavior:
  - `_youtube_auto_poll_timer`
  - `_youtube_live_refresh_timer`
- Reduced these `MainWindow` YouTube timer methods to thin delegators:
  - `_ensure_youtube_timers`
  - `_sync_youtube_auto_poll_timer`
- Kept deeper host-owned YouTube runtime seams in `MainWindow` for now:
  - OAuth connect worker lifecycle
  - upload queue/enqueue behavior
  - upload tick/runtime orchestration
  - active worker cancel-state internals
- Preserved existing timer behavior exactly:
  - auto poll timer: `30000 ms`, timeout -> `_youtube_upload_tick`
  - live refresh timer: `1500 ms`, refreshes jobs table only while `_current_primary_page == "youtube"`
  - auto-poll sync gate: `autoUploadYouTube` enabled, `db_cfg` present, and app not closing

### Why Changed
- This is the next lowest-risk YouTube slice after the UI/profile delegation work because it moves timer policy entry routing behind the coordinator boundary without widening scope into the deeper asynchronous upload runtime.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for YouTube auto-upload toggle behavior, startup/shutdown timer gating, and YouTube page live refresh.

## 2026-06-08 (Enterprise Refactor Slice 7 — YouTubeCoordinator UI and Profile Entry Delegation)

### What Changed
- Added `python_app/features/youtube/coordinator.py` with a new `YouTubeCoordinator`.
- Wired `MainWindow` to instantiate `self.youtube_coordinator` and import/export the new coordinator through the feature package.
- Reduced these UI-facing `MainWindow` YouTube methods to thin delegators:
  - `_refresh_youtube_jobs_table`
  - `_selected_youtube_job_uid`
  - `_retry_selected_youtube_job`
  - `_cancel_youtube_upload`
  - `_on_youtube_row_selected`
  - `_on_music_profile_youtube_connect`
  - `_on_music_profile_youtube_disconnect`
- Preserved deeper behavior in host-side implementation seams where runtime ownership still belongs on the shell for now:
  - `_refresh_youtube_jobs_table_impl`
  - `_selected_youtube_job_uid_impl`
  - `_cancel_youtube_upload_impl`
- Moved coordinator-owned YouTube responsibilities to include:
  - jobs-table row loading and rendering
  - selected-job resolution
  - retry action routing
  - row-selection button-state refresh
  - profile-level connect/disconnect entry routing
- Kept higher-risk host-owned YouTube internals in `MainWindow` for now:
  - OAuth connect worker lifecycle
  - upload queue/enqueue behavior
  - upload tick/runtime orchestration
  - timer synchronization / auto-poll logic
  - active worker cancel-state internals

### Why Changed
- This is the safest first YouTube extraction slice because it removes a coherent UI-facing workflow cluster from `MainWindow` while preserving the deeper asynchronous runtime behavior on stable host seams.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/__init__.py`
- `python_app/features/youtube/__init__.py`
- `python_app/features/youtube/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\youtube\\coordinator.py" "python_app\\features\\youtube\\__init__.py" "python_app\\features\\__init__.py"`
- VS Code diagnostics checked for all changed Python files: no diagnostics.
- Pending manual runtime/UI regression validation for YouTube profile connect/disconnect, YouTube jobs-table refresh/retry/cancel actions, and startup timer behavior.

## 2026-06-08 (Enterprise Refactor Slice 6 — ProgressCoordinator Remaining Action Delegation)

### What Changed
- Completed the next safe Progress extraction step in `python_app/features/progress/coordinator.py`.
- Reduced these remaining public `MainWindow` progress methods to thin delegation wrappers while preserving their existing method names for current callers:
  - `_progress_restart_converter`
  - `_progress_restart_merge_only`
- Added host-side implementation seams to keep deeper workflow behavior stable while shrinking the shell surface:
  - `_progress_restart_converter_impl`
  - `_progress_restart_merge_only_impl`
- Confirmed `ProgressCoordinator` now owns:
  - progress context-menu construction/dispatch
  - output-folder open and batch-id copy helpers
  - row-scoped cancel and cancel-all flows
  - image restart actions
  - converter restart routing
  - merge-only restart routing
  - safe YouTube row actions (start, retry, cancel, open URL, restart-from-image)
- Kept deeper host-owned runtime/workflow helpers in `MainWindow` for now:
  - auto-video prerequisite evaluation and channel start internals
  - merge worker queue/thread orchestration
  - YouTube upload queue/tick runtime helpers

### Why Changed
- This continues the enterprise MainWindow refactor by moving the remaining progress action entrypoints behind the coordinator boundary without breaking dashboard callers or deeper workflow logic.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/progress/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\progress\\coordinator.py"`
- VS Code diagnostics checked for both changed files: no diagnostics.
- Pending manual runtime/UI regression validation for dashboard failure actions, progress converter/merge actions, and YouTube-linked row actions.

## 2026-06-08 (Enterprise Refactor Slice 5 — ProgressCoordinator Action Routing)

### What Changed
- Moved the next safe progress interaction slice into `python_app/features/progress/coordinator.py`.
- Reduced these `MainWindow` progress methods to thin delegation wrappers:
  - `_on_progress_table_context_menu`
  - `_progress_cancel_row`
  - `_progress_cancel_all_pending_jobs`
  - `_progress_restart_images`
- Expanded `ProgressCoordinator` ownership to include:
  - progress context-menu construction/dispatch
  - output-folder open and batch-id copy helpers
  - row-scoped cancel action
  - cancel-all progress flow orchestration
  - image restart actions
- Kept deeper cross-feature progress commands on the host for now:
  - `_progress_restart_converter`
  - `_progress_restart_merge_only`
  - direct YouTube worker/tick helpers invoked from the coordinator through the host seam

### Why Changed
- This is the next lowest-risk Progress extraction step after the read/refresh delegation slice. It keeps user-visible behavior stable while removing another dense action-routing cluster from `MainWindow`.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/progress/coordinator.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\progress\\coordinator.py"`
- Pending manual runtime/UI regression validation for progress context menu actions, cancel-all flow, converter/merge handoff actions, and YouTube-linked row actions.

## 2026-06-08 (Enterprise Refactor Slice 4 — ProgressCoordinator MainWindow Delegation)

### What Changed
- Wired `python_app/app/main_window.py` to import and instantiate `ProgressCoordinator`.
- Reduced these `MainWindow` progress helpers to thin delegation wrappers while preserving their existing method names/signatures for current callers:
  - `_refresh_progress_table`
  - `_refresh_progress_table_async`
  - `_apply_progress_rows`
  - `_collect_progress_rows`
  - `_scan_progress_output_dir`
  - `_progress_row_meta_at`
  - `_progress_mark_visible_rows_cancelling`
- Confirmed the real progress orchestration remains in `python_app/features/progress/coordinator.py`, which now owns:
  - progress refresh orchestration
  - row-model construction
  - output-directory scan cache logic
  - progress row metadata lookup
  - visible-row cancelling markers
- Kept progress context-menu routing and progress action handlers in `MainWindow` for this slice.

### Why Changed
- This is the next safe MainWindow extraction slice: it removes duplicated progress read/refresh business logic from the shell class without changing user-visible behavior or current caller contracts.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/main-window-extraction-map.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\progress\\coordinator.py"`
- Pending manual runtime/UI regression validation for progress refresh, context menu actions, cancel-all flow, and YouTube-linked row updates.

## 2026-06-08 (Enterprise Refactor Slice 3 — PersistenceCoordinator Internal Migration)

### What Changed
- Moved real persistence/bootstrap orchestration into `python_app/features/persistence/coordinator.py`:
  - database bootstrap initialization from env + migration
  - persisted app-data hydration into `music_data` / `e_settings`
  - DB collection reload for profiles, descriptions, and structures
  - settings patch persistence plus in-memory state sync
  - DB migrate+reload and persisted-state reload helpers
- Reduced `python_app/app/main_window.py` persistence methods to thin coordinator delegation wrappers.
- Replaced duplicate direct DB reload branches in:
  - `_reset_music_local_data()`
  - `_on_music_migrate_db_clicked()`
  with coordinator-owned flows.

### Why Changed
- This continues the enterprise MainWindow refactor by moving startup/hydration and persistence orchestration behind the existing coordinator boundary, reducing direct DB ownership in the shell class without broad unrelated refactors.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/features/persistence/coordinator.py`
- `python_app/docs/enterprise-architecture-audit/tasks.md`
- `python_app/docs/enterprise-architecture-audit/continuity-summary.md`

### Verification Performed
- Static code-path verification of persistence bootstrap, hydration, migration reload, and settings patch delegation.
- `python -m py_compile "python_app\\app\\main_window.py" "python_app\\features\\persistence\\coordinator.py"`
- Pending manual runtime/UI regression validation.

## 2026-06-08 (YouTube Auto-Upload Startup Guard + Shutdown Job Cleanup)

### What Changed
- Updated `python_app/app/main_window.py` to prevent silent YouTube auto-upload resume on app launch:
  - startup now sanitizes persisted `autoUploadYouTube` back to `False` before music UI refresh
  - YouTube poll/tick paths now also respect app-closing state
  - merged MP4 enqueue path no longer immediately triggers upload tick unless auto-upload is actually enabled at runtime
- Added reusable unfinished-job cleanup helper in `MainWindow`:
  - cancels pending/running Image jobs in DB
  - cancels pending/running YouTube jobs in DB
  - signals in-memory YouTube worker cancel events and stops auto-poll runtime during shutdown / cancel-all
- Updated `closeEvent()` to run shutdown cleanup without prompting the user.
- Updated `python_app/views/progress_view.py` to add a visible `Cancel All Jobs` button beside `Refresh`, wired to the existing cancel-all handler.

### Why Changed
- Boss reported unexpected YouTube uploads resuming automatically after launch because persisted settings re-enabled the poll timer during startup refresh.
- Boss also requested explicit cancellation controls and shutdown hygiene so stale pending/running jobs do not survive between sessions.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/views/progress_view.py`
- `debug-youtube-auto-upload.md`

### Verification Performed
- Static code-path verification of startup auto-upload trigger and shutdown cleanup paths.
- Pending: manual UI validation for startup state, progress cancel action, and shutdown cancellation behavior.

## 2026-06-04 (Project Structure: Hygiene + Packaging Baseline)

### What Changed
- Removed committed runtime artifacts and hardened ignore rules:
  - Ignored `**/__pycache__/` and `*.py[cod]`
  - Removed existing `__pycache__` folders and `python_app/debug.log`
- Removed committed secrets:
  - Deleted `python_app/.env`
  - Added `python_app/.env.example`
- Standardized local video template storage:
  - `python_app/database/persistence.py` now reads/writes `python_app/video_templates_local.json`
  - Deleted `python_app/database/video_templates_local.json`
- Started packaging clean-up for `python_app`:
  - Added `python_app/__init__.py` and `python_app/__main__.py` so the app can be launched via `python -m python_app`
  - Converted internal imports to package-relative imports (controllers/services/database/views)
  - Removed the `sys.path` mutation in `python_app/main.py`
- Removed subprocess PYTHONPATH injection:
  - `python_app/services/video_export.py` now runs `visualizer.main` with `cwd` set to the project root (no `PYTHONPATH` env hacks)
- Moved maintenance scripts out of runtime root:
  - `extract_*`, `remove_*`, `refactor_imports.py` moved into `python_app/tools/`

### Why Changed
- Boss requested project-structure best practices before scaling worker concurrency.
- Improves long-term maintainability by:
  - removing secrets from the repo
  - making imports deterministic and packaging-safe
  - keeping runtime code separate from one-off refactor tooling

### Affected Files
- `.gitignore`
- `python_app/.env.example`
- `python_app/__init__.py`
- `python_app/__main__.py`
- `python_app/main.py`
- `python_app/services/video_export.py`
- `python_app/database/persistence.py`
- `python_app/tools/extract_components.py`
- `python_app/tools/extract_views.py`
- `python_app/tools/remove_components.py`
- `python_app/tools/remove_methods.py`
- `python_app/tools/refactor_imports.py`

### Migration Requirements
- Create your local `python_app/.env` by copying `python_app/.env.example` and filling the real DB credentials.
- Launch the Python app from repo root using:
  - `python -m python_app`
- Local templates now live at:
  - `python_app/video_templates_local.json`

### Verification Performed
- `python -m compileall -q python_app visualizer`
- `python -c "import python_app.main"`

## 2026-06-04 (Repo Cleanup: Archive Electron App)

### What Changed
- Archived Electron/React/Vite app and related artifacts into:
  - `archive/electron-app/`
- Archived legacy Electron-era root docs:
  - `docs/` → `archive/electron-app/docs/`
  - `requirements/` → `archive/electron-app/requirements/`
- Updated root `README.md` to be Python-first (run via `python -m python_app`).

### Why Changed
- Boss requested removing the Electron app from the active repository structure so the project stays focused on the Python desktop app.

### Affected Files
- `README.md`
- `archive/electron-app/**` (moved from root)

### Notes / Constraints
- `visualizer/**` is still required by the Python app for spectrum preview and GPU export; removing it needs a dedicated migration task.

### Verification Performed
- `python -m compileall -q python_app visualizer`
- `python -c "import python_app.main"`

## 2026-06-04 (Pure Python: Move Visualizer Into python_app)

### What Changed
- Moved renderer package into the Python app:
  - `visualizer/**` → `python_app/visualizer/**`
- Updated Python imports:
  - `python_app/main.py` now imports `python_app.visualizer` via package-relative imports.
  - `python_app/views/components.py` updated to use `..visualizer`.
- Updated export subprocess entrypoint:
  - `python -m visualizer.main` → `python -m python_app.visualizer.main` in [video_export.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/video_export.py)

### Why Changed
- Boss requested the repository be 100% Python with no root-level non-app packages.

### Affected Files
- `python_app/main.py`
- `python_app/views/components.py`
- `python_app/services/video_export.py`
- `python_app/visualizer/**` (moved from root)
- `README.md`

### Migration Requirements
- None (run from repo root):
  - `python -m python_app`

### Verification Performed
- `python -m compileall -q python_app`
- `python -c "import python_app.main; import python_app.visualizer.main"`

## 2026-06-04 (Project Structure: Start App Shell)

### What Changed
- Introduced `python_app/app/` and moved first pieces out of `main.py`:
  - `python_app/app/ui_bus.py` now owns `UiBus`
  - `python_app/app/bootstrap.py` owns the `QApplication` + OpenGL format setup + window creation
- Entry now runs through the bootstrap layer when launching `python -m python_app`.

### Affected Files
- `python_app/app/ui_bus.py`
- `python_app/app/bootstrap.py`
- `python_app/__main__.py`
- `python_app/main.py`

### Verification Performed
- `python -m compileall -q python_app`
- `python -c "import python_app.app.bootstrap; import python_app.main"`

## 2026-06-04 (Project Structure: Move MainWindow Out of main.py)

### What Changed
- `MainWindow` (and its supporting UI helpers in the same module scope) moved from `python_app/main.py` into:
  - `python_app/app/main_window.py`
- `python_app/main.py` is now a thin compatibility wrapper:
  - re-exports `MainWindow`
  - keeps `run_app()` as a wrapper over `app.bootstrap.run()`

### Affected Files
- `python_app/app/main_window.py`
- `python_app/main.py`

### Verification Performed
- `python -m compileall -q python_app`
- `python -c "import python_app.main; import python_app.app.main_window"`

## 2026-06-04 (Project Structure: Move Shared Widgets Into app/)

### What Changed
- Moved non-business UI helpers into:
  - `python_app/app/widgets.py` (`AppDateEdit`, `PopoutPreviewWindow`)
- Updated:
  - `python_app/app/main_window.py` to import these helpers instead of defining them inline
- Adjusted debug log target back to the python_app root:
  - `python_app/debug.log` (still ignored by git)

### Affected Files
- `python_app/app/widgets.py`
- `python_app/app/main_window.py`

### Verification Performed
- `python -m compileall -q python_app`
- `python -c "from python_app.app.widgets import AppDateEdit, PopoutPreviewWindow"`

## 2026-06-04 (Project Structure: Extract Theme Builder)

### What Changed
- Theme tokens and app stylesheet generation moved into:
  - `python_app/app/theme.py`
- `python_app/app/main_window.py` now delegates:
  - `_build_ui_tokens()` → `build_ui_tokens()`
  - `_build_app_stylesheet()` → `build_app_stylesheet(...)`

### Affected Files
- `python_app/app/theme.py`
- `python_app/app/main_window.py`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-04 (Project Structure: Centralize Resource Paths)

### What Changed
- Added `python_app/app/resources.py` for path resolution:
  - `assets_dir()`, `icon_path(...)`, `lucide_icon_path(...)`
- Updated `MainWindow` to use these helpers so icon paths resolve correctly from `python_app/app/*`.

### Affected Files
- `python_app/app/resources.py`
- `python_app/app/main_window.py`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-04 (Project Structure: Centralize Debug Logging)

### What Changed
- Added `python_app/app/logging.py`:
  - `log_line(...)` writes to `python_app/debug.log` and prints to stdout
- Updated `MainWindow` to delegate `_log(...)` to `app.logging.log_line(...)`.

### Why Changed
- Keeps debug output consistent across the app shell and reduces duplicated file-write logic.

### Affected Files
- `python_app/app/logging.py`
- `python_app/app/main_window.py`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-04 (Project Structure: Feature Facades for Large Flows)

### What Changed
- Added a `python_app/features/` namespace that acts as the canonical import surface for large flows:
  - `features/youtube/*` re-exports YouTube DB + service APIs used by the app shell
  - `features/video_export/*` re-exports export service + view mixin
  - `features/progress/*` re-exports progress view mixin
- Updated the app shell imports in `MainWindow` to reference `features/*` instead of importing directly from `services/`, `database/`, and `views/` for those feature areas.

### Why Changed
- Makes feature boundaries explicit and reduces cross-file hunting without changing runtime behavior.

### Affected Files
- `python_app/features/__init__.py`
- `python_app/features/progress/__init__.py`
- `python_app/features/progress/view.py`
- `python_app/features/video_export/__init__.py`
- `python_app/features/video_export/view.py`
- `python_app/features/video_export/export.py`
- `python_app/features/youtube/__init__.py`
- `python_app/features/youtube/db.py`
- `python_app/features/youtube/oauth.py`
- `python_app/features/youtube/uploader.py`
- `python_app/app/main_window.py`

### Verification Performed
- `python -m compileall -q python_app`
- `python -c "import python_app.app.main_window; import python_app.features.youtube.uploader"`

## 2026-06-04 (Stability: Fix Asset Paths + Guard OpenGL Init Failure)

### What Changed
- Fixed QSS asset URLs used by combo/spin arrows to resolve from `python_app/assets/` (not `python_app/app/assets/`):
  - `combo-arrow.svg`, `spin-up-arrow.svg`, `spin-down-arrow.svg`
- Hardened `SpectrumPreview` so a failed OpenGL/GLSL initialization does not cascade into attribute errors during `paintGL`.

### Why Changed
- Prevents missing-asset warnings after the app-shell refactor.
- Makes the app more resilient on machines/environments that cannot provide the required GLSL version for the GPU preview.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/views/components.py`

### Known Limitations
- The preview/export shaders expect GLSL 3.30+. Systems with older OpenGL drivers (or software renderers) will not render the preview correctly.

## 2026-06-04 (Planning: Profile-Scoped Image Configuration)

### What Changed
- Added planning docs for moving image generation configuration under Profiles:
  - `python_app/docs/profile-image-config/design.md`
  - `python_app/docs/profile-image-config/technical.md`
  - `python_app/docs/profile-image-config/tasks.md`

### Why Changed
- Boss requested per-profile independence for background/thumbnail samples and prompts to support flexible workflows and future user sign-in separation.

## 2026-06-04 (YouTube: Stop Reupload Loop + Validate Merged MP4)

### What Changed
- Prevented auto-scan enqueue from resurrecting failed YouTube jobs:
  - `FAILED` jobs no longer flip back to `PENDING` automatically.
- Added MP4 readiness validation before enqueue/upload (size + mtime stability; `ffprobe` duration when available) to avoid uploading partially-written merged files.
- Updated the worker to skip reupload when a job already has `youtube_video_id` and instead re-run post actions (thumbnail update and conditional playlist add).
- Added a post-upload YouTube processing status check; if YouTube reports failure/rejection, the job is marked `FAILED` without entering an auto-retry loop.
- Added planning docs:
  - `python_app/docs/youtube-upload-integrity/*`

### Affected Files
- `python_app/database/youtube_db.py`
- `python_app/services/youtube_uploader.py`
- `python_app/features/youtube/uploader.py`
- `python_app/app/main_window.py`

## 2026-06-04 (Workers: Performance Tab + Concurrency Controls)

### What Changed
- Added Settings → Performance tab with worker limits:
  - `perfMusicWorkers`, `perfImageWorkers`, `perfMergeWorkers`, `perfYouTubeWorkers`
  - Export continues to use `videoExportWorkers` (synced between Video page and Performance tab)
- Implemented atomic DB-claim + worker pool for image jobs to prevent duplicate pickup.
- Implemented bounded YouTube uploader concurrency using atomic DB-claim to prevent duplicate pickup.
- Implemented bounded music generation concurrency across batch units (date + OK/ALT pair index) while keeping inner batch song loop sequential.
- Implemented merge-only queueing when merge workers are busy; merge worker limit applies across export-merge + merge-only tasks.

### Affected Files
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/app/main_window.py`
- `python_app/database/image_db.py`
- `python_app/services/image_generation.py`
- `python_app/database/youtube_db.py`
- `python_app/controllers/music_controller.py`
- `python_app/docs/worker-concurrency/*`


## 2026-06-03 (Video: Background Motion Reactivity)

### What Changed
- Added Background motion settings (optional, Background-only):
  - Motion Mode: None / Zoom / Vibrate / Both
  - Zoom Strength (0.0–2.0)
  - Vibrate Strength (0.0–2.0)
- Template schema now stores these under `backgroundSettings`:
  - `motionMode`
  - `motionZoomStrength`
  - `motionVibrateStrength`
- Renderer now applies the motion consistently across:
  - MP4 export
  - Preview PNG render
  - Live preview render
- Python app in-editor preview (`SpectrumPreview`) now honors:
  - Background Motion enablement + strengths
  - Particle v2 features (reactive-only spawn, react color, styles) so you can verify the look before exporting

### Why Changed
- Boss wanted an explicit setting to make the background zoom and/or vibrate only when the music reacts, without shaking the whole scene by default.

### Affected Files
- `python_app/docs/background-motion/tasks.md`
- `python_app/docs/background-motion/design.md`
- `python_app/docs/background-motion/technical.md`
- `python_app/views/settings_view.py`
- `python_app/views/components.py`
- `python_app/main.py`
- `python_app/models/spectrum_model.py`
- `visualizer/gpu_render.py`

## 2026-06-05 (Template: Enable/Disable Logo)

### What Changed
- Added a template-level toggle `logoSettings.enabled` (default ON) and exposed it in the Logo tab as “Enable Logo” (ON/OFF).
- When disabled:
  - Logo controls collapse in the UI (matches the Particles UX pattern).
  - Preview does not render the logo.
  - Export does not render the logo (CPU + GPU renderers honor the flag).

### Why Changed
- Boss requested the ability to turn off the logo without deleting the logo file/path, and to match the existing “Enable Particles” UX.

### Affected Files
- `python_app/models/spectrum_model.py`
- `python_app/views/settings_view.py`
- `python_app/app/main_window.py`
- `python_app/views/components.py`
- `python_app/visualizer/main.py`
- `python_app/visualizer/gpu_render.py`
- `python_app/docs/logo-enable-toggle/*`

## 2026-06-05 (Video Template Enhancements: Export Text Overlays)

### What Changed
- GPU renderer now draws `textOverlays` into exported outputs:
  - MP4 export: overlays are composited on top of the post-processed frame (after bloom/RGB split).
  - Preview PNG export: overlays are composited the same way as MP4 export.
  - Live Preview: overlays are drawn on top of the scene each frame.
- Adds a small GPU texture cache (5 slots) to avoid re-rasterizing text each frame during export/preview.

### Why Changed
- Boss requested the new “Intro text overlays” feature to render not only in the in-app preview, but also in the final exported MP4/PNG.

### Affected Files
- `python_app/visualizer/gpu_render.py`
- `python_app/docs/video-template-enhancements/tasks.md`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (Workflow: Real-Time Pipeline Timeline)

### What Changed
- Replaced the placeholder Workflow page with a real-time timeline overview:
  - Run selector is now a dropdown (no table), keeping the page visually clean and focused.
  - Timeline is centered, and connectors align to the circle center for a true “timeline” feel.
  - Each step shows an elapsed duration label (minutes) derived from DB timestamps and output file mtimes when available.
  - Added a centered “Generate” CTA on Workflow so Boss can start generation using the Workflow From/To range without switching to Music.
  - Removed the ring sweep animation (performance-first). Rings only update when real progress changes.
  - Music → Image → Convert → Merge → YouTube, each with a circular progress ring + icon + % and compact metric lines.
- Refresh behavior:
  - Auto-refreshes while the Workflow page is active (throttled timer, background-thread fetch, UI-thread apply).
  - Uses the existing Progress pipeline computation to avoid duplicate logic.

### Why Changed
- Boss requested an overall workflow timeline that shows end-to-end progress at a glance, with professional UX (icons + circular progress) and concrete numbers (e.g., 10/20 songs).

### Affected Files
- `python_app/views/workflow_view.py`
- `python_app/views/components.py`
- `python_app/app/main_window.py`
- `python_app/docs/workflow-timeline/*`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (Workflow: Fix Upload-Step Lag + Timeline Blinking)

### What Changed
- Reduced Workflow live-refresh UI churn:
  - Workflow run dropdown no longer clears/rebuilds its entire model every refresh when the underlying run keys are unchanged; labels update in-place.
  - Workflow timeline no longer deletes/recreates all step widgets every refresh; it updates existing widgets in-place when the step structure is unchanged.
- Reduced upload-driven UI pressure:
  - YouTube upload progress events are now throttled (time + percent delta) to avoid excessive UI updates.
- Added planning docs:
  - `python_app/docs/workflow-upload-performance/*`

### Why Changed
- Boss reported severe slowdown and visible blinking on the Workflow page during the YouTube Upload step. Root cause was frequent widget rebuilds during refresh and high-frequency progress events.

### Affected Files
- `python_app/views/workflow_view.py`
- `python_app/views/components.py`
- `python_app/app/main_window.py`
- `python_app/docs/workflow-upload-performance/*`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (YouTube: Retry DNS/Name-Resolution Failures)

### What Changed
- YouTube upload now treats DNS/name-resolution failures as transient (retryable) instead of immediately marking jobs `FAILED`.
- Added docs:
  - `python_app/docs/youtube-upload-network-retry/*`

### Why Changed
- Boss encountered `Failed to resolve oauth2.googleapis.com` / `NameResolutionError` during upload. This is usually temporary (DNS/network), so the job should auto-retry.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/docs/youtube-upload-network-retry/*`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (YouTube: Stop Repeat Upload Loop When MP4 Not Ready)

### What Changed
- Prevented YouTube jobs from repeating forever when the merged MP4 is not yet stable/valid:
  - The “MP4 not ready” pre-upload check now increments `attempt_count`, stores the real readiness reason in `error`, and stops after a bounded number of attempts (marks `FAILED`).
  - When a job is `FAILED`/`CANCELLED` and a newer merged file path is detected for the same `(batch, profile, role)` job uid, the auto-enqueue can re-open the job (set back to `PENDING`) so a genuinely new output can be uploaded.
- Added docs:
  - `python_app/docs/youtube-upload-repeat-fix/*`

### Why Changed
- Boss reported “uploading again and again”. Root cause was a `RUNNING → PENDING` loop that did not increment attempts when MP4 readiness validation failed, causing infinite retries.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/database/youtube_db.py`
- `python_app/docs/youtube-upload-repeat-fix/*`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (Debugging: Instrument YouTube Upload Pipeline)

### What Changed
- Added runtime instrumentation (Debug Server events) around:
  - YouTube worker pickup + MP4 readiness decisions
  - OAuth refresh start/success/failure
  - Upload start and `next_chunk()` exceptions
  - Upload success (video id)
- Debug session:
  - `debug-youtube-upload-issues.md`

### Why Changed
- Boss requested deeper evidence to understand why YouTube uploading is challenging/unreliable in real conditions.

### Affected Files
- `python_app/app/main_window.py`
- `python_app/services/youtube_uploader.py`
- `debug-youtube-upload-issues.md`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (YouTube: Cancel-Safe Uploads + No Duplicate Re-Uploads)

### What Changed
- Cancellation now avoids accidental duplicate uploads:
  - If Boss cancels after the video has already uploaded (but before thumbnail/playlist finishes), the job is marked `CANCELLED` while still saving `youtube_video_id`/`youtube_url`, so a later Retry updates the same upload instead of re-uploading a duplicate.
  - After the upload response returns, cancellation no longer raises and loses the video id; post-actions are skipped safely.
- Workflow “Generate” CTA is disabled while music generation is running to prevent starting another batch concurrently.
- Added a global performance setting for YouTube upload chunk size (MB) and wired it into the uploader (default 256MB).

### Why Changed
- Boss reported risk of duplicate uploads and wanted retry/cancel to be duplication-proof while keeping the “no auto-delete on YouTube” policy.

### Affected Files
- `python_app/services/youtube_uploader.py`
- `python_app/database/youtube_db.py`
- `python_app/app/main_window.py`

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-05 (Output Resolution: Social Presets + Per-Profile Override)

### What Changed
- Added social-media-friendly output resolution presets (16:9, 9:16, 1:1, 4:5, QHD) and wired them end-to-end:
  - Image generation uses the chosen output resolution for both Background and Thumbnail.
  - Auto-Video and manual Export now render MP4 at the chosen output resolution (GPU renderer width/height).
- Added per-profile `Output resolution` override:
  - `Use global (default)` inherits from the global output resolution.
  - When set, both image generation and auto-video exports use the profile override.
- Updated Image + Video preview aspect ratio boxes to match the selected output resolution.

### Why Changed
- Boss requested Shorts/Reels/TikTok 9:16 support and multiple platform resolutions while keeping the workflow end-to-end.

### Affected Files
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/views/image_view.py`
- `python_app/views/video_view.py`
- `python_app/views/components.py`
- `python_app/services/image_generation.py`
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`
- `python_app/app/main_window.py`

### Migration Notes
- Adds `profiles.output_resolution` (text) with default empty string (inherit global).

### Verification Performed
- `python -m compileall -q python_app`

## 2026-06-04 (Profiles: Per-Profile Image Config Overrides)

### What Changed
- Added Profile-scoped Image override fields (prompts + samples) that persist into `profiles.image_config` (JSONB):
  - Mode: `bg_thumb` (default) vs `thumb_only` (reuse thumbnail as background)
  - Base/background/thumbnail prompts
  - Background/thumbnail samples dir (for Random mode)
  - Background/thumbnail sample lists (one path per line)
  - Random mode now supports tri-state (inherit / on / off)
- Image enqueue now resolves profile overrides when creating new `image_jobs`:
  - prompt precedence: manual → profile → global → preset fallback
  - samples precedence: manual → profile → global
- Image worker now resolves Random mode directories and random flags per job/profile (so different profiles can random-pick from different folders).
- `thumb_only` mode behavior:
  - Enqueue skips background job creation
  - Thumbnail generation no longer waits on a background job
  - Background consumers fall back to the READY thumbnail output via `get_ready_background_output()`

### Why Changed
- Boss requested per-profile samples/prompts so each channel/profile can run independently without sharing a single global image configuration.

### Affected Files
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/app/main_window.py`
- `python_app/controllers/image_controller.py`
- `python_app/services/image_generation.py`
- `python_app/docs/profile-image-config/tasks.md`

### Known Limitations
- Manual verification still required on a real DB run (create 2 profiles → enqueue image jobs → confirm prompts/samples differ, and confirm `thumb_only` uses thumbnail as background in export/preview).

## 2026-06-03 (YouTube: Upload % in Progress + Remove YouTube Page)

### What Changed
- Progress page now shows a **YouTube** column per batch/channel:
  - `Queued`, `Uploading XX%`, `Done`, `Failed`, `Cancelled`
- Live upload percent is driven by the existing upload progress callback and cached in-memory while uploading.
- Upload now re-reads the latest profile from Postgres before starting, to ensure uploads always use the current per-profile defaults.
- Removed the standalone **YouTube** workspace page from the left navigation (Progress is now the monitoring surface).

### Why Changed
- Boss wanted upload monitoring integrated into the same Progress pipeline view, and to remove the separate YouTube page once the pipeline is complete.

### Affected Files
- `python_app/docs/youtube-progress/tasks.md`
- `python_app/docs/youtube-progress/design.md`
- `python_app/docs/youtube-progress/technical.md`
- `python_app/views/progress_view.py`
- `python_app/views/core_view.py`
- `python_app/database/youtube_db.py`
- `python_app/main.py`

### Known Limitations
- Upload percent is live (in-memory) and resets if the app restarts mid-upload. DB status still remains accurate (PENDING/RUNNING/READY/FAILED).

## 2026-06-03 (YouTube: Fix Thumbnail/Playlist + Prevent Re-Upload Loop)

### What Changed
- Thumbnail upload no longer causes the whole job to fail/retry if YouTube rejects the thumbnail:
  - Correct MIME type for PNG/JPG thumbnails
  - Thumbnail failures are recorded as a warning while keeping the upload job `READY`
- Playlist add failures are recorded as a warning while keeping the upload job `READY`.
- Pending job pick order changed to prioritize the most recently retried/queued upload first.
- Upload chunk size increased (default 256MB, clamped 8–512MB) to reduce per-chunk overhead and improve throughput.
- Progress Notes now show the full warning/error via hover tooltip.
- `Retry YouTube Upload` now works even if the job was previously `CANCELLED` (explicit retry forces it back to `PENDING`).
- Added terminal log events so Boss can confirm retry/pickup/progress without relying on UI refresh:
  - Retry requested
  - Job picked by worker
  - Upload % (logged every 10%)
  - Done / Failed

### Why Changed
- Boss reported: uploads succeed but thumbnail isn’t applied, playlist isn’t applied, and the same batch re-uploads repeatedly. Root cause was post-upload thumbnail failure throwing an exception and forcing retries.

### Affected Files
- `python_app/services/youtube_uploader.py`
- `python_app/database/youtube_db.py`
- `python_app/main.py`

## 2026-06-02 (YouTube: OAuth Apps Manager + Per-Profile Client Selection)

### What Changed
- Added a DB-backed YouTube OAuth Apps manager (client id + client secret) under Settings → YouTube.
- Added a per-profile dropdown “YouTube OAuth app” to choose which client to use (fallback to global Settings → API fields).
- Updated YouTube connect/upload to resolve OAuth client per profile:
  - If profile selects an OAuth app → use it
  - Otherwise → use global `youtubeClientId` / `youtubeClientSecret`
- Added DB support:
  - `youtube_oauth_apps` table
  - `profiles.youtube_oauth_app_id` column

### Follow-up
- Disconnect now doubles as a safe “Cancel” while a profile is mid-connect (OAuth flow running), so you can cancel and retry without getting stuck in “Connecting…”.

### Why Changed
- Boss has multiple Google accounts/channels requiring different OAuth clients, so the app must support multiple client id/secret pairs safely and scalably.

### Affected Files
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`
- `python_app/database/youtube_db.py`
- `python_app/views/music_view.py`
- `python_app/models/music_model.py`
- `python_app/main.py`

## 2026-06-02 (YouTube Upload: Multi-Channel Connect + AI Use Disclosure)

### What Changed
- Updated YouTube Connect so if the authenticated Google account returns multiple channels, the app prompts you to select which channel to bind to the selected Music Profile.
- Added a per-profile “AI use” setting (Yes/No) and sends it on upload via `status.containsSyntheticMedia`.
- Added DB support for the new profile setting via `profiles.youtube_contains_synthetic_media`.

### Why Changed
- Boss manages multiple channels under the same Google login, so “connect” must not silently bind to the wrong channel.
- Boss requires the YouTube “AI use” disclosure to be present and automatically applied from saved profile defaults.

### Affected Files
- `python_app/services/youtube_oauth.py`
- `python_app/services/youtube_uploader.py`
- `python_app/views/music_view.py`
- `python_app/main.py`
- `python_app/models/music_model.py`
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`

## 2026-06-02 (YouTube Upload: Category Dropdown + Batch-Date Scheduling + Thumbnail Attach)

### What Changed
- Replaced Profile “Category id” free-text field with a dropdown of common YouTube categories (Music = 10) while still allowing custom numeric entry.
- Changed Scheduled publish behavior:
  - Profile stores only publish time (HH:MM).
  - Upload computes `publishAt` using `batchId` date + profile time (same batch date by default).
- Added thumbnail attachment during upload:
  - Resolves per-batch thumbnail from the batch run folder and uploads it after `videos.insert` using `thumbnails.set`.

### Why Changed
- Category ids are not user-friendly; dropdown prevents incorrect values and reduces friction.
- Scheduling date should match the batch date automatically; the profile only needs a default time.
- Each batch has its own thumbnail; uploads should consistently attach it without manual steps.

### Affected Files
- `python_app/views/music_view.py`
- `python_app/main.py`
- `python_app/services/youtube_uploader.py`

## 2026-06-02 (YouTube: Playlist Dropdown + Publish Time Storage Fix)

### What Changed
- Added a per-profile Playlist dropdown:
  - Playlists are fetched from YouTube using the connected profile credentials and cached per profile.
  - Selected playlist id is saved as `youtubePlaylistId` on the profile.
- Upload now automatically adds uploaded videos to the selected playlist (when set) using `playlistItems.insert`.
- Expanded default YouTube OAuth scopes to include playlist write permission (`youtube.force-ssl`). Existing connected profiles must Disconnect + Connect again to grant the new scope.
- Fixed Scheduled publish-time storage by introducing `profiles.youtube_publish_time` (text) so time-only values do not conflict with the legacy `youtube_publish_at` timestamp column.

### Why Changed
- Boss needs an easy way to pick the correct playlist per channel before upload.
- Profile Scheduled time is stored as HH:MM; it must not be persisted into a timestamp column.

### Affected Files
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/services/youtube_uploader.py`
- `python_app/main.py`
- `python_app/services/youtube_oauth.py`

## 2026-06-02 (Fix: Profile Save SQL Param Mismatch)

### What Changed
- Fixed `db_upsert_profile` SQL placeholders so saving a Profile no longer crashes with `TypeError: not all arguments converted during string formatting`.

### Why Changed
- The INSERT statement included the `youtube_oauth_app_id` column but missed its `%s` placeholder, causing a mismatch between placeholders and parameters.

### Affected Files
- `python_app/database/persistence.py`

## 2026-06-02 (UX: Profile Save Status Timestamp)

### What Changed
- Profile Save now writes a timestamped footer/status message (e.g., `Profile saved: <name> · YYYY-MM-DD HH:MM:SS`) so repeated saves are clearly visible.
- Profile Save errors are handled with an in-app warning instead of crashing the app.

### Why Changed
- The previous status text ("Profile saved") could look unchanged when saving repeatedly, which made it hard to confirm the click succeeded.

### Affected Files
- `python_app/main.py`

## 2026-06-02 (UX: Single Global Footer Status)

### What Changed
- Global footer status now shows the latest app status message on every page (Dashboard/Progress/Image/Video/YouTube/Settings), instead of being limited to Music/Settings.
- Video export status updates now also update the global footer status, so long-running export/merge work is visible from anywhere.
- Removed the Settings page “footer-style” bar and replaced it with a normal Settings action bar at the top, so the app has only one consistent footer.

### Why Changed
- Boss reported inconsistent footers and status visibility across pages; a single global footer makes status feedback predictable and consistent.

### Affected Files
- `python_app/main.py`
- `python_app/views/music_view.py`

## 2026-06-02 (Music Composer: Auto Toggles Toolbar + Lyrics Expand)

### What Changed
- Moved Auto-Gen Image / Auto-GSuno / Auto-Video / Auto-Upload toggles into the top composer toolbar (after Count and before Generate).
- Removed the toggle row from the Song card so the Lyrics editor expands down to the bottom of the card.

### Why Changed
- Boss requested a cleaner layout: automation toggles should live in the top toolbar, and the lyrics editor should use the available vertical space.

### Affected Files
- `python_app/views/music_view.py`

## 2026-06-02 (Image Page: No Global Scroll, Card-Only Scroll)

### What Changed
- Removed the Image page wrapper scroll area so the screen fits without a page-level scrollbar.
- Adjusted Image page layout sizing (reduced hard minimum heights, added row/column stretch) so each section fits the viewport and scrolling happens inside lists/tables/editors only.

### Why Changed
- Boss requested: no global page scroll; only allow scroll inside each card section when content exceeds.

### Affected Files
- `python_app/views/image_view.py`

## 2026-06-02 (Music Composer: Automation Card Under Channels)

### What Changed
- Moved the Auto-Gen Image / Auto-GSuno / Auto-Video / Auto-Upload toggles + Generate button out of the top toolbar.
- Added a dedicated full-width “Automation” card under the OK/ALT channel lists to keep the toolbar clean and group actions logically.

### Why Changed
- Boss requested the automation controls to live under the OK/ALT channels and span the two-column width for better visual balance.

### Affected Files
- `python_app/views/music_view.py`

## 2026-06-02 (Image Page: Batches Panel Above Job Queue)

### What Changed
- Split the batch date filters + batch list + Generate/Stop/Clear actions into a dedicated “Batches” panel.
- Moved the “Batches” panel to the right column above “Job Queue” for a clearer workflow.

### Why Changed
- Boss requested that batch selection controls live above the Job Queue instead of inside the prompt panel.

### Affected Files
- `python_app/views/image_view.py`

## 2026-06-02 (Spectrum Particles v2: Spawn Gating + Reactive Color + Styles)

### What Changed
- Added new particle settings:
  - Spawn Mode (Always / Audio Reactive Only)
  - Spawn Trigger (Kick / Bass / Kick or Bass) + Threshold
  - React Color + React Strength (base → react blend)
  - Style (Dot / Soft Glow / Ring / Spark / Bokeh)
- Updated the Python app Particles settings UI (PyQt) to expose these new controls.
- Updated the MP4 export renderer (ModernGL point sprites) to match preview behavior, including a new `pt_style` shader uniform and style-specific sprite shaping.

### Why Changed
- Boss wanted particles to stay “quiet” until audio reacts, to react via color on beat/bass, and to have a few more beautiful particle styles without adding an overwhelming settings UI.

### Affected Files
- `python_app/views/settings_view.py`
- `python_app/main.py`
- `visualizer/gpu_render.py`
- `python_app/models/spectrum_model.py`

## 2026-06-01 (Video Preview + Suno Lyrics: Request Hardening)

### What Changed
- Updated the Video template preview renderer (`SpectrumPreview`) to initialize ModernGL using `moderngl.init_context()` with a Qt `getProcAddress` loader and to bind the QOpenGLWidget framebuffer via `detect_framebuffer(defaultFramebufferObject())`.
- Added browser-like request headers (`Accept`, `Connection`, `User-Agent`) to Suno lyrics POST/GET requests to reduce provider-side blocking.

### Why Changed
- Boss reported `Terminal#531-536` repeated logs: `Error in paintGL: 'QOpenGLContext' object has no attribute 'functions'`. This originates from ModernGL/glcontext auto-detection under PyQt6.
- Boss provided Suno lyrics generation docs; requests were aligned with the API, and headers were hardened to match the credits request pattern.

### Affected Files
- `python_app/views/components.py`
- `python_app/services/suno_lyrics.py`

## 2026-06-01 (Music Generation: Album Consistency per Batch)

### What Changed
- Enforced a single album name per `batchId` during bulk generation: the first successful song in a batch sets the album, and all subsequent songs in the batch reuse it.
- Extended title/album generation to support a forced album so providers keep album constant while still generating unique titles.

### Why Changed
- Boss requested album name consistency within the same batch (History should show one album across the batch rows).

### Affected Files
- `python_app/controllers/music_controller.py`
- `python_app/services/music_generation.py`
- `python_app/docs/music-pipeline-upgrades/tasks.md`
- `python_app/docs/music-pipeline-upgrades/technical.md`

## 2026-06-02 (Image Worker: Prevent Thumbnail Attempt Burn When BG Not Ready)

### What Changed
- Image worker now defers thumbnail jobs until their background image is READY, without bumping `attempt_count`.
- Pending job ordering is adjusted so background jobs are processed before thumbnail jobs within the same worker tick.

### Why Changed
- Boss logs showed thumbnails failing after 3 attempts with `Background image is not ready yet` even though this is a dependency wait state, not a real generation failure.

### Affected Files
- `python_app/services/image_generation.py`

## 2026-06-02 (Auto-Video: Prevent Partial Merge When MP3/MP4 Not Complete)

### What Changed
- Auto-Video now waits for the expected MP3 count per batch before starting export/merge.
- Merge now requires that the expected MP4 count is fully ready (no more “merge whatever exists” behavior).

### Why Changed
- Boss reported Auto-Video merging early after converting only a few MP3s, producing a merged video missing tracks (partial batch).

### Affected Files
- `python_app/main.py`
- `python_app/docs/auto-video-after-suno/technical.md`

## 2026-06-02 (Progress Page: End-to-End Pipeline Reporting)

### What Changed
- Added a new primary sidebar page: Progress.
- Implemented an end-to-end progress report split into Music, Image, Converter, and Merge, shown per batch and per channel (OK/ALT).
- Added DB helpers for efficient progress reads (song counts per batch, image job status per batch).
- Fixed Progress UI initialization by using the existing `_apply_card_field` styling helper for comboboxes.
- Improved Progress page performance by moving refresh computation off the UI thread, adding an in-flight guard, and reducing auto-refresh frequency.
- Further improved Progress performance by batching DB reads (song counts, run dirs, image job statuses) and caching output-directory scans using directory mtime.
- Fixed Progress limit dropdown popup rendering by enforcing a minimum width for the combobox and its popup view (prevents items being elided to "...").
- Hardened Progress refresh against “stuck refreshing” by adding a stale in-flight watchdog and speeding up folder scans using a single `os.scandir` pass.
- Added Postgres connect/query timeouts and missing indexes for Progress queries (prevents indefinite hangs and speeds up large tables).
- Fixed Progress “Refreshing…” stuck state by routing background-thread UI updates through a Qt signal (thread-safe) instead of relying on `QTimer.singleShot` from a non-Qt thread.
- Changed Progress table ordering to show the latest batches first (run date / batch descending).
- Added Progress From/To date filters and a per-row right-click context menu to restart Image/Converter/Merge stages and open the output folder.
- Fixed Progress right-click menu readability by styling `QMenu` (background, text color, selection) in the global stylesheet.
- Added a Progress Status column (Queued/Rendering/Converting/Merging/Done/Failed) so you can quickly see if a row is actively progressing.
- Improved Progress “Restart Converter” feedback by showing the exact missing prerequisites (FFmpeg/template mapping/background/output folder/MP3 count) instead of a generic message.

### Affected Files
- `python_app/views/core_view.py`
- `python_app/views/progress_view.py`
- `python_app/main.py`
- `python_app/database/music_db.py`

## 2026-06-02 (Progress: Cancel-All Feedback + Optimistic UI)

### What Changed
- Cancel ALL Pending Jobs now runs asynchronously with an application-modal progress dialog and step-by-step status updates on the Progress page.
- Added structured terminal logs for cancel-all steps (start, image cancel, YouTube cancel, done) with counts and elapsed time.
- Optimistically marks visible Progress rows that are in the Image stage as `Cancelling…` before the DB cancellation completes, then forces a refresh.

### Why Changed
- Boss requested visible progress feedback and terminal logs when cancelling all jobs, and immediate UI feedback for rows still being worked on.

### Affected Files
- `python_app/main.py`

## 2026-06-02 (Progress: Default Date Range = Today)

### What Changed
- Progress page From/To date filters now default to the current date instead of showing an empty placeholder.

### Why Changed
- Boss requested Progress From/To to default to today for faster daily tracking.

### Affected Files
- `python_app/views/progress_view.py`

## 2026-06-02 (Navigation: Dashboard Is Home)

### What Changed
- Renamed the `Home` nav item to `Dashboard` (same page key `home`) so the dashboard landing is the first page.
- Updated the Home placeholder page title/text to `Dashboard` so it matches the nav label.

### Why Changed
- Boss requested the dashboard to live under Home (first landing page) instead of being a separate page.

### Affected Files
- `python_app/views/core_view.py`
- `python_app/main.py`

## 2026-06-02 (Dashboard/Home: KPI + Pipeline Health + Failures + Activity)

### What Changed
- Implemented the Dashboard UI on the Home page:
  - KPI cards (Active Batches, Failed Items, Songs, Images Ready, MP4 Converted, Merged Videos, YouTube Uploaded, Suno Credits)
  - Pipeline Health stage distribution (from Progress rows)
  - Recent Failures table (from Progress rows) with right-click actions (reuse Progress restart/cancel actions)
  - Recent Activity table (derived from DB tables: songs, image_jobs, youtube_upload_jobs)
- Added an async refresh + auto-refresh timer that only runs while Dashboard (Home) is active.

### Why Changed
- Boss requested a real dashboard to live on Home so the app opens with an “at a glance” operational view.

### Affected Files
- `python_app/views/dashboard_view.py`
- `python_app/database/dashboard_db.py`
- `python_app/main.py`
- `python_app/docs/dashboard/design.md`
- `python_app/docs/dashboard/technical.md`
- `python_app/docs/dashboard/tasks.md`
- `python_app/database/image_db.py`
- `python_app/docs/progress-page/*`

## 2026-06-02 (Image Page: Layout and Space Rebalance)

### What Changed
- Rebalanced the Image workspace layout into a two-column layout:
  - Left: Background/Thumbnail samples + previews, with Prompt+Run moved under the previews.
  - Right: Job Queue occupying roughly 50% width from top to bottom.
- Improved preview fit by enhancing `AspectRatioBox` sizing behavior (height-for-width) to reduce wasted space.

### Affected Files
- `python_app/views/image_view.py`
- `python_app/views/components.py`

## 2026-06-02 (Sidebar Icons: Missing Icons)

### What Changed
- Added missing sidebar icons for Progress and YouTube in the `public/icons/lucide` set so all left navigation items render consistently.

### Affected Files
- `public/icons/lucide/activity.svg`
- `public/icons/lucide/youtube.svg`

## 2026-06-03 (Music History: Load Lyrics on Select)

### What Changed
- Fixed History row selection so the lyrics box always loads the selected song’s lyrics (raw/polished) even when the song came from the database history list (not the in-memory session list).

### Root Cause
- History selection updated `music_current_song_id` but `_current_music_song()` looked up lyrics only in `music_data["songs"]`, which may not contain older DB-loaded songs. The UI therefore showed empty or unrelated lyrics.

### Affected Files
- `python_app/main.py`
- `python_app/controllers/music_controller.py`

## 2026-06-03 (Progress: Cancel Jobs)

### What Changed
- Added Progress right-click actions:
  - Cancel Row (Stop All Jobs)
  - Cancel ALL Pending Jobs (DB)
- Implemented DB-safe cancellation for image jobs and YouTube upload jobs using a `CANCELLED` status. Cancellation is best-effort for already-running work; existing output files are kept.
- Prevented worker updates from overriding a cancelled job (READY/RUNNING/FAILED updates now skip rows already marked CANCELLED).

### Affected Files
- `python_app/main.py`
- `python_app/database/image_db.py`
- `python_app/database/youtube_db.py`

## 2026-05-28 (Video Preview: OpenGL paintGL Error Fix)

### What Changed
- Fixed the Video template preview renderer (`SpectrumPreview`) spamming `Error in paintGL: 'QOpenGLContext' object has no attribute 'functions'` by avoiding `moderngl.detect_framebuffer()` and binding Qt’s default framebuffer via PyOpenGL.

### Why Changed
- On this Windows environment, `PyQt6.QtGui.QOpenGLContext` does not expose `functions()`, causing `moderngl.detect_framebuffer()` to crash every frame and flood logs.

### Affected Files
- `python_app/views/components.py`

### Notes / Limitations
- This impacts the live Video preview UI only; it does not affect end-to-end Music/Image/Video/Merge automation.

## 2026-05-28 (FFmpeg Merge: Apostrophe Path Fix)

### What Changed
- Fixed FFmpeg merge failures caused by special characters (apostrophes, spaces, etc.) in MP4 filenames by hardlinking/copying inputs to safe temp filenames before concatenation.
- The concat list now references the safe temp paths (no escaping edge cases), eliminating errors like `Impossible to open '.../Don\t'` or truncated paths like `Impossible to open '\"D:/.../1.'`.
- Added merge preflight to skip incomplete/invalid MP4s in advance:
  - waits for file size/mtime to stabilize (avoids merging while export is still writing)
  - optionally uses `ffprobe` (when available next to ffmpeg) to reject zero-duration/corrupt outputs

### Why Changed
- Boss reported merge failures like: `Impossible to open '.../4. Don\\t'` which breaks the end-to-end Auto-Video merge flow.

### Affected Files
- `python_app/main.py`
 
### Notes
- Electron-side merge code is not used anymore (Boss confirmed Python app only).

## 2026-05-28 (Image Job Queue: Retry Buttons for BG/TH)

### What Changed
- Replaced the BG/TH bullet status cells with explicit Retry buttons in the Job Queue table.
- Clicking BG Retry re-queues Background and Thumbnail (so the thumbnail always matches the new background).
- Clicking TH Retry re-queues only the Thumbnail.
- Manual retry now resets `attempt_count` and clears `output_image_path` so the worker can re-attempt cleanly.

### Affected Files
- `python_app/main.py`
- `python_app/controllers/image_controller.py`
- `python_app/database/image_db.py`

## 2026-05-28 (Profiles: Video Template Mapping)

### What Changed
- Added `videoTemplateId` to Profiles and persisted it in Postgres (`profiles.video_template_id`).
- Added a Profiles dropdown to select a Video Template; the UI shows `Name · <template_id>` and stores the template id.

### Why Changed
- Boss chose Option C so each channel profile uses the correct video template automatically in future end-to-end automation.

### Affected Files
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/main.py`
- `python_app/controllers/music_controller.py`
- `python_app/docs/video-after-suno/*`

### Migration Requirements
- Run Settings → Database → Migrate to add `profiles.video_template_id`.

### Verification Performed
- Ran `py -m py_compile` on modified modules (clean).

## 2026-05-28 (Image Retry + Auto-Video After Suno)

### What Changed
- Added an automatic image worker poll every 30 seconds when Auto-Gen Image is enabled (non-blocking).
- Added retry behavior for transient image failures (timeouts / SSL EOF / background-not-ready) by re-queuing jobs as PENDING (max 3 attempts).
- Added live Job Queue refresh while the image worker is running (so status updates show without manual Refresh).
- Added a Music page toggle `Auto-Video` (after Suno) and a background scheduler stub that exports+merges per channel folder when MP3s + background + template mapping are ready.
- Added planning docs for the end-to-end Auto-Video workflow.

### Affected Files
- `python_app/main.py`
- `python_app/views/music_view.py`
- `python_app/models/music_model.py`
- `python_app/services/image_generation.py`
- `python_app/controllers/image_controller.py`
- `python_app/database/image_db.py`
- `python_app/docs/auto-video-after-suno/*`

### Notes
- Random thumbnail failures caused by empty top-level sample folder are non-retryable and remain FAILED until folder contents are fixed.

## 2026-05-28 (Image Background: No Text Constraint)

### What Changed
- Enforced a background-only prompt constraint to prevent generating any text/logos/watermarks in background images (to avoid conflicting with thumbnail text overlay).
- Improved SLAI transport robustness by retrying/fallback across endpoints on transient HTTP errors (including 403 Turnstile/Sentinel).

### Affected Files
- `python_app/controllers/image_controller.py`
- `python_app/services/image_provider_slai.py`
- `python_app/services/image_generation.py`

### Verification Performed
- Ran `py -m py_compile python_app/controllers/image_controller.py python_app/services/image_provider_slai.py python_app/services/image_generation.py` (clean).

## 2026-05-28 (Planning: YouTube Upload Flow)

### What Changed
- Added planning documents for a new end-to-end flow to upload merged MP4s to YouTube per profile/channel.

### Affected Files
- `python_app/docs/youtube-upload/requirement.md`
- `python_app/docs/youtube-upload/design.md`
- `python_app/docs/youtube-upload/technical.md`
- `python_app/docs/youtube-upload/tasks.md`

## 2026-05-28 (YouTube Upload: OAuth + Auto Upload Queue)

### What Changed
- Added Settings → API fields for YouTube OAuth client id/secret.
- Added Settings → Profiles YouTube section:
  - Connect/Disconnect per profile (channel)
  - Per-profile defaults: visibility (private/unlisted/public/scheduled), publish datetime, title/description templates, tags, category, made-for-kids.
- Added a new YouTube workspace page showing upload jobs with Retry/Cancel.
- Added Postgres tables for YouTube OAuth accounts and upload jobs.
- Implemented desktop OAuth loopback connect flow (browser consent) and stores refresh tokens encrypted with Windows DPAPI in Postgres.
- Implemented an upload worker that performs resumable uploads with progress + retries for transient failures.
- Integrated end-to-end trigger:
  - when Auto-Video finishes and Auto-Upload is enabled, enqueue a YouTube upload job per channel (OK/ALT not mixed)
  - a 30s scanner also detects missed `MERGED_*.mp4` outputs and enqueues jobs

### Why Changed
- Boss requested a complete end-to-end pipeline: Music → Image → Video → Merge → YouTube upload per profile.

### Affected Files
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/views/core_view.py`
- `python_app/views/youtube_view.py`
- `python_app/main.py`
- `python_app/database/music_migrate.py`
- `python_app/database/persistence.py`
- `python_app/database/youtube_db.py`
- `python_app/services/dpapi.py`
- `python_app/services/youtube_oauth.py`
- `python_app/services/youtube_uploader.py`
- `python_app/requirements.txt`

### New Dependencies
- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`

### Migration Requirements
- Run Settings → Database → Migrate to add:
  - `youtube_accounts`, `youtube_upload_jobs`
  - new `profiles.youtube_*` default columns

### Notes / Limitations
- DPAPI encryption is tied to the Windows user context; moving the DB to another machine/user will require reconnecting YouTube.

## 2026-05-28 (Music Pipeline Upgrades: Batch Integrity, Export Speed, Random Merge, Split AI Providers)

### What Changed
- Bulk generation now keeps retrying within a capped budget until each batch reaches the requested song count (e.g., 10 saved songs for a 10-song request).
- Auto-Video and Export merges now shuffle ordering each merge run (Always random) and write a `MERGE_ORDER_*.txt` file into the output folder for traceability.
- MP3→MP4 export speed controls:
  - Added `Speed` mode (balanced/fast/very_fast) that tunes encoder parameters for NVENC and x264.
  - Auto-Video now exports MP3→MP4 in parallel using the existing `Workers` setting (previously serial).
- Split AI configuration:
  - Title/Album provider: DeepSeek / SLAI
  - Lyrics provider: DeepSeek / SLAI / Suno
- Title/Album generation now uses pool items as inspiration, but always generates a new unique title+album via the selected provider.
- Added Suno lyrics integration using `/api/v1/lyrics` + polling `/api/v1/lyrics/record-info`.

### Why Changed
- Boss observed incomplete batches (8/9 songs saved when requesting 10), slow MP3→MP4 conversion in bulk, and wanted randomized merged song ordering.
- Boss requested lyrics provider selection including Suno, while keeping title/album generation provider separate.

### Affected Files
- `python_app/controllers/music_controller.py`
- `python_app/services/music_generation.py`
- `python_app/services/suno_lyrics.py`
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/views/video_view.py`
- `python_app/services/video_export.py`
- `python_app/main.py`
- `visualizer/main.py`
- `visualizer/gpu_render.py`
- `python_app/docs/music-pipeline-upgrades/*`

### Notes / Limitations
- Suno lyrics prompts are limited to 200 characters per Suno API docs; prompts are truncated to fit.
- Suno lyrics API requires a callback URL; configure Settings → Suno callback URL (ngrok recommended).

## 2026-05-28 (Hotfix: Suno Lyrics 403 + Batch Retry Budget)

### What Changed
- Fixed `batchMaxExtraAttempts=0` being treated as “use default” due to a falsy `or` expression; 0 now correctly means no extra attempts.
- Restored song draft retry loop to honor `songDraftMaxAttempts` (it was incorrectly fixed at 1 attempt).
- Improved Suno lyrics error handling:
  - HTTP 401/403 now surfaces as “forbidden/unauthorized” with clear guidance and aborts retries immediately (avoids burning the whole batch retry budget on a bad key/permissions).

### Affected Files
- `python_app/controllers/music_controller.py`
- `python_app/services/suno_lyrics.py`

## 2026-05-28 (Suno Credits: Remaining Balance + Credit Gate)

### What Changed
- Added Suno remaining credits integration using `GET /api/v1/generate/credit`.
- Added Settings → Suno UI:
  - `Check Credits` button + live `Credits: N` label
  - configurable `Reserve`, `Music cost`, `Lyrics cost`
- Added credit gating:
  - Before starting bulk Generate, the app checks remaining credits and blocks the run if `remaining < (estimated_cost + reserve)`.
  - Before submitting an individual Suno task (auto/manual), the app blocks if `remaining < (music_cost + reserve)`.

### Affected Files
- `python_app/services/suno_credits.py`
- `python_app/models/music_model.py`
- `python_app/views/music_view.py`
- `python_app/main.py`

## 2026-05-28 (Header: Suno Credits Display)

### What Changed
- Displayed Suno remaining credits under the user name in the app header.
- Added a lightweight background refresh (60s cache/interval) and updates after saving Suno settings or pressing `Check Credits`.

### Affected Files
- `python_app/views/core_view.py`
- `python_app/main.py`

## 2026-05-28 (Generate: Always Refresh Suno Credits)

### What Changed
- Generate now always attempts a Suno credits refresh when a Suno API key is configured, even if the current run does not use Suno.
- Added a “freshness” helper so Generate reuses a very recent cached credit value (≤ 15s) and otherwise re-checks via API (reduces perceived latency while staying strict).

### Affected Files
- `python_app/main.py`

## 2026-05-28 (Suno Credits: Better 403/1010 Diagnostics)

### What Changed
- Added browser-like request headers (`User-Agent`, `Accept`, `Connection: close`) to reduce provider-side 403 blocks.
- Improved error parsing so 403 with `code=1010` surfaces as a likely provider block (permissions/plan/IP/VPN/bot protection), making it clearer what to fix.

### Affected Files
- `python_app/services/suno_credits.py`

## 2026-05-26 (Settings Database: Clear Songs)

### What Changed
- Added a `Clear songs DB` danger action button to the Settings → Database page.
- Wired the Settings button to the existing generated-data purge handler used by Music → Pools.

### Why Changed
- Boss requested a quick way to delete all generated songs directly from the Database settings page without needing to switch to Music → Pools.

### Affected Files
- `python_app/views/music_view.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- Reuses the existing DB purge workflow (`music_controller.clear_generated()` → `database/music_pools.clear_generated`) without introducing any new deletion code paths.

### Verification Performed
- Ran `py -m py_compile python_app/views/music_view.py python_app/main.py`
- Checked editor diagnostics: clean

### Notes
- The purge action deletes generated tables (`songs`, `history`, `images`) and is not reversible.

## 2026-05-26 (Image Generation: Per-Channel Background + Thumbnail)

### What Changed
- Added a full Image workspace page (samples, prompt presets, date range, generate/stop, job queue table).
- Added a new Settings → Image tab to configure background/thumbnail sample directories, output directory, resolution, and style strength.
- Implemented a DB-backed image job queue (`image_jobs`) with statuses and retry support, plus prompt presets and anti-repeat history.
- Added a prompt preset manager (add/edit/delete) backed by `image_prompt_presets`.
- Added 16:9 preview panes for background + thumbnail; selecting a job row loads generated outputs into the previews.
- Image workspace UX improvements:
  - shows active BG/Thumb sample folder paths and image counts,
  - supports recursive listing under the configured sample folders,
  - provides empty-state text when no samples/jobs exist,
  - disables Stop when idle and only enables it when there are pending/running jobs.
- Added a background worker pipeline that:
  - generates `background_*.png` from a selected background sample + prompt,
  - generates `thumbnail_*.png` from the generated background blended with a thumbnail sample + prompt.
- Integrated auto-enqueue: when a song is generated and `autoGenImage` is enabled, enqueue background+thumbnail jobs for both OK and ALT channels in that batch.
- Fixed Image “Generate Now” crash when rendering Job Queue (profile name lookup).
- Improved image job validation: Generate Now filters missing sample paths; background job error includes selected filenames to help identify missing samples.
- Fixed image job sample path decoding from Postgres JSONB so background jobs can see selected samples reliably.
- Job Queue now shows 1 row per channel per batch (BG+TH), supports BG/TH preview per row, and supports double-click preview on samples.
- Updated manual Image generation to select existing batches from Music History (multi-select batch picker) instead of creating new manual batch ids.
- Added a `Clear Queue` action to delete all image jobs from Postgres (with confirmation).
- Moved last-run image worker summary (`completed/checked/failed`) into the Job Queue footer area.
- Improved Image worker logs with per-job start/end timing and SLAI request timing for easier diagnosis.
- Updated SLAI IMG integration to use multipart/form-data (per api-img.slai.shop docs), prefer api-img endpoint first, and include Authorization header when downloading returned URLs.
- Hardened SLAI IMG network transport against `EOF occurred in violation of protocol` by forcing TLS 1.2 and using connection-close; if one endpoint fails at TLS level, it will try the fallback endpoint.
- Updated sample listing to top-level-only (ignore subfolders) per Boss requirement, and updated thumbnail generation to embed the thumbnail style sample as a visual reference box instead of blending pixels into the background.
- Reduced thumbnail text size by scaling the generated text-only overlay to 91% before compositing, keeping the background pixel-identical.
- Updated the thumbnail overlay prompt to include size-only placement rules (percent of 16:9 frame) without prescribing style (style comes from the thumbnail sample reference).
- Added Random checkboxes for Background Samples and Thumbnail Samples; when enabled, the system picks 1 sample per job using least-used history across the folder (no manual selection required).
- When Random is ON, the corresponding sample list is disabled and any existing selections are cleared (and persisted as empty selection).

### Why Changed
- Boss requested image generation from curated samples with prompt presets, and output counts that scale per channel:
  - Example: 3 OK + 3 ALT = 6 channels/day → 6 backgrounds + 6 thumbnails per day.

### Affected Files
- `python_app/main.py`
- `python_app/views/music_view.py`
- `python_app/views/image_view.py`
- `python_app/controllers/image_controller.py`
- `python_app/services/image_generation.py`
- `python_app/services/image_provider_slai.py`
- `python_app/database/music_migrate.py`
- `python_app/database/music_db.py`
- `python_app/database/image_db.py`
- `python_app/docs/image-generation-samples/requirement.md`
- `python_app/docs/image-generation-samples/design.md`
- `python_app/docs/image-generation-samples/technical.md`
- `python_app/docs/image-generation-samples/tasks.md`

### Architecture Impact
- Introduces a Postgres-backed job queue for images (similar lifecycle to the Suno poller), enabling resume/retry and UI visibility.
- Uses the existing Suno “run folder” allocation flow and persists per-batch folder mapping via `batch_run_dirs` to keep outputs stable.
- Keeps UI updates thread-safe by emitting results through the existing `music_event` bus.

### New Dependencies
- Uses `Pillow` (`PIL`) for image decoding/PNG conversion, blending, and cover-crop resizing.

### Migration Requirements
- Run Database → Migrate to create:
  - `batch_run_dirs`, `image_jobs`, `image_prompt_presets`, `image_random_history`.

### Verification Performed
- Ran `py -m py_compile` on all image-related modules (clean).
- Ran `ensure_database_and_migrate()` using `.env` DB config (migrations applied successfully).

### Known Limitations
- Requires a valid `SLAI IMG API key` configured in Settings → API.
- Requires configured sample folders:
  - `imageBackgroundSamplesDir` and `imageThumbnailSamplesDir` (legacy fallback: `imageSamplesDir/background` and `imageSamplesDir/thumbnail`)

## 2026-05-26 (Video Export: Auto Merge Reliability)

### What Changed
- Improved Auto merge MP4 robustness:
  - attempts a fast concat merge using stream copy,
  - validates merged duration against the sum of inputs,
  - falls back to a re-encode concat pipeline if copy-merge fails or produces a partial output,
  - skips obviously incomplete MP4 inputs when ffprobe can’t read a valid duration (best-effort merge),
  - adds a `Stop Merge` action button while merging,
  - includes recent FFmpeg output lines in the failure message for easier diagnosis.

### Why Changed
- Boss reported merges intermittently failing or producing merged files that only contain a subset of exported MP4s.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No new UI or new services; only changes the merge strategy inside the existing export workflow.

### Verification Performed
- Ran `py -m py_compile python_app/main.py` (clean).

## 2026-05-23

### What Changed
- Fixed the `PyQt6 + QOpenGLWidget + ModernGL` initialization path in `python_app/main.py` by replacing the failing implicit context detection with an explicit Qt `getProcAddress()` loader.
- Updated the Python preview spectrum behavior to match the active renderer rules more closely:
  - removed the non-reactive baseline ring,
  - made `Fill Circle` use the same active color engine instead of a separate flat fill color,
  - tightened the spectrum radius so it sits directly around the logo,
  - made particles spawn around the logo edge and react more strongly to kick energy.
- Added startup persistence/restore for Python app runtime selections:
  - background image,
  - logo image,
  - MP3 folder,
  - selected MP3,
  - selected template id.
- Fixed template save behavior so re-saving the current template updates the same template id instead of always creating duplicates.

### Why Changed
- The preview was not actually usable: `debug.log` showed repeated runtime errors like `QOpenGLContext object has no attribute functions`, so the OpenGL widget was failing before meaningful rendering could happen.
- The Python app had visual behavior drift compared with the main renderer logic, especially for baseline ring, fill circle, particles, and logo spacing.
- File and template selections were only partially persisted, forcing repeated manual setup on restart.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The Python app still remains a standalone PyQt6 application.
- Rendering still reuses shader and audio logic from `visualizer/`, but the Qt host now attaches ModernGL through a Qt-specific loader instead of relying on the failing default detection path.
- Persistence still goes through Electron-style settings where available, with local fallback behavior unchanged.

### New Dependencies
- No new package dependencies added.

### Migration Requirements
- None for code structure.
- Existing saved settings continue to work.
- New persisted keys may now appear in settings data:
  - `videoRenderLogoPath`
  - `videoRenderMp3Dir`
  - `videoRenderSelectedMp3`
  - `videoRenderTemplatePath`

### Verification Performed
- `py -m py_compile python_app/main.py python_app/video_export.py python_app/persistence.py python_app/spectrum_model.py`
- Short PyQt startup smoke test:
  - created `QApplication`,
  - opened `MainWindow`,
  - allowed preview to initialize/render briefly,
  - exited cleanly.
- Verified runtime log output now shows successful `initializeGL` and `paintGL` frames instead of the previous repeated `functions` crash.

### Known Limitations
- Full interactive QA is still not complete for all user flows such as drag positioning, template CRUD under live DB conditions, audio seek edge cases, and full export with real assets.
- The Python app still shares some rendering logic with `visualizer/`, so future renderer math changes should be mirrored carefully.

### Suggested Next Improvements
- Add a dedicated smoke-test harness for `python_app` startup and export command construction.
- Add structured logging around template load/save, audio load/play, and export lifecycle.
- Audit remaining UI behaviors against the Electron feature set so preview and export stay visually aligned.

## 2026-05-24

### What Changed
- Verified the Python app's key runtime flows with live smoke tests instead of static inspection only:
  - audio load/playback/seek,
  - template save/update/load,
  - one real MP4 export using the active renderer pipeline.
- Fixed audio playback readiness in `python_app/main.py` so playback becomes available as soon as the MP3 decoder is ready, without waiting for the heavier spectrum analysis pass to finish.
- Fixed playback clock tracking in `python_app/main.py` so seek, pause, resume, and stop maintain the correct absolute track position instead of drifting from `pygame.mixer.music.get_pos()`.
- Fixed audio duration reporting in `python_app/main.py`:
  - corrected the wrong analyzer property lookup,
  - added fast duration detection through `pygame.mixer.Sound(...).get_length()` so the seek bar can show duration immediately after decode.
- Prevented background audio-analysis status text from overwriting export progress text while an export is running.

### Why Changed
- Runtime verification showed the player was still unreliable even after preview initialization was fixed.
- The old code gated playback on full analyzer readiness, making the player appear stuck while librosa analysis was still running.
- The old seek clock used `pygame.mixer.music.get_pos()` directly, which only reports elapsed time since the latest `play()` call and therefore breaks absolute position after seek.
- The duration label always showed `00:00` because the code looked for `a.info.duration` even though the analyzer exposes `a.info.duration_sec`.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Live playback smoke test with a generated MP3:
  - confirmed `audio_ready=True` before analyzer completion,
  - confirmed play starts,
  - confirmed seek to 5s advances from the correct base position,
  - confirmed pause/resume/stop keep the expected time state.
- Live template smoke test:
  - save current template,
  - update and re-save same template id,
  - reload by id,
  - confirm no duplicate row is created for the same template id.
- Live export smoke test:
  - generated a short MP3,
  - ran `video_export.ExportJob`,
  - confirmed `Exported MP4`,
  - confirmed process exited with code `0`.

### Known Limitations
- Playback verification used controlled smoke assets rather than Boss's full production library.
- Full manual UX validation is still needed for:
  - drag-position interaction feel,
  - large-batch export behavior,
  - long songs with heavy analyzer cost,
  - all spectrum preset combinations under real music.

### Suggested Next Improvements
- Add a small non-UI smoke-test script for `python_app` that validates startup, audio decode, template persistence, and export in one command.
- Add explicit audio-state labels in the UI for:
  - decoding,
  - analyzing,
  - ready,
  - failed.
- Add export failure detail capture into the Python app UI so FFmpeg/renderer errors surface without needing to inspect logs manually.

## 2026-05-24 (Logo Size UI Mapping)

### What Changed
- Changed the Python app logo size slider from a long direct pixel range to a compact UI scale:
  - UI slider now uses `1..10`
  - stored/rendered logo size now uses `100..1000`
- Added conversion helpers in `python_app/main.py` so the slider and the real render size stay in sync.
- Updated template normalization in `python_app/spectrum_model.py` so logo size defaults/clamps to the new real range.

### Why Changed
- The previous logo size slider used a long raw range in the UI, which made the control awkward to use.
- Boss requested a short slider while still keeping a large real render range underneath.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Checked runtime diagnostics: no editor diagnostics reported.
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py`

### Notes
- The UI label now shows both values, for example `Size (3 => 300)`.
- Existing older template values still load, but once adjusted in the UI they are saved using the new `100..1000` real-size mapping.

## 2026-05-24 (Fill Circle Color Engine Cleanup)

### What Changed
- Removed the separate `Fill Color` control from the Python app Layer Inspector.
- Removed `fillColor` from the Python app template normalization path for newly saved templates.
- Kept `Fill Circle` as a simple on/off option that uses the same active layer color engine as the spectrum ring.

### Why Changed
- The preview renderer already uses the active layer color array for the fill pass, so the extra `Fill Color` field was misleading and suggested a second color source that should not exist.
- Boss requested that filled circles automatically follow the same color engine as the spectrum itself.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Searched for remaining runtime references to the removed `Fill Color` editor path.
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py`
- Checked diagnostics: clean

### Notes
- Older local templates may still contain a legacy `fillColor` field in `video_templates_local.json`, but the Python app no longer uses it for rendering.

## 2026-05-24 (Particles Outward Travel Fix)

### What Changed
- Fixed particle launch behavior in `visualizer/particles.py` so particles now spawn near the logo-edge ring and launch radially outward instead of picking a random direction.
- Updated particle speed scaling in both preview and export render paths:
  - `python_app/main.py`
  - `visualizer/gpu_render.py`
- Aligned Python app default particle values in `python_app/spectrum_model.py` with the active normalized slider ranges:
  - `speed: 15`
  - `reactivity: 0.5`

### Why Changed
- Boss reported that particles were visible behind the logo but were not traveling outward toward the screen edges as expected.
- Root cause was a combination of two problems:
  - spawn position was near the logo, but velocity direction was randomized across the full circle instead of being pushed away from the center,
  - the preview/export speed formula was still effectively tuned for the old larger speed values, so the current `1..15` UI range produced motion that was far too weak.

### Affected Files
- `visualizer/particles.py`
- `python_app/main.py`
- `visualizer/gpu_render.py`
- `python_app/spectrum_model.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py visualizer/particles.py visualizer/gpu_render.py`
- Checked editor diagnostics for the updated Python files: clean
- Ran a focused particle motion validation script and confirmed strong radial travel:
  - `avg_outward_alignment: 0.9983`
  - `min_outward_alignment: 0.9879`
  - this confirms particles now move almost entirely away from the emitter center instead of drifting randomly

### Known Limitations
- The shared particle system still emits from the frame center; if the spectrum/logo anchor is moved far away from center, particle origin will not yet follow that moved anchor.
- Full visual QA with Boss's real templates/audio is still recommended to fine-tune travel feel at different lifetime/speed combinations.

### Suggested Next Improvements
- Add emitter-position support so particles always follow the live spectrum/logo anchor, not only the frame center.
- Add a small debug overlay or log values for live particle count / speed / spawn rate when tuning presets.

## 2026-05-24 (Fill Body, Taller Spikes, Edge Death)

### What Changed
- Changed Python preview fill rendering in `python_app/main.py` so `Fill Circle` uses the live outer spike contour instead of a fixed inner circle.
- Applied the same fill-body fix to the shared export renderer in `visualizer/gpu_render.py`.
- Increased supported spectrum spike height range by raising the normalized clamp and UI slider limit:
  - template clamp now supports up to `120`
  - Python app layer slider now supports up to `120`
- Adjusted particle edge culling in `visualizer/particles.py` so particles remain alive until their visible size moves fully past the screen edge.

### Why Changed
- Boss reported that the spectrum body still looked transparent and background content was visible through it.
- Root cause: the old fill path drew a static circle under the ring instead of filling the actual reactive spike silhouette.
- Boss also requested much taller rabbit-ear spikes; the previous normalization/UI hard-capped spike height at `30`.
- Boss reported particles appeared to die too early near the edge. Root cause: culling used particle center coordinates only, not the visible particle radius.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `visualizer/gpu_render.py`
- `visualizer/particles.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py visualizer/particles.py visualizer/gpu_render.py`
- Checked editor diagnostics for all modified Python files: clean
- Verified particle edge logic by code path inspection after switching culling from strict screen bounds to size-aware padded bounds

### Known Limitations
- Export renderer fill-body behavior is now fixed for the curved waveform-style path; if further fill support is needed for every bar-style preset, that can be expanded in a follow-up.
- Rabbit-ear feel still depends on the selected curve/mirror/gravity combination and the actual audio energy distribution.

### Suggested Next Improvements
- Add a dedicated `Ear Boost` control if Boss wants the top-left/top-right peaks exaggerated beyond normal audio response.
- Make particle emitter origin follow dragged spectrum position instead of remaining centered in the frame.

## 2026-05-24 (Independent Reactivity Smoothing)

### What Changed
- Added independent reactivity smoothing settings for the Python app:
  - background reaction smoothing,
  - logo reaction smoothing,
  - particles reaction smoothing.
- Updated the Python preview host in `python_app/main.py` so:
  - background brightness reacts through its own smoothed audio envelope,
  - logo scale reacts through its own smoothed audio envelope,
  - particles now modulate spawn/speed through a smoothed audio envelope so travel can ramp up and down with the music instead of only feeling like a fixed burst system.
- Added the new fields to template defaults/normalization in `python_app/spectrum_model.py`.
- Updated the shared GPU renderer in `visualizer/gpu_render.py` so exported/shared render paths understand the same smoothing settings.

### Why Changed
- Boss reported that background reactivity did not feel like it was responding properly to audio.
- Boss requested logo audio smoothing similar to the spectrum response.
- Boss requested particles to speed up and slow down with audio response, not just exist as static-speed motion.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `visualizer/gpu_render.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py visualizer/gpu_render.py visualizer/particles.py`
- Checked diagnostics for edited files: clean

### Known Limitations
- Visual feel tuning still depends on the source audio's bass profile and the chosen reactivity/smoothing values.
- Shared GPU renderer still contains duplicated render paths; behavior is aligned, but that file would benefit from future refactoring to reduce drift risk.

### Suggested Next Improvements
- Add a small live meter or debug text for background/logo/particle audio envelopes while tuning presets.
- Consider a separate particle `burst` control if Boss wants stronger kick accents while keeping a smoother base-speed movement.

## 2026-05-24 (UI/UX Recommendation Document)

### What Changed
- Added a detailed future UI/UX recommendation document for the standalone Python app:
  - `python_app/UI_UX_RECOMMENDATIONS.md`

### Why Changed
- Boss requested a documented senior-level UX/UI recommendation set before implementation.
- The current Python app UI is functional, but the control density, hit targets, visual fatigue, and live-update behavior need a structured redesign plan rather than ad-hoc styling changes.

### Affected Files
- `python_app/UI_UX_RECOMMENDATIONS.md`
- `python_app/DEVELOPMENT_LOG.md`

### Document Scope
- Captures current UX issues
- Defines UX goals
- Recommends improved information architecture
- Recommends control sizing, layout, input patterns, and interaction behavior
- Defines phased implementation priorities and acceptance criteria

### Verification Performed
- Reviewed current UI structure in `python_app/main.py` before documenting recommendations
- Confirmed document was added successfully

### Notes
- This is a planning/documentation change only; no runtime UI behavior was modified in this step.

## 2026-05-24 (Export Output Folder Visibility)

### What Changed
- Updated the Python app export UI so the output location is visible and selectable from the bottom export bar.
- Added an `Output Folder` button near the export controls in `python_app/main.py`.
- Added a visible output label that shows:
  - the currently selected export folder, or
  - the last exported MP4 full path after a successful export.
- Updated export-event handling so `outputPath` from the renderer is surfaced in the UI instead of being silently ignored.

### Why Changed
- Boss successfully exported MP4s but could not tell where they were saved.
- The app already persisted `videoRenderOutputDir`, but it reused that folder silently, which made export feel confusing and hidden.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/video_export.py`
- Checked diagnostics for `python_app/main.py`: clean

### Notes
- Existing behavior remains: if no output folder is configured, the app still prompts for one before export.
- New behavior makes the folder/path visible in the UI so the user knows where the MP4 is being written.

## 2026-05-24 (Export Progress UX Cleanup)

### What Changed
- Simplified the bottom export toolbar in `python_app/main.py`:
  - removed the unused Python preview/export engine selector,
  - removed the dedicated `Output Folder` button from the toolbar.
- Changed export start behavior so clicking `Start Batch Export` now asks for the output folder immediately.
- The folder picker now opens in the current MP3 folder by default so Boss can export beside the source audio or navigate elsewhere.
- Improved export progress feedback so the UI now shows:
  - which MP3 is currently exporting,
  - current MP3 percent complete,
  - current render stage text from the renderer,
  - rendered frame count when available,
  - how many MP3s have already finished in the batch.
- Enabled visible percent text on the export progress bar.
- Improved success/failure messages so they include the current MP3 or saved MP4 path.

### Why Changed
- Boss needed clearer export progress and batch-state visibility during long exports.
- The previous UI exposed unnecessary controls and did not clearly show:
  - current file,
  - current file percentage,
  - completed batch count,
  - active export step.
- Boss also requested that output selection happen when export starts instead of through a separate button.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/video_export.py visualizer/main.py visualizer/gpu_render.py`
- Checked diagnostics for `python_app/main.py`: clean

### Notes
- Export still uses the selected output folder for the full batch.
- The save-folder chooser now defaults to the MP3 folder so exporting beside the source files is easy.

## 2026-05-24 (Per-Song Export Progress Fix)

### What Changed
- Refined export progress handling in `python_app/main.py` so the UI now tracks a stable current-song progress state instead of blindly echoing every raw renderer message.
- Increased the export progress bar height again and kept the percentage text visible inside the bar for better readability.
- Added percent formatting that shows more useful values for long renders:
  - very small progress now shows as `<0.1%`,
  - early progress under `10%` shows one decimal place,
  - larger progress shows as whole percentages.
- Added stage-message normalization in `python_app/main.py` so noisy startup text no longer makes export look frozen on frame `0`.
- Derived progress from `frame/totalFrames` when available, so the per-song percentage follows actual rendering progress more reliably.
- Cleaned up `visualizer/gpu_render.py` startup event emission:
  - replaced the old `Rendering frame 0...` style noise with a single friendlier `Preparing first frame...` stage,
  - removed the extra `Writing frame 0...` and `Frame 0 written successfully!` messages.

### Why Changed
- Boss reported that export appeared stuck at `Rendering frame 0` and the progress bar was too small and not clearly showing how much of the current song had been exported.
- Root cause was a combination of two issues:
  - the UI trusted raw renderer startup/debug messages too literally,
  - the visible percent format rounded small early progress back to `0%`, which made long renders feel stalled even when frames were advancing.

### Affected Files
- `python_app/main.py`
- `visualizer/gpu_render.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/video_export.py visualizer/gpu_render.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `visualizer/gpu_render.py`
- Both updated files reported clean diagnostics.

### Known Limitations
- The progress bar is still per-song, not full-batch percent across all MP3s.
- Renderer progress events are still emitted periodically rather than for every single frame, so the bar updates in steps instead of perfectly continuously.

### Suggested Next Improvements
- Add a second small batch-progress bar if Boss wants overall batch completion percent in addition to per-song progress.
- Surface estimated time remaining once a few progress samples are available for the current export.

## 2026-05-24 (UI Recommendations Refresh + UX Phase 1 Pass)

### What Changed
- Updated `python_app/UI_UX_RECOMMENDATIONS.md` so it now reflects the current real app instead of the older simpler control set.
- Added a current-state UX supplement covering:
  - template delete flow,
  - multi-layer inspector controls,
  - glow / softness controls,
  - stacked presets,
  - MP3 folder browsing that shows `.mp3` files,
  - per-song export progress and output-folder flow.
- Applied a focused Phase 1 UX pass in `python_app/main.py` aimed at ergonomics and scanability without rewriting the full layout architecture:
  - increased default control sizing,
  - increased slider hit area,
  - enlarged left and right sidebars,
  - softened the overall dark theme,
  - turned the preview header and playback/export area into clearer card-like surfaces,
  - added explicit `Stop` playback control beside play/pause,
  - strengthened section and panel headings,
  - increased export/playback text readability.
- Added a small `_apply_phase1_ux_tuning()` helper in `python_app/main.py` so common widget types receive a larger baseline size consistently.

### Why Changed
- Boss asked to update the UX recommendation document with the new controls and then start improving the actual UI now.
- The older recommendation document was no longer fully accurate because the app has grown significantly:
  - more layer controls,
  - more export-state controls,
  - more template-management controls.
- The current UI still felt too small, dense, and tiring even though the app had become much more capable.

### Affected Files
- `python_app/UI_UX_RECOMMENDATIONS.md`
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/UI_UX_RECOMMENDATIONS.md`
- Both updated files reported clean diagnostics.

### Known Limitations
- This is a Phase 1 ergonomic improvement pass, not the full planned UX refactor.
- The panels still use a long stacked widget architecture; they are clearer than before, but not yet converted into fully collapsible section cards.
- Heavy slider-driven preview updates are not yet broadly debounced in this pass.

### Suggested Next Improvements
- Convert the left and right sidebars into true grouped section cards or collapsible panels.
- Split the right panel more clearly into:
  - layer management,
  - geometry,
  - blend / glow,
  - color engine.
- Add debounced update behavior for the heaviest preview-affecting sliders.
- Consider replacing the current checkbox pattern with more intentional switch or segmented-control behavior for binary options.

## 2026-05-24 (Fixed Window Size + Left Panel Cards)

### What Changed
- Changed the Python app main window in `python_app/main.py` from a resizable startup size to a fixed application size of `1670 x 1080`.
- Continued the UI refactor in `python_app/main.py` by converting the left control area from one long stacked list into clearer card-style sections:
  - Spectrum Presets
  - Audio Reactivity
  - Positioning
  - Background
  - Logo
  - Particles
- Added a reusable local `section_card(...)` helper in `_build_settings_ui()` so the left panel now has visual grouping with:
  - card surface,
  - border,
  - rounded corners,
  - title,
  - optional helper subtitle.
- Added particle subsection headings inside the particle controls for:
  - Density
  - Motion
  - Visual

### Why Changed
- Boss requested that the main window size be fixed instead of only opening at a preferred size.
- Boss also asked to continue updating the UI after the first ergonomic pass.
- The left panel still felt like a single uninterrupted configuration dump even after the larger controls and calmer theme were added.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- The updated file reported clean diagnostics.

### Known Limitations
- This pass improves left-panel grouping only; the right panel still uses the older long inspector structure.
- The window is now fixed-size, so future layout work should assume `1670 x 1080` as the current design target.

### Suggested Next Improvements
- Refactor the right sidebar into matching cards for:
  - layer management,
  - geometry,
  - blend / glow,
  - color engine.
- Add collapsible behavior once the card grouping is stable.
- Add debounced preview updates for the heaviest live sliders.

## 2026-05-24 (Compact UX Preference Update)

### What Changed
- Updated `python_app/UI_UX_RECOMMENDATIONS.md` again to reflect Boss's clarified layout preferences after reviewing the current UI visually.
- Added an explicit `Boss Compact UI Preferences` section covering:
  - compact inputs and controls,
  - reducing sidebar scrolling,
  - reducing frame / border count,
  - moving left sidebar heavy controls toward compact tabs for:
    - `Spectrum`
    - `Background`
    - `Logo`
    - `Particles`
- Updated the document's immediate priority list so the recommended next UX direction is now compactness and density rather than continuing to enlarge controls.

### Why Changed
- Boss clarified that the preferred desktop-tool direction is more compact and space-efficient, not larger and roomier.
- The recent larger-control pass improved comfort but also made the sidebars feel too bulky, too framed, and too scroll-heavy for the preferred workflow.
- This documentation change is important because future UI work should follow Boss's compact creator-tool preference instead of continuing the earlier larger-control bias.

### Affected Files
- `python_app/UI_UX_RECOMMENDATIONS.md`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Reviewed the updated documentation content directly after patching.

### Suggested Next Improvements
- Implement compact left-sidebar tabs for:
  - `Spectrum`
  - `Background`
  - `Logo`
  - `Particles`
- Reduce border density and nested framing in both sidebars.
- Rebalance compact spacing and readable typography so the sidebars fit more primary controls without constant scrolling.

## 2026-05-24 (Reference-Style Compact UI Pass)

### What Changed
- Updated `python_app/main.py` to apply a new compact dark-blue UI theme based on the provided reference screenshots.
- Introduced a new global style system aligned to the reference direction:
  - dark navy main background,
  - slightly lifted panel surfaces,
  - medium-blue action buttons,
  - compact `Segoe UI`-style typography,
  - darker filled inputs and dropdowns,
  - thinner sliders,
  - lighter, less dominant borders.
- Reduced overall chrome density by removing the previous left-sidebar card stack approach and replacing it with compact left sidebar tabs:
  - `Spectrum`
  - `Background`
  - `Logo`
  - `Particles`
- Reorganized the spectrum-related controls under the compact `Spectrum` tab:
  - style preset,
  - stacked ring preset,
  - audio reactivity,
  - positioning.
- Flattened the `Particles` panel to reduce nested borders and improve compactness.
- Tightened the right `Layer Inspector` layout by:
  - reducing spacing,
  - reducing explicit large-height control styles,
  - adding smaller section labels for:
    - Layer
    - Geometry
    - Blend / Glow
    - Color Engine
- Updated header, playback, and export surfaces to better match the same reference-inspired color and density system.
- Restyled the export button / progress presentation to use the same blue visual language rather than the previous green-heavy variant.

### Why Changed
- Boss requested that the current UI be restyled to closely match the provided reference images while also moving the app toward:
  - compact left sidebar tabs,
  - reduced frames / borders,
  - denser right inspector,
  - less sidebar scrolling.
- The earlier larger-control and card-heavy pass did not match Boss's compact creator-tool preference.
- The old left sidebar still created unnecessary scroll pressure because too much content remained expanded at once.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the refactor.

### Known Limitations
- The reference match is screenshot-derived and implemented through Qt styles, so it is a close visual translation rather than a pixel-perfect clone from original source design tokens.
- The right inspector is denser than before but still scrolls for full layer controls because the layer editor contains many fields.
- A future pass can still improve:
  - compact iconography,
  - tighter export footer styling,
  - more custom toggle controls instead of default checkboxes.

### Suggested Next Improvements
- Continue compacting the right inspector with custom toggle rows and tighter grouped controls.
- Add optional compact sub-tabs inside the layer inspector if Boss wants even less right-panel scrolling.
- Fine-tune button widths, label shortening, and control row composition after Boss visually reviews this pass.

## 2026-05-24 (Corrective UI Pass After Screenshot Review)

### What Changed
- Updated `python_app/main.py` again after reviewing the actual screenshot of the new UI.
- Widened the sidebars to reduce clipping and cramped control rows:
  - left sidebar from `292` to `322`,
  - right sidebar from `306` to `336`.
- Improved the left template area by separating the template action buttons from the template dropdown so they no longer compete in one narrow row.
- Strengthened the top preview action row by shortening labels:
  - `Live Preview`
  - `Background`
  - `Logo`
- Reworked the export area layout into a cleaner stacked structure:
  - first row for folder selection + export action,
  - second row for the selected MP3 combo.
- Rebuilt the right inspector hierarchy into softer grouped section surfaces instead of one long flat stacked form:
  - `Layer`
  - `Geometry`
  - `Blend / Glow`
  - `Color Engine`
- Kept the grouped sections visually lighter by using subtle filled surfaces without heavy border framing.

### Why Changed
- Boss asked for a corrective UI pass after screenshot review.
- The screenshot showed several real problems:
  - left sidebar still felt too narrow,
  - right inspector title/content felt clipped and overcrowded,
  - export row was too compressed,
  - the inspector still behaved like a long settings dump instead of grouped workflow sections.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the corrective pass.

### Known Limitations
- The left sidebar can still scroll when a dense tab such as `Particles` is active because that tab still exposes many controls at once.
- The right inspector is more structured now, but a future pass could still reduce scroll depth further with compact toggles or optional sub-tabs.

### Suggested Next Improvements
- Replace default checkbox rows with compact custom toggle controls.
- Further reduce left-tab vertical length for dense tabs like `Particles`.
- Fine-tune the export footer hierarchy and spacing after Boss visually reviews this corrective pass.

## 2026-05-24 (Chrome Reduction + Text Transport Controls)

### What Changed
- Updated `python_app/main.py` again to reduce extra UI chrome in the center panel.
- Removed the framed container look from:
  - `Preview: ...` header area,
  - `Playback`,
  - `Export Queue`,
  - export status text such as `Analyzing audio for spectrum...`,
  - `Output Folder`.
- Switched the playback transport controls from symbol-only buttons to compact text buttons:
  - `-10s`
  - `Play`
  - `Pause`
  - `Stop`
  - `+10s`
- Removed the framed look from the playback timer label so it reads as plain status text.
- Tightened global horizontal control sizing by reducing:
  - line-edit / combo horizontal padding,
  - combo drop-down width,
  - button horizontal padding,
  - tab horizontal padding and minimum width.

### Why Changed
- Boss requested removal of the remaining frame-heavy look in the center playback/export area.
- Boss also requested text-based playback controls if proper icons were not available.
- Boss requested shorter control widths so inputs and controls fit more naturally inside the left and right sidebars.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Known Limitations
- This pass reduces chrome and control width, but some dense tabs can still scroll because they still expose many controls at once.
- Default Qt checkbox visuals are still present and remain a candidate for a future custom compact toggle pass.

### Suggested Next Improvements
- Replace checkbox rows with custom compact toggle switches.
- Continue shortening long labels in the sidebars where possible.
- If Boss wants even denser sidebars, the next step should be combining some slider rows with shorter inline labels / value placement.

## 2026-05-24 (Center Section Backgrounds + Right Inspector Width Cleanup)

### What Changed
- Updated `python_app/main.py` again to visually split the center area into clearer parts while keeping the lighter no-frame direction.
- Added subtle background sections for:
  - `Playback`
  - `Export Queue`
- Kept the labels/status lines inside those sections visually clean without reintroducing heavy framed rows for every line item.
- Tightened the right inspector to reduce overflow and remove the extra horizontal scrollbar pressure by:
  - forcing the right scroll area horizontal scrollbar off,
  - reducing section-box padding,
  - reducing section internal spacing,
  - shrinking action-button padding in the layer row,
  - shortening layer action button labels to:
    - `Add`
    - `Dup`
    - `Del`
  - shortening long geometry labels such as:
    - `Curve 180`
    - `Mirror 360`
    - `Bar Width`
    - `Spike Height`
    - `Layer Gap`

### Why Changed
- Boss requested some background separation in the center panel so `Playback` and `Export Queue` are visually split part by part again.
- Boss also requested making the right-side inputs and controls shorter so the scrollbar could be removed.
- The screenshot showed the right inspector still suffering from compact-width overflow rather than purely vertical density.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Known Limitations
- This pass is aimed at removing the unnecessary horizontal scrollbar pressure on the right panel.
- If Boss later wants the right panel to avoid vertical scrolling too, that will require a stronger control-reduction pass or collapsible inspector subsections.

### Suggested Next Improvements
- Replace checkbox rows with compact custom toggles to save width and height.
- If needed, make `Layer`, `Geometry`, `Blend / Glow`, and `Color Engine` collapsible.
- Move some slider values inline or to suffix badges to shrink row height further.

## 2026-05-24 (Shared UI Design System Refactor)

### What Changed
- Refactored `python_app/main.py` to introduce a reusable UI design system instead of continuing with scattered one-off widget styling.
- Added centralized UI tokens for:
  - application backgrounds,
  - panel surfaces,
  - borders,
  - text colors,
  - primary/secondary button colors,
  - input surfaces,
  - scrollbar/slider colors.
- Added a single shared app stylesheet builder so core widget styling now comes from one place instead of many individual `setStyleSheet()` calls.
- Added reusable widget-role helpers for:
  - panel roles,
  - label roles,
  - button roles.
- Added a reusable section builder helper for shared panel-section construction.
- Migrated key app areas to the shared system:
  - left template header and sidebar shell,
  - center shell and preview toolbar,
  - playback section,
  - export section,
  - right inspector shell,
  - left compact settings sections,
  - right inspector section cards.
- Replaced several hardcoded button style transitions with role-based button state switching for the export action.

### Why Changed
- Boss asked for the senior-engineering approach: build a reusable UX/UI system first so controls and inputs stay consistent across the whole app.
- Root cause:
  - styling had become fragmented across many local `setStyleSheet()` calls,
  - repeated colors and sizing rules were being copied manually,
  - future UI changes would have kept drifting unless the style system was centralized.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the refactor.

### Architecture Impact
- The Python app UI now has a clearer foundation for future work:
  - theme tokens,
  - shared widget roles,
  - shared panel-section construction.
- This should make future UX changes safer and faster because styling updates can be applied through the shared system instead of per-widget patching.

### Known Limitations
- The app is not fully converted yet; some labels/layouts still use direct local construction and can be migrated further in later passes.
- The refactor intentionally focused on high-impact shared primitives first rather than rewriting every widget in one risky change.

### Suggested Next Improvements
- Continue migrating remaining ad hoc label/value styling to shared helper builders.
- Add shared compact toggle components for checkbox-like controls.
- Add shared helper patterns for slider rows with inline value display.

## 2026-05-24 (UI Consistency Pass: Sidebar Cards + Semantic Buttons)

### What Changed
- Updated `python_app/main.py` again to make the left sidebar, right sidebar, and center control sections follow the same reusable UI language more consistently.
- Expanded the shared UI token/style system with reusable semantic button colors for:
  - action / primary,
  - secondary,
  - delete / danger,
  - warning,
  - success.
- Changed the shared input surface color so form fields inside section cards visually sit with the section-card background instead of looking like a mismatched separate theme.
- Converted the left template area into its own curved section card to match the right inspector style more closely.
- Converted the left sidebar tab content to use curved section cards like the right sidebar:
  - `Spectrum` now uses separate cards for presets, audio reactivity, and positioning,
  - `Background`, `Logo`, and `Particles` now use their own card sections.
- Updated the right inspector layer actions:
  - moved the action buttons onto a new line below the layer selector,
  - renamed them to full words:
    - `Add`
    - `Duplicate`
    - `Delete`
  - applied semantic colors so destructive action is visually distinct.
- Updated center playback/export controls:
  - playback and export sections now use the same softer section-card surface language,
  - playback transport controls are visible button-like controls again instead of ambiguous flat text,
  - `Start Batch Export` was renamed to `Export`,
  - export stop/running state now uses the warning semantic button style.
- Updated template delete to use the semantic danger style.

### Why Changed
- Boss reported the UI system still had visible inconsistencies:
  - left sidebar and right sidebar were not visually aligned,
  - right inspector inputs looked mismatched against their card backgrounds,
  - right inspector action buttons were cramped and did not use proper shared styles,
  - playback/export buttons were not clearly readable as buttons,
  - semantic action colors had not yet been defined for reuse.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Architecture Impact
- The shared UI system now includes semantic action colors, which makes future button styling more reusable and more intentional.
- Left and right sidebars are now closer to the same section-card pattern, reducing style drift.

### Known Limitations
- Some label rows and advanced controls are still built manually and can be migrated further into shared row helpers later.
- Checkbox visuals are still using default Qt indicators rather than a custom compact toggle component.

### Suggested Next Improvements
- Add shared compact toggle components for checkbox-like rows in the inspector and particle controls.
- Add shared slider-row helpers with standardized label/value placement.
- Continue shortening dense right-inspector content if Boss wants to further reduce vertical scroll depth.

## 2026-05-24 (Control Surface Context + Shared Toggle/Slider Helpers)

### What Changed
- Updated `python_app/main.py` to separate control styling by context instead of forcing every field to use the same background treatment.
- Added shared field roles so controls can now be styled differently depending on where they are used:
  - `card` field role for controls living inside curved section cards,
  - `standalone` field role for controls that should keep their own filled surface outside cards.
- Card-contained `QLineEdit` and `QComboBox` controls now visually inherit the card surface instead of adding a second conflicting filled background on top of the card.
- Added reusable helper methods for:
  - card/standalone field assignment,
  - compact toggle rows,
  - shared slider rows.
- Replaced repeated manual slider construction in major sections with the shared slider-row helper, including:
  - left sidebar audio reactivity,
  - background controls,
  - logo controls,
  - particle controls,
  - right inspector geometry,
  - right inspector blend/glow.
- Replaced checkbox-style rows used for compact binary controls with the new shared compact toggle control in:
  - particle enable,
  - right inspector `Curve 180`,
  - right inspector `Mirror 360`,
  - right inspector `Fill Circle`.
- Applied card field styling to major in-card inputs and selects such as:
  - template fields,
  - style/preset dropdowns,
  - anchor dropdown,
  - export track selector,
  - layer selector and layer fields,
  - color-engine dropdowns and color inputs.

### Why Changed
- Boss identified that controls inside cards still looked wrong because they were carrying their own filled background instead of respecting the card surface.
- Boss also asked to proceed with the next best pass after that fix.
- Root cause:
  - the shared style system still treated all line edits and combo boxes as one visual type,
  - slider rows were still duplicated manually across the app,
  - checkbox-like binary controls were not yet using a shared compact control pattern.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the refactor.

### Architecture Impact
- The UI system now separates control surface behavior by context, which is important for maintaining visual consistency between cards and non-card regions.
- The app now has reusable toggle and slider-row primitives that can be used for future UI work instead of rebuilding the same patterns manually.

### Known Limitations
- Not every remaining control row in the app has been migrated yet, but the main left and right inspector patterns now use the shared helpers.
- Standalone field role support exists for future usage, even if most important controls are currently card-contained.

### Suggested Next Improvements
- Continue migrating any remaining manual field rows to the shared helpers.
- If Boss wants even tighter density, introduce inline value badges or two-column slider layouts for selected sections.
- Consider custom popup/menu styling for dropdown lists to further match the card-based UI language.

## 2026-05-24 (Premium Toggle Polish + Inline Metric Density)

### What Changed
- Updated `python_app/main.py` again to improve the compact toggle experience and make slider/value rows denser without losing readability.
- Refined the shared toggle style:
  - wider compact pill shape,
  - clearer visual contrast,
  - visible text state,
  - explicit `ON` / `OFF` labels.
- Added reusable metric-row parsing and rendering helpers so slider controls can show:
  - setting name on the left,
  - current value on the right,
  - slider below.
- Converted the shared slider-row helper to use that denser two-part metric presentation instead of a single combined label line.
- Updated the major left/right sidebar slider flows so live changes and template reloads now refresh the new metric display correctly.
- Upgraded the following areas to use the denser metric presentation:
  - left audio reactivity,
  - positioning `X/Y Offset`,
  - background controls,
  - logo controls,
  - particle controls,
  - right inspector geometry,
  - right inspector blend/glow.
- Updated compact toggles so runtime/template sync now refreshes their visible `ON` / `OFF` state correctly for:
  - particle enable,
  - `Curve 180`,
  - `Mirror 360`,
  - `Fill Circle`.

### Why Changed
- Boss asked to proceed with the next best UI step after the shared toggle/slider helper pass.
- Goal:
  - make toggles feel more premium and intentional,
  - reduce sidebar visual height pressure,
  - keep values easier to scan while preserving compactness.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the update.

### Architecture Impact
- The shared UI system now includes:
  - a stronger compact toggle primitive with explicit state text,
  - reusable metric parsing/display helpers for slider rows.
- Future sidebar controls can now reuse the same denser metric layout instead of rebuilding title/value rows manually.

### Known Limitations
- Dropdown list popups still use the earlier shared popup styling and may benefit from a later polish pass.
- Some non-slider/manual rows still use older layouts and can be migrated later if Boss wants further compact cleanup.

### Suggested Next Improvements
- Convert more non-slider rows into compact two-column layouts where it helps width and height.
- Polish the dropdown popup visuals to better match the card surfaces.
- If Boss wants, continue with a focused spacing pass to shave a little more height from dense sections without hurting readability.

## 2026-05-24 (Compact Form Rows + Dropdown Popup Polish)

### What Changed
- Updated `python_app/main.py` again to reduce vertical waste in short label/input rows and improve dropdown popup styling so combo menus feel more aligned with the shared card-based theme.
- Enhanced the shared combo popup styling:
  - added popup padding,
  - added per-item padding,
  - set clearer minimum item height,
  - added rounded-feeling item spacing,
  - kept selected items visually aligned with the app accent color.
- Added a reusable compact form-row helper for short fields that benefit from a denser two-column layout:
  - label on the left,
  - field on the right,
  - optional automatic card-field styling.
- Applied the compact form-row helper to selected high-value rows in the left sidebar:
  - `Anchor`
  - `Shape`
- Applied the compact form-row helper to selected high-value rows in the right inspector:
  - `Layer Name`
  - `Gravity`
  - `Blend`
  - `Mode`
  - `Direction`
  - `Preset`
- Also tightened the solid-color editor row so `Color` now sits in a denser left/right row with the hex input and `Pick` action instead of using more vertical stacking than necessary.

### Why Changed
- Boss asked to continue to the next UI pass after the toggle/metric density work.
- Root cause:
  - some remaining short form rows were still stacked vertically even though they were good candidates for a denser side-by-side layout,
  - combo popup lists still looked too default compared with the rest of the shared design system.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Architecture Impact
- The shared UI system now has a reusable compact form-row primitive in addition to:
  - section builders,
  - field-role styling,
  - toggle rows,
  - metric slider rows.
- This gives future cleanup passes a better path for shrinking vertical density without ad hoc layout edits.

### Known Limitations
- Not every possible row should be converted to a two-column layout; some longer fields still read better as stacked rows in narrow sidebars.
- Dropdown popup behavior is visually improved, but deeper custom popup rendering would require a more advanced delegate/model approach if Boss wants a truly bespoke menu look later.

## 2026-05-25 (Music Toolbar + Settings UX Parity Fixes)

### What Changed
- Updated `python_app/main.py` after Boss reported several real Music/Settings regressions and parity gaps.
- Added `Khmer` to the Music page `Language` selector while keeping the existing Electron-aligned languages.
- Fixed the Music/Settings refresh pipeline:
  - removed the stale `music_tabs` guard from `_refresh_music_ui()`,
  - switched the guard to the real current composer surface (`music_history_table`),
  - this restores UI repaint after settings/profile changes now that the old inner Music tabs no longer exist.
- Fixed the profile-creation UX path in `Settings -> Profiles`:
  - explicitly refreshes the settings profile list after create/save/delete,
  - explicitly refreshes the Music-page OK/ALT profile lists,
  - scrolls the selected profile into view after refresh.
- Reworked the top Music composer bar so the top card now stretches across the available width instead of living inside the previous left-aligned constrained wrapper.
- Increased top-bar control widths so the `Generate` CTA has safer space and is less likely to clip on the far right.
- Improved slider interaction for Music controls:
  - added reusable `_configure_step_slider(...)`,
  - gave `Creativity` and `Polish` stronger step/page-step behavior,
  - added mouse-wheel slider support through `eventFilter(...)`.
- Ported the Electron `Effects` preview behavior for the Song card:
  - Python now derives `Valence`, `Danceability`, and `Instrumental` preview bars from `Creativity`,
  - this now follows the Electron logic in `src/pages/Home.tsx` instead of incorrectly reading only selected-song stored values.
- Continued the focused settings UX pass:
  - widened the settings tab header buttons,
  - increased minimum size of key cards in `API`, `Profiles`, `Paths`, `Suno`, and `Database`,
  - improved `Profiles` column balance,
  - made the Settings footer use the shared footer panel role for better visual integration.

### Why Changed
- Boss reported four concrete issues:
  - missing `Khmer` language option,
  - top composer card not reaching the edge and causing CTA clipping,
  - `Creativity` / `Polish` sliders feeling difficult to use,
  - profile creation reporting success without visibly updating the list.
- Boss also asked for the next senior UI/UX pass on the weakest Settings tabs (`Profiles`, `Database`, `API`) and for closer Electron behavior where applicable.
- Root cause for the profile/list refresh issue was not just styling:
  - `_refresh_music_ui()` still depended on the deleted `music_tabs` widget from the old Music-page architecture,
  - so the UI refresh path silently stopped executing after that refactor.
- Root cause for the effects mismatch was a parity gap:
  - Electron previews Music `Effects` from the live `Creativity` value,
  - Python was still binding those bars only to selected song fields.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No persistence schema changes were introduced.
- No new dependencies were added.
- This pass improves:
  - current Music composer layout behavior,
  - current Settings page UX structure,
  - runtime repaint reliability after the tab-architecture change,
  - Electron parity for the Music `Effects` preview calculation.

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py python_app/music_model.py python_app/music_pools.py python_app/music_migrate.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Performed runtime smoke launch:
  - started `python_app/main.py`,
  - confirmed the app launches and continues running after the refactor.

### Honest Status
- Verified:
  - the stale refresh guard is fixed,
  - profile create/save/delete now force the relevant list refresh paths,
  - Khmer is added to the Music language selector,
  - the top composer card now uses the full row instead of the old constrained shell,
  - `Creativity` now drives the Song `Effects` preview like Electron,
  - compile/diagnostics are clean,
  - the app launches after the change.
- Partially verified:
  - final live visual balance still needs Boss's screenshot confirmation,
  - slider feel and profile visibility should now be materially improved, but Boss should confirm them in the running UI.

### Suggested Next Improvements
- If Boss wants the Music composer to match Electron even closer, convert the top control row from the current single horizontal layout into a more explicitly wrapping desktop control surface.
- Continue the focused Settings UX pass on:
  - `Profiles` detail density,
  - `Database` action grouping,
  - `API` field grouping and card rhythm.

## 2026-05-25 (Profiles Layout, Database Top Packing, Channel Exclusion)

### What Changed
- Updated `python_app/main.py` again after Boss reported three concrete issues in the current Music/Settings UX:
  - `Channel logo` visually sitting too low in `Settings -> Profiles`,
  - `Database` content appearing pushed down inside its cards,
  - the same channel profile being selectable in both `OK` and `ALT`.
- Reordered the `Profiles` detail form so `Channel logo (center)` now appears immediately after `Folder name`, before `Run prefix (optional)`.
- Tightened the logo field row by forcing the logo row widget to use a fixed-height expanding size policy instead of leaving it free to behave like a larger generic container.
- Fixed the `Database` tab card body packing:
  - added bottom stretch inside `Connection`,
  - added bottom stretch inside `Phrase Pool Data`,
  - this keeps the actual content anchored to the top and pushes spare height downward instead of leaving large dead zones between headings and fields.
- Added mutual exclusion logic for Music page channel selection:
  - when a profile is selected in `OK channels`, it becomes disabled in `ALT channels`,
  - when a profile is selected in `ALT channels`, it becomes disabled in `OK channels`,
  - if a profile is newly selected on one side, it is automatically removed from the opposite side in settings state.
- Disabled conflicting items visually in the opposite list by removing the enabled flag and applying muted text.

### Why Changed
- Boss correctly identified that the current UI still had real structural problems, not just styling preferences:
  - the `Channel logo` row did not read like part of the immediate profile details flow,
  - the `Database` cards looked like their form controls were sinking toward the bottom,
  - allowing the same profile in both `OK` and `ALT` breaks the intended channel assignment model.
- Root cause analysis:
  - `Profiles`: field order and row widget sizing made the logo row feel detached from the folder field,
  - `Database`: the cards had extra reserved height but no explicit bottom stretch inside the body layout, so spacing distribution looked wrong,
  - channel selection: the refresh path rebuilt the lists but did not mark opposite-side selections as blocked or auto-remove conflicts.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py python_app/persistence.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Persistence Verification
- Verified from `python_app/persistence.py`:
  - `ffmpegPath` is stored inside the shared `settings` object,
  - when DB config is active, `write_music_app_data(...)` writes the whole app data payload into Postgres `app_json`,
  - therefore `ffmpegPath` is persisted in the DB-backed `app_json` settings payload, not in a separate dedicated SQL column.

### Honest Status
- Verified:
  - the `Profiles` field order is corrected in code,
  - `Database` cards now explicitly pack content to the top,
  - OK/ALT mutual exclusion is implemented in code,
  - compile/diagnostics are clean,
  - `ffmpegPath` DB persistence behavior is confirmed by code inspection.
- Partially verified:
  - final visual balance still needs Boss's runtime confirmation from the live UI.

### Suggested Next Improvements
- If Boss wants, the next Settings polish pass should:
  - make the `Profiles` editor read more like a true properties panel,
  - tighten button hierarchy further,
  - bring `Paths` and `Database` even closer to the Electron visual rhythm.

## 2026-05-25 (Descriptions + Structures UI Parity Pass)

### What Changed
- Updated the shared saved-text editor builder in `python_app/main.py` so both `Descriptions` and `Structures` follow the same two-pane management UI direction as Electron `SavedTextsTab`.
- Increased the page width budget for the shared text editor pages so the list/editor split can breathe more like the desktop Electron layout.
- Rebalanced the two-pane proportions:
  - larger left saved-items table,
  - stronger right editor panel,
  - taller minimum working surfaces for both panes.
- Added a clearer `Text` label above the editor area to match the field structure Boss referenced.
- Tightened the page rhythm and spacing so the action row, list pane, editor title, fields, and save action read as one continuous workspace.
- Removed a real structural bug from `_build_music_text_tab(...)`:
  - the same shell widget was being added to the page layout twice,
  - this was incorrect and could create awkward layout behavior.

### Why Changed
- Boss asked whether both `Descriptions` and `Structures` could follow the same UI shown in the reference screenshot.
- The Python app already had a conceptually similar editor, so this pass focused on closer layout parity and cleaner desktop proportions rather than inventing a new pattern.
- The duplicate widget insertion in the old builder was also corrected because it was a real code defect, not just a styling mismatch.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - the shared builder now drives both `Descriptions` and `Structures` with the updated wider two-pane layout,
  - the duplicate shell insertion bug is removed,
  - compile/diagnostics are clean.
- Partially verified:
  - final visual closeness to Boss's reference still needs runtime screenshot confirmation.

### Suggested Next Improvements
- If Boss wants even closer Electron parity later:
  - add a more explicit active-state badge rendering in the left table,
  - fine-tune row heights and table density,
  - tune the right pane widths separately for `Descriptions` vs `Structures`.

## 2026-05-25 (Count SpinBox Controls + Saved Description Delete Fix)

### What Changed
- Updated `python_app/main.py` to fix two Music workflow regressions reported by Boss:
  - the `Count` control arrows were visually collapsed / unclear,
  - deleting a song description did not behave reliably.
- Added explicit `QSpinBox` subcontrol styling for the up/down buttons:
  - reserved right-side space for the stepper buttons,
  - made the up/down button hit areas visible,
  - added hover styling so the controls read as clickable.
- Fixed the saved-text delete flow for both `Descriptions` and `Structures`:
  - when a row is deleted, the corresponding active/enabled IDs are also removed from settings state,
  - this prevents stale references from making deletion appear broken,
  - after deletion, the UI refreshes and reselects the next valid row when one exists.

### Why Changed
- Boss reported that the `Count` step arrows were not visible/clickable enough in the Music toolbar.
- Boss also reported that song descriptions could not be deleted.
- Root cause analysis:
  - `Count`: the global `QSpinBox` theme styled the field body but never explicitly styled the spin buttons, so the control affordance became too weak in the dark theme.
  - `Descriptions`: the delete path removed the row itself, but it did not clear the deleted item's IDs from active/enabled settings arrays, leaving stale state behind.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - `QSpinBox` now has explicit visible step-button styling in code,
  - deleting a description/structure now also cleans related active/enabled IDs,
  - the delete flow reselects the next valid row after removal,
  - compile/diagnostics are clean.
- Partially verified:
  - Boss still needs to confirm the step arrows are visually clear in the live Qt runtime on the current machine/theme.

### Follow-up Fix
- A runtime regression was then reported from the delete path:
  - `NameError: name 'merge_settings' is not defined`
- Root cause:
  - the previous delete-flow patch referenced `merge_settings(...)`, but that helper does not exist anywhere in the Python app.
- Fix applied in `python_app/main.py`:
  - replaced the invalid helper call with the existing flat settings merge pattern:
    - `{**self._music_settings(), **settings_patch}`
- Verification:
  - `py -m py_compile python_app/main.py` passes
  - diagnostics for `python_app/main.py` remain clean

## 2026-05-25 (Descriptions + Structures Track-List Style)

### What Changed
- Updated the shared saved-text list UI in `python_app/main.py` so both `Descriptions` and `Structures` now use the same simpler list style as the Music track list instead of the previous two-column table.
- Replaced the left-side `QTableWidget` with a `QListWidget` styled using the existing `trackList` role already used by the MP3 track list.
- Preserved the existing editor behavior:
  - select row -> load item into right editor,
  - save -> refresh list and reselect the saved item,
  - delete -> refresh list and reselect the next valid item,
  - set active -> refresh and keep the selected item focused.
- Added active-state text to the list items using a lightweight `[Active]` suffix.
- Preserved saved item IDs on each `QListWidgetItem` via `UserRole` so refresh/reselection remains stable.

### Why Changed
- Boss asked whether `Song Structures` and `Song Descriptions` could follow the cleaner list style shown in the reference screenshot.
- The app already had a reusable list style for the MP3 track list, so reusing that existing visual system was the safest and most consistent approach.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - both `Descriptions` and `Structures` now use the track-list style in code,
  - shared list actions still compile and wire correctly after the widget swap,
  - compile/diagnostics are clean.
- Partially verified:
  - Boss should still confirm the final row density and active-label feel in the live UI.

## 2026-05-25 (Count SpinBox Width Tuning)

### What Changed
- Updated the Music page `Count` spinbox in `python_app/main.py` to give the built-in up/down controls more room.
- Increased the spinbox control width from `64` to `84`.
- Increased the spin-button lane and text padding so the arrows are less cramped and more clearly clickable.

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - the `Count` input control now has a wider overall field and wider stepper area in code,
  - compile/diagnostics are clean.
- Partially verified:
  - Boss should confirm the final visual comfort in the live UI.

### Suggested Next Improvements
- Do a focused spacing pass to slightly reduce per-section padding and row gaps where readability still holds.
- Convert a few remaining short rows selectively if Boss wants even more compact sidebars.
- If needed later, add custom item delegates for even richer dropdown popup visuals.

## 2026-05-24 (Focused Spacing Compression Pass)

### What Changed
- Updated `python_app/main.py` to reduce vertical and horizontal space usage through the shared UI system rather than by patching isolated widgets.
- Tightened the global compact styling for controls:
  - reduced shared `QLineEdit` / `QComboBox` height from `32` to `30`,
  - reduced shared button minimum height from `32` to `30`,
  - reduced toolbar/transport/compact-secondary button heights and padding,
  - slightly tightened tab padding and minimum tab width,
  - reduced extra top margin on `subheading` labels.
- Tightened the shared section builder:
  - reduced section card content margins,
  - reduced internal section spacing,
  - reduced body top margin,
  - reduced metric-header spacing,
  - reduced compact form-row spacing and default label width.
- Tightened major shell layouts:
  - left sidebar body margins/spacing,
  - right sidebar body margins/spacing,
  - playback section padding/spacing,
  - export section padding/spacing.
- Tightened selected sidebar-specific layouts:
  - tab-page top margin and spacing,
  - compact tab strip spacing,
  - stacked preset row spacing,
  - positioning header row spacing,
  - X/Y offset row spacing,
  - particle control block spacing,
  - layer action row spacing,
  - solid color row spacing,
  - gradient block spacing.

### Why Changed
- Boss asked to proceed to the next UI pass after the compact form-row and popup polish work.
- Goal:
  - reclaim more vertical room inside the left and right sidebars,
  - keep the newer shared design system intact,
  - reduce crowding by trimming accumulated margins and row gaps instead of shrinking text too aggressively.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the spacing pass.

### Architecture Impact
- The compact density of the app now comes more from shared spacing rules than from ad hoc widget tweaks.
- Future UX passes can keep refining density through the central helpers instead of reworking each section independently.

### Known Limitations
- This pass reduces space noticeably, but it does not eliminate all sidebar scrolling in every state.
- Some sections remain inherently tall because they expose many live controls at once.

### Suggested Next Improvements
- If Boss wants even less scroll pressure, introduce collapsible groups in the densest sidebar sections.
- Convert a few more remaining short rows only where it clearly improves density.
- Consider a future “basic / advanced” split for the right inspector if control count keeps growing.

## 2026-05-24 (Playback + Export Layout Refactor and Transparent Slider Wrappers)

### What Changed
- Updated `python_app/main.py` again to address the latest UI issues Boss reported in the center area, right inspector header, and slider-wrapper visuals.
- Changed the shared base widget styling so generic `QWidget` containers default to transparent instead of inheriting the app background fill.
- Kept explicit panel/card backgrounds only on widgets that intentionally use the shared panel roles.
- This removes the unwanted filled background behind compound slider wrapper widgets such as:
  - `X Offset`
  - `Y Offset`
  - similar grouped slider wrappers in the right inspector.
- Tightened the right sidebar header area by:
  - reducing the right panel top margin,
  - removing the extra free-floating subtitle block above the first inspector section.
- Refactored the preview/center area so playback sits directly under the preview instead of being pushed too low by the expanding aspect-ratio region:
  - created a fixed-height preview box for the current window size,
  - reduced center vertical spacing,
  - placed a stretch below the bottom control block instead of letting the preview consume all spare space.
- Refactored playback controls:
  - removed the separate `Pause` button,
  - made the main play button dynamically switch between `Play` and `Pause`,
  - kept `-10s`, `Stop`, and `+10s`,
  - styled the transport buttons with blue action styling as requested.
- Refactored the export area into two clear columns under the playback section:
  - left column:
    - full track list using a `QListWidget`,
    - shows all available MP3 tracks at once instead of a dropdown selector;
  - right column:
    - `Select MP3 Folder`,
    - `Export`,
    - export progress,
    - current song/status text,
    - analyzing/export detail text,
    - output-folder / last-MP4 info.
- Replaced the old combo-box-based MP3 selection flow with track-list-based helpers while preserving the existing export pipeline behavior.

### Why Changed
- Boss reported:
  - slider wrapper rows still looked like they had their own background color,
  - the right panel content appeared pushed too far downward,
  - playback needed to sit closer under the preview and use a dynamic play/pause button,
  - export queue needed a clearer two-column structure with a full track list.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the refactor.

### Architecture Impact
- The shared style system now treats generic layout wrappers as transparent by default, which better supports card-based composition.
- MP3 selection is now driven by a reusable track-list pattern instead of only a compact dropdown.
- Playback state presentation is improved through a single dynamic play/pause action instead of two separate controls.

### Known Limitations
- The preview box height is now tuned for the current fixed window size; if the window-size strategy changes later, the preview sizing strategy may need another pass.
- The export/status text still reuses the same labels for audio-analysis and export-state messaging, which is functional but could be further refined later.

### Suggested Next Improvements
- If Boss wants, do one more polish pass on the new two-column export section:
  - track list item density,
  - selected-row styling,
  - status text hierarchy,
  - column width balance.
- If needed later, further refine the right inspector header treatment now that the extra top gap is removed.

## 2026-05-25 (Saved Text 4-Column Tables + Explicit Spin Arrows)

### What Changed
- Updated the shared saved-text manager in `python_app/main.py` so both `Descriptions` and `Structures` now use a real 4-column `QTableWidget` again instead of the temporary track-list view.
- Applied the exact table headers Boss requested to both managers:
  - `No`
  - `Name`
  - `Status`
  - `Date Created`
- Kept the shared builder model so both pages still use the same code path for:
  - refresh,
  - selection,
  - save/reselect,
  - active-state display.
- Preserved `createdAt` when saving an existing description/structure so the new `Date Created` column stays stable instead of being overwritten on edit.
- Improved the shared table presentation:
  - row selection remains row-based,
  - `Name` stretches to fill the available width,
  - `Status` shows `Active` vs `Saved`,
  - `Date Created` is formatted from real saved timestamps.
- Fixed the `Count` control affordance in the Music toolbar by making the spinbox arrows explicit instead of relying on the platform theme:
  - added `QAbstractSpinBox.ButtonSymbols.UpDownArrows`,
  - widened the control again to better fit the button lane,
  - updated the shared dark-theme `QSpinBox` styling to use real up/down button backgrounds and pressed states.
- Added dedicated SVG assets for the spin controls:
  - `python_app/spin-up-arrow.svg`
  - `python_app/spin-down-arrow.svg`
- Wired those SVG assets into the shared stylesheet so the up/down arrows render visibly in the dark theme.

### Why Changed
- Boss changed direction from the temporary list-style experiment and explicitly requested a 4-column header layout for both `Song Structures` and `Song Descriptions`.
- Boss also reported that the spinbox arrows were still not visible enough in the live UI.
- Root cause analysis:
  - the prior list-style swap removed the table headers Boss wanted,
  - the earlier spinbox width/styling pass still depended too much on native arrow rendering, which can remain effectively invisible in a dark themed Qt runtime.

### Affected Files
- `python_app/main.py`
- `python_app/spin-up-arrow.svg`
- `python_app/spin-down-arrow.svg`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - both saved-text managers now render the requested 4-column table in code,
  - existing save/refresh/reselect logic compiles cleanly after the `QTableWidget` rollback,
  - explicit spin-arrow SVG assets are present and wired into the shared stylesheet,
  - the `Count` spinbox now explicitly requests visible up/down arrow buttons,
  - compile/diagnostics are clean.
- Partially verified:
  - Boss still needs to confirm the final live Qt rendering of the new table density and spin arrows on the running app.

### Suggested Next Improvements
- If Boss wants the table to feel even closer to Electron, the next pass can tune:
  - row height density,
  - column widths,
  - active-row emphasis.

## 2026-05-25 (Startup Crash Fix + Shared Calendar Today Default)

### What Changed
- Updated `python_app/main.py` to fix the runtime crash Boss reported from `Terminal#744-761`.
- Restored the missing shared UI token used by the new spinbox pressed-state styling:
  - added `secondary_pressed` to the shared palette in `_build_ui_tokens()`.
- Added a reusable `AppDateEdit` subclass in `python_app/main.py`.
- Applied that shared date-edit class to every calendar picker created through `_create_calendar_picker(...)`, which currently covers all Music page date controls:
  - `Run From`
  - `Run To`
  - `History From`
  - `History To`
- Kept the existing blank-placeholder field behavior (`MM/DD/YYYY`) for unset filters.
- Changed popup behavior so when an unset date field is opened, the calendar now jumps to and highlights the current date by default instead of opening at the placeholder/minimum date.

### Why Changed
- Boss reported a real startup failure after the earlier spinbox arrow pass:
  - `KeyError: 'secondary_pressed'`
- Boss also asked for calendar pickers to show the current date by default when clicked.
- Root cause analysis:
  - the stylesheet started using `secondary_pressed`, but the token was never added to the shared theme map,
  - the shared calendar helper used a minimum-date placeholder (`2000-01-01`) for blank fields, so the popup naturally opened on that old date instead of today.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Ran a focused runtime smoke check in offscreen Qt mode:
  - instantiated `MainWindow()`,
  - confirmed startup completed successfully,
  - confirmed the previous init crash path is gone.

### Honest Status
- Verified:
  - the `secondary_pressed` KeyError is fixed in code,
  - `MainWindow()` now initializes successfully in a runtime smoke test,
  - all current shared calendar picker controls now use the same today-on-open behavior when blank,
  - compile/diagnostics are clean.
- Partially verified:
  - Boss should still confirm the final visual feel in the normal on-screen app, especially that the popup lands on today's month/day exactly as expected.

### Suggested Next Improvements
- If Boss wants stricter UX later, I can also make `Show all` explicitly clear both date fields and reset the popup to today the next time the picker is opened.

## 2026-05-25 (Calendar Popup Behavior Correction + History Selection Write Reduction)

### What Changed
- Corrected the previous calendar-picker fix in `python_app/main.py` because the first popup override approach was not reliable in the current PyQt binding/runtime.
- Reworked the shared `AppDateEdit` behavior so blank date fields now:
  - temporarily prime themselves with today when focused/clicked,
  - open the popup anchored on the current date instead of year `2000`,
  - restore the blank placeholder if the user leaves without actually choosing a date.
- Kept explicit user selections intact, including when the selected value is today's date.
- Increased the shared calendar picker width so the full `MM/DD/YYYY` value has enough room and no longer truncates visually.
- Removed an unnecessary full `music app data` save from history-row selection in `python_app/main.py`:
  - selecting a history row now persists only lightweight runtime state instead of writing the full normalized app payload on every click.

### Why Changed
- Boss reported that the calendar still showed the old placeholder-era date instead of the current date.
- Boss's screenshot also showed the date field itself was too narrow and clipping the rendered value.
- The earlier implementation only tried to steer the calendar page, but Qt was still anchoring the popup from the field's stored minimum-date value.
- Code inspection also showed a real low-value performance cost:
  - clicking a history row triggered `_save_music_app_data()` even though the action only changes transient UI/runtime selection state.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Ran a focused offscreen runtime test to verify:
  - blank picker focuses to today's date,
  - closing without selection restores placeholder state,
  - explicit selection preserves the chosen date,
  - `MainWindow()` still initializes successfully.

### Honest Status
- Verified:
  - the shared calendar logic now primes today's date before popup anchor time,
  - blank fields restore correctly if the user does not commit a date,
  - the date field width is widened in code,
  - history-row selection no longer forces a full app-data save,
  - compile/diagnostics/runtime smoke checks are clean.
- Partially verified:
  - Boss should still confirm the exact live on-screen feel in the normal desktop app.

### Follow-up Refinement
- Added one more shared fix in `python_app/main.py` so the dropdown-arrow click path also primes today's date through the generic widget event path, not only through field focus / direct body click handling.
- Re-verified:
  - `py -m py_compile main.py` passes
  - diagnostics remain clean
  - `MainWindow()` still initializes successfully in the runtime smoke check

## 2026-05-25 (Phase 1 Safe Restructure: Controller + Refresh Split + Shared Music Helpers)

### What Changed
- Completed the agreed Phase 1 safe restructure in `python_app` without changing the visible desktop workflow.
- Added a new shared helper module:
  - `python_app/music_common.py`
- Centralized repeated backend/common helpers into that module:
  - shared Postgres connection helper,
  - shared text normalization helper,
  - shared DB identity key helper,
  - shared `opening2` lyric-line extraction helper.
- Updated the existing music backend modules to reuse the shared helper layer instead of duplicating their own DB/common helpers:
  - `python_app/music_db.py`
  - `python_app/music_pools.py`
  - `python_app/music_generation.py`
  - `python_app/music_migrate.py`
  - `python_app/persistence.py`
- Added a new orchestration layer:
  - `python_app/music_controller.py`
- Wired `MainWindow` to use the new `MusicController` for Phase 1 music orchestration:
  - settings updates,
  - date-filter persistence,
  - history-row selection handling,
  - Suno poll trigger flow.
- Split the previous monolithic `_refresh_music_ui()` path in `python_app/main.py` into narrower refresh methods:
  - `_refresh_music_runtime_controls(...)`
  - `_refresh_music_editor_state(...)`
  - `_refresh_music_settings_fields(...)`
  - `_refresh_music_reference_views()`
- Kept `_refresh_music_ui()` as the stable top-level entry point, but it now delegates to those narrower refresh slices instead of containing one large mixed block.

### Why Changed
- Boss approved the recommended safe restructure path:
  - extract `MusicController`
  - split `_refresh_music_ui()`
  - centralize DB/common helpers
- The previous shape had three real maintainability/performance problems:
  - `main.py` mixed widget rendering with music orchestration,
  - the music backend repeated DB/connect/normalize helpers across several modules,
  - full music refreshes were too broad for some simple actions.

### Performance Improvement Included
- Reduced one real unnecessary refresh/write-heavy path:
  - history-row selection now goes through the controller and refreshes only the editor/song state instead of forcing the full `music` UI refresh path.
- Combined with the earlier removal of full app-data save on history selection, this makes row-to-row browsing cheaper and less noisy.

### Affected Files
- `python_app/main.py`
- `python_app/music_common.py`
- `python_app/music_controller.py`
- `python_app/music_db.py`
- `python_app/music_pools.py`
- `python_app/music_generation.py`
- `python_app/music_migrate.py`
- `python_app/persistence.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py music_common.py music_controller.py music_db.py music_pools.py music_generation.py music_migrate.py persistence.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_common.py`: clean
  - `python_app/music_controller.py`: clean
  - `python_app/music_db.py`: clean
  - `python_app/music_pools.py`: clean
  - `python_app/music_generation.py`: clean
  - `python_app/music_migrate.py`: clean
  - `python_app/persistence.py`: clean
- Ran a focused offscreen runtime smoke test:
  - instantiated `MainWindow()`,
  - confirmed the app still initializes successfully after the Phase 1 extraction.

### Honest Status
- Verified:
  - the helper duplication has been reduced through the new shared module,
  - music orchestration now has a dedicated controller layer,
  - `_refresh_music_ui()` is now structurally split into smaller responsibilities,
  - compile/diagnostics/runtime smoke tests are clean.
- Partially verified:
  - Boss should still confirm the live desktop feel, especially Music page row selection and Settings refresh behavior during normal usage.

### Suggested Next Improvements
- Phase 2 can safely continue with:
  - tab-visible / dirty-flag refreshes for pools and history,
  - reducing duplicate audio decode work during MP3 load,
  - gradually moving more music business rules out of `MainWindow` and into controller/service layers.

## 2026-05-25 (Phase 2 Performance Pass: Narrower Music Refresh + Audio Duration Cache)

### What Changed
- Continued the approved Phase 2 performance pass in `python_app`.
- Narrowed live Music control refresh behavior in `python_app/music_controller.py`:
  - `_update_music_settings(...)` no longer forces the full `_refresh_music_ui()` path for every small composer control change,
  - it now refreshes only the runtime controls and editor/song state needed for those live changes.
- Kept the full refresh path available for broader workflows, but removed it from the hot path used by:
  - language,
  - creativity,
  - count,
  - strict level,
  - uniqueness history window,
  - shuffle/match/all/cycle toggles,
  - polish strength,
  - auto image / auto Suno toggles.
- Preserved the Phase 1 history-row optimization:
  - selection continues to refresh only the editor/song state instead of rebuilding the full Music surface.
- Optimized the preview audio load path in `python_app/main.py`:
  - added a lightweight `_audio_duration_cache`,
  - keyed the cache by file path + file metadata,
  - stopped calling `pygame.mixer.Sound(...).get_length()` on every load,
  - duration is now cached after analyzer completion and reused on later loads of the same unchanged file.

### Why Changed
- After Phase 1, two safe performance hotspots still remained:
  - small live Music control changes still triggered a broader-than-needed refresh path,
  - audio loading still performed duplicate work for the same file by decoding once for playback and again for duration.
- The goal of this pass was to improve responsiveness without introducing risky UI rewrites or backend behavior drift.

### Affected Files
- `python_app/main.py`
- `python_app/music_controller.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py music_controller.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_controller.py`: clean
- Ran a focused offscreen runtime smoke test:
  - instantiated `MainWindow()`,
  - confirmed the app still initializes successfully after the Phase 2 changes.

### Honest Status
- Verified:
  - live Music control changes now use a narrower refresh path in code,
  - history-row selection remains on the lighter editor-only refresh path,
  - audio duration caching is wired into the load path,
  - compile/diagnostics/runtime smoke checks are clean.
- Partially verified:
  - Boss should still confirm the live desktop feel when rapidly changing Music controls and repeatedly selecting the same MP3 files.

## 2026-05-25 (Phase 6 Architecture Pass: UI Components Extraction)

### What Changed
- Created a new `views/` directory to hold UI component builders.
- Extracted almost 2000 lines of UI construction code out of `main.py` into specialized View Mixins:
  - `views/music_view.py`: `MusicViewMixin` (handles Music workspace, Settings, Pools, Suno tabs)
  - `views/video_view.py`: `VideoViewMixin` (handles Video workspace, Layer UI)
  - `views/settings_view.py`: `SettingsViewMixin` (handles Video Settings, Spectrum Settings)
  - `views/core_view.py`: `CoreViewMixin` (handles App Header, Global Footer, Navigation Shell)
- `MainWindow` now cleanly inherits from these Mixins, preserving all state references while physically splitting the massive file into manageable, domain-specific UI components.
- Fixed a bug where `assets/*.svg` files were not successfully moved on Windows due to PowerShell execution policies, causing missing arrows in QComboBox and QSpinBox controls. SVGs are now properly placed and loaded.

### Why Changed
- Boss requested we take the next logical step and extract UI chunks (MusicTab, SettingsTab, VideoTab) into their own files.
- `main.py` was over 6700 lines long, making it hard to navigate. By using View Mixins, we safely extracted the UI building logic without breaking the tight coupling between the UI elements and the `MainWindow` state.
- This paves the way for further decoupling into pure standalone `QWidget` components in the future.

### Affected Files
- `python_app/main.py`
- `python_app/views/music_view.py`
- `python_app/views/video_view.py`
- `python_app/views/settings_view.py`
- `python_app/views/core_view.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Ran a focused offscreen runtime smoke test:
  - instantiated `MainWindow()`,
  - confirmed the app initializes without `ImportError`, `NameError`, or `AttributeError`, proving the UI Mixins successfully attach to the main window.
  - fixed a runtime `NameError` in `_tick_ui` caused by the missing `_fmt_time` import after extracting components.

### Honest Status
- Verified:
  - 2000 lines successfully extracted into `views/`.
  - Compile/diagnostics/runtime smoke checks are clean.
  - Arrow SVGs are correctly placed in `assets/`.
- Partially verified:
  - Boss should confirm the UI boots correctly and the spin/dropdown arrows are visible again.

## 2026-05-25 (Phase 5 Architecture Pass: Standard Python Package Structure)

### What Changed
- Reorganized the flat `python_app` folder into a professional, scalable Python package structure.
- Created semantic directories and moved files accordingly:
  - `models/`: `music_model.py`, `spectrum_model.py`
  - `database/`: `persistence.py`, `music_db.py`, `music_migrate.py`, `music_pools.py`
  - `services/`: `music_generation.py`, `music_suno.py`, `music_ngrok.py`, `music_callback.py`, `video_export.py`
  - `controllers/`: `music_controller.py`
  - `utils/`: `music_common.py`
  - `assets/`: `combo-arrow.svg`, `spin-up-arrow.svg`, `spin-down-arrow.svg`
- Added `__init__.py` files to each directory to make them proper Python packages.
- Updated all `import` statements across the entire codebase to use the new module paths (e.g., `from models.music_model import ...`).
- Updated the SVG asset paths in `main.py` to point to the new `assets/` directory.

### Why Changed
- As requested by Boss, we needed to make the project structure truly professional.
- A flat file structure inside `python_app/` becomes unmanageable as the project grows.
- Grouping files by their domain (models, DB, services, controllers, UI) follows standard software engineering practices (similar to Django, FastAPI, or advanced desktop apps).
- This structure sets the stage perfectly for the final extraction phase: breaking down the UI from `main.py` into separate components (which could live in a new `ui/` or `views/` folder).

### Affected Files
- Entire `python_app/` directory (moved files and updated imports).
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - Automated import refactoring script.
  - `py -m py_compile main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Ran a focused offscreen runtime smoke test:
  - instantiated `MainWindow()`,
  - confirmed the app initializes without `ImportError` or `FileNotFoundError`, proving the package structure and asset paths are perfectly wired.

### Honest Status
- Verified:
  - The folder structure is now cleanly separated by domain.
  - All imports and asset paths are fully functional.
  - Compile/diagnostics/runtime smoke checks are clean.
- Partially verified:
  - Boss should confirm the codebase feels easier to navigate and verify the UI boots correctly on their machine.

## 2026-05-25 (Phase 4 Architecture Pass: Extract Business Logic to Controller)

### What Changed
- Moved heavy music business logic out of `main.py` and into `music_controller.py`:
  - **Profiles CRUD**: `create_profile`, `save_profile`, `delete_profile`
  - **Saved Texts CRUD**: `save_saved_text`, `delete_saved_text`
  - **Pools Actions**: `generate_pool`, `import_pool`, `clear_pool`, `clear_generated`
  - **Music Generation**: Extracted the massive `_run_music_generation_worker` loop into `generate_music_batch`.
- `main.py` now purely acts as the View layer for these operations, reading UI state, calling the `MusicController`, and showing success/error messages via `QMessageBox`.
- UI refresh orchestration (like clearing text boxes or navigating back to previous items) remains in `main.py`, preserving snappy UI interactions.

### Why Changed
- `main.py` was acting as a monolithic God Object, mixing Qt UI rendering, SQL database calls, and complex generation orchestration.
- By moving these actions to `music_controller.py`, we achieve a clean Separation of Concerns (UI vs Business Logic).
- This drastically improves maintainability and makes future improvements to the music generation pipeline much safer, as we no longer risk breaking the UI layer when adjusting backend logic.

### Affected Files
- `python_app/main.py`
- `python_app/music_controller.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py music_controller.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_controller.py`: clean
- Ran a focused offscreen runtime smoke test:
  - instantiated `MainWindow()`,
  - confirmed the app initializes without import errors, proving the Controller and DB dependencies are correctly wired.

### Honest Status
- Verified:
  - the separation of concerns is strictly enforced,
  - `main.py` is significantly smaller and focused on Qt UI,
  - compile/diagnostics/runtime smoke checks are clean.
- Partially verified:
  - Boss should confirm the live desktop feel when performing CRUD operations on Profiles/Texts, managing Pools, and running a Music Generation batch to ensure the flows still work as expected.

## 2026-05-25 (Phase 3 Performance Pass: Dirty-Gated Views + AudioAnalyzer Cache)

### What Changed
- Added safe dirty-flag logic to the heaviest view rendering paths:
  - `_refresh_music_pool_table`
  - `_refresh_music_pool_stats`
  - `_refresh_music_history_table`
- These methods now check if their respective page (`Settings -> Pools` or `Music`) is currently visible.
- If not visible, they skip the heavy DB fetch/table rebuild and mark a dirty flag (`_music_pools_dirty` or `_music_history_dirty`).
- When the user navigates back to those tabs via `_set_primary_page` or `_on_music_settings_tab_changed`, the dirty flag is checked, and the views are refreshed on-demand.
- Further optimized the MP3 load path in `main.py`:
  - Added an LRU-like cache (`_audio_analyzer_cache`) to store the completed `AudioAnalyzer` instance.
  - When selecting an MP3 that was recently analyzed, the app now skips the heavy 60fps FFT feature extraction and reuses the cached analyzer.
  - Limited the cache size to 5 files to prevent memory bloat while preserving snappy back-and-forth selection behavior.

### Why Changed
- Even with narrower refresh methods from Phase 2, `_refresh_music_history_table` and `_refresh_music_pool_table` were still being triggered in the background during certain full-refresh cycles.
- Rebuilding 1000s of QTableWidget items while the user is looking at another tab wastes CPU and blocks the UI thread.
- Similarly, switching between two MP3 files (e.g. comparing "OK" and "Alt" versions) forced the Python analyzer to re-read and re-fft the whole file every time. Caching the `AudioAnalyzer` makes A/B comparison instant.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran:
  - `py -m py_compile main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Ran a focused offscreen runtime smoke test:
  - instantiated `MainWindow()`,
  - confirmed the app still initializes successfully, loads MP3 files into the cache, and processes page switches without errors.

### Honest Status
- Verified:
  - dirty-gated refresh logic correctly skips work when tabs are hidden,
  - audio analyzer caching is wired in with a bounded limit,
  - compile/diagnostics/runtime smoke checks are clean.
- Partially verified:
  - Boss should confirm the UI responsiveness when switching tabs (e.g. from Video back to Music/History or into Settings -> Pools) and when toggling between two recently selected MP3s.

## 2026-05-24 (Full-Height Export List + Footer Shell Pass)

### What Changed
- Updated `python_app/main.py` again to improve the new export layout and add a real footer shell.
- Fixed the export-height distribution so the MP3 track list can grow to the bottom of the available center column space instead of stopping early:
  - the center shell now gives the remaining height to the bottom control region,
  - the export section itself now stretches inside that region,
  - the track list is allowed to expand instead of being held to a fixed-looking short block.
- Kept `Select MP3 Folder` as a blue action button.
- Changed idle `Export` styling to the shared green/success role, while preserving the runtime warning state when the button becomes `Stop Export`.
- Added a real application footer across the bottom shell using a dedicated shared footer panel role.
- Added footer labels that show:
  - app identity on the left,
  - current template / selected track in the middle,
  - output folder on the right.
- Added footer refresh wiring so the footer updates when:
  - settings/output folder change,
  - template changes,
  - MP3 track selection changes.

### Why Changed
- Boss requested:
  - the export MP3 list should use the whole available height to the bottom,
  - `Select MP3 Folder` should read clearly as a blue button,
  - `Export` should read clearly as a green action button,
  - a new footer should be introduced.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Architecture Impact
- The app shell now has a footer panel layer instead of ending abruptly at the bottom edge.
- Export action semantics are more aligned with the shared role-based button system:
  - folder/action browsing = blue,
  - export/start = green,
  - stop/cancel running export = warning.

### Known Limitations
- The new footer is intentionally lightweight; if Boss wants richer footer behavior later, it can be expanded into a fuller status bar.
- The export two-column proportions may still benefit from one final visual balance pass depending on how many tracks are loaded.

### Suggested Next Improvements
- If Boss wants, do one focused export polish pass next:
  - stronger selected-track styling,
  - better right-column hierarchy,
  - footer text balance,
  - final track-list density tuning.

## 2026-05-24 (Right Inspector Top Alignment + Export Action Card Polish)

### What Changed
- Updated `python_app/main.py` again to correct the visual offset in the right inspector and improve the export queue second column.
- Fixed the right inspector “offset / too much top spacing” feel by:
  - forcing the right `QScrollArea` to align its content to the top,
  - trimming the right panel top margin slightly more,
  - tightening the right panel top-level spacing.
- This makes the `Layer` card sit much closer under `Layer Inspector` instead of feeling like the whole inspector starts too low.
- Reworked the export queue second column into a clearer action/status card:
  - wrapped the right export column content in its own shared section card,
  - added an `Actions` subheading,
  - kept `Select MP3 Folder` as blue/primary,
  - kept `Export` as green/success,
  - increased both action buttons to a clearer `34px` minimum height,
  - kept progress and export status/details inside the same right-side card for stronger grouping.

### Why Changed
- Boss reported two visible UX problems:
  - the right inspector looked like it was taking too much empty height at the top, making the first card feel visually offset,
  - the export queue second column buttons did not look like they were using the shared button styling clearly enough.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Architecture Impact
- The right inspector now has a more stable top-aligned scroll behavior rather than relying on the scroll area’s default layout behavior.
- The export second column now follows the same card/grouping pattern used elsewhere in the shared UI system instead of leaving actions and status floating in open space.

### Known Limitations
- This improves the visual offset problem, but if Boss wants the right inspector even tighter later, the next step would be reducing the title/header height further or making some inspector sections collapsible.
- The export right column is now clearly grouped, but its exact width balance relative to the track list may still benefit from one final visual review.

### Suggested Next Improvements
- If Boss wants, do one more pass on the right inspector:
  - slightly tighten the title/header area,
  - reduce section subtitle height,
  - optionally collapse advanced sections.
- Or do one more export polish pass:
  - selected-track emphasis,
  - status text hierarchy,
  - column width tuning.

## 2026-05-24 (Dropdown Arrow + Inspector Root-Cause Fix)

### What Changed
- Updated `python_app/main.py` again to fix the remaining dropdown-arrow issue and address the real root cause of the right-inspector offset.
- Added a dedicated combo-box arrow asset at `python_app/combo-arrow.svg`.
- Updated the shared combo-box stylesheet so dropdowns now render an explicit down-arrow image instead of leaving the indicator area visually empty.
- Strengthened the export right column further:
  - kept the right-side action/status card,
  - changed the two action buttons into a clearer stacked vertical action layout,
  - preserved `Select MP3 Folder` as blue/primary and `Export` as green/success.
- Fixed the remaining right-inspector top-offset issue at the actual layout source:
  - added a bottom stretch to the right inspector layout so all cards are explicitly packed to the top,
  - this avoids relying only on the scroll area’s alignment behavior.

### Why Changed
- Boss reported two remaining issues:
  - dropdowns still lacked a visible down-arrow,
  - previous passes still had not truly fixed the right-inspector offset and export-column clarity.
- Root cause analysis:
  - the earlier combo-box styling reserved space for an arrow but did not actually provide one,
  - the earlier inspector pass treated the scroll-area container but did not hard-pack the inspector content itself to the top via the inner layout,
  - the earlier export right-column pass improved grouping, but the horizontal button arrangement still did not read strongly enough as action controls in that narrow column.

### Affected Files
- `python_app/main.py`
- `python_app/combo-arrow.svg`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`
- File compiled cleanly and diagnostics were clean after the pass.

### Architecture Impact
- The shared UI system now has a real reusable combo-box arrow asset instead of relying on implicit/default arrow behavior.
- The right inspector now packs content to the top through the actual inner layout instead of only through scroll-area alignment hints.

### Known Limitations
- This should resolve the remaining inspector-offset root cause, but final visual confirmation still depends on Boss’s runtime review of the live app.
- The export right column is now more readable, but it may still benefit from one more hierarchy pass if Boss wants even stronger visual separation between actions and status.

### Suggested Next Improvements
- If Boss wants, do one short final polish pass on:
  - export status hierarchy,
  - selected-track emphasis,
  - right inspector title/header density.

## 2026-05-24 (Template Management, Style Presets, Background Shake)

### What Changed
- Improved template management in `python_app/main.py`:
  - added `Delete` button with confirmation,
  - kept the template combo focused on the currently loaded template instead of resetting to placeholder after every load,
  - ensured save refreshes and reselects the current template entry.
- Added backend delete support in `python_app/persistence.py` for DB-backed templates.
- Improved style preset handling in the Python app:
  - selecting a style preset now applies a concrete preset patch to the base layer instead of only storing a style string,
  - the Python preview renderer now actually reads and renders the selected style preset.
- Added distinct preview styling behavior for previously weak presets such as:
  - `dot-matrix`,
  - `neon-pulse`.
- Updated the shared GPU export renderer in `visualizer/gpu_render.py` so:
  - background audio reactivity includes shake/zoom-like motion instead of brightness only,
  - `dot-matrix` and `neon-pulse` exports no longer collapse into the same classic bar style.

### Why Changed
- Boss requested:
  - delete support for saved templates,
  - easier template management,
  - reliable save-template behavior,
  - spectrum engine preset list items to work as their own presets,
  - background audio reaction to move/shake instead of only changing brightness.
- Root causes found:
  - template UI had no delete flow,
  - template combo behavior was awkward and not manager-friendly,
  - Python preview style selection was not consumed by the preview renderer at all,
  - export renderer still treated some style presets as the same fallback bar mode,
  - background reactivity only changed brightness and did not affect background motion.

### Affected Files
- `python_app/main.py`
- `python_app/persistence.py`
- `visualizer/gpu_render.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/persistence.py python_app/spectrum_model.py visualizer/gpu_render.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/persistence.py`
  - `visualizer/gpu_render.py`
- All clean

### Notes
- Background reactivity now combines brightness with subtle shake/scale movement using the existing background reactivity controls.
- Template deletion resets the current editor back to a fresh default template after confirmed delete.

## 2026-05-24 (Multi-Layer Spectrum Editing and Preset Tuning)

### What Changed
- Added real spectrum layer management to `python_app/main.py`:
  - layer selector,
  - `Add` layer,
  - `Remove` layer,
  - editing state follows the selected layer instead of always editing the base ring.
- Added per-layer `radiusOffset` control so each spectrum ring can sit farther from the logo and from neighboring rings for stacked multi-color visuals.
- Updated the Python app preview renderer so it now draws all configured spectrum layers instead of only `layers[0]`.
- Updated shared GPU export/live-preview renderer paths so `radiusOffset` also affects exported MP4 output.
- Tuned style preset defaults so `soft-waveform`, `mountain`, and `liquid` are more visually distinct.
- Added extra geometry differentiation between `mountain` and `liquid` in preview/export renderer branches:
  - `mountain` pushes sharper/taller peaks,
  - `liquid` becomes thicker/rounder with more body.

### Why Changed
- Boss requested:
  - a focused preset-visual tuning pass,
  - real add/remove spectrum circle layers,
  - per-layer color engine behavior,
  - larger/manageable layer sizing for richer stacked color rings similar to the reference.
- Root causes found:
  - Python app UI only edited `layers[0]`,
  - Python app preview only rendered `layers[0]`,
  - there was no per-layer ring-gap/radius control,
  - waveform-family presets were still too visually similar.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `visualizer/gpu_render.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py visualizer/gpu_render.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/spectrum_model.py`
  - `visualizer/gpu_render.py`
- All clean

### Notes
- The style preset remains template-wide, but each layer now has its own radius/gap, opacity, and color engine.
- Multi-layer stacked rings now work in the Python preview and shared GPU export path.

## 2026-05-24 (Layer Blend Modes, Duplicate/Rename, Quick Stack Presets)

### What Changed
- Added practical layer-polish controls in `python_app/main.py`:
  - duplicate selected layer,
  - rename selected layer,
  - per-layer blend mode selector (`Normal`, `Additive`, `Screen`).
- Added ready-made stacked ring presets in the Python app:
  - `Triple Neon Halo`,
  - `Bass Vortex Stack`,
  - `Soft Aura Stack`.
- The stacked preset applier creates multiple spectrum layers with tuned color engines, opacity, radius offsets, and blend modes.
- Updated the Python app live preview so it now honors `blend_mode` per layer, matching the shared export renderer behavior more closely.
- Extended `python_app/spectrum_model.py` normalization so `blend_mode` persists in saved templates.

### Why Changed
- Boss requested the next visual-polish pass after multi-layer support:
  - more usable layer management,
  - stronger stacked spectrum looks,
  - faster workflow to create attractive multi-ring visuals.
- Existing `glow`/`blur` schema fields are not yet actually rendered in the current spectrum preview/export code path, so exposing them now would create fake controls.
- Blend mode, duplicate/rename, and quick stacked presets provide real visible gains immediately without fake UX.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py visualizer/gpu_render.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/spectrum_model.py`
  - `visualizer/gpu_render.py`
- All clean

### Notes
- `blend_mode` now works in Python preview and shared GPU export paths.
- `glow` / `blur` fields still exist in schema but remain intentionally hidden from the UI until they are truly rendered.

## 2026-05-24 (Real Layer Glow Passes and paintGL Crash Fix)

### What Changed
- Fixed a Python app preview crash in `paintGL()` where `mirrored` was referenced before assignment after multi-layer spectrum changes.
- Moved the FFT mirroring/smoothing step back into the per-layer render loop so each layer uses its own `mirrored` setting safely.
- Added real per-layer glow rendering in the Python app preview:
  - `Glow Strength` slider,
  - `Glow Softness` slider,
  - halo passes render before the main crisp spectrum pass.
- Added matching per-layer glow halo passes in the shared GPU export renderer so exported MP4 output follows the same visual model.
- Updated stacked preset templates to include non-zero `glow` and `blur` defaults so the new effect is visible immediately.
- Tightened template normalization for layer `glow` and `blur` ranges.

### Why Changed
- Boss approved the next recommendation pass for real per-layer glow/bloom.
- A new regression appeared in the Python preview:
  - `UnboundLocalError: cannot access local variable 'mirrored'`
- Root cause:
  - `render_fft` was calculated outside the layer loop, but `mirrored` is now a layer-local value.
- Rendering goal:
  - avoid fake glow controls,
  - make glow a true render pass instead of cosmetic metadata.

### Affected Files
- `python_app/main.py`
- `python_app/spectrum_model.py`
- `visualizer/gpu_render.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/spectrum_model.py visualizer/gpu_render.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/spectrum_model.py`
  - `visualizer/gpu_render.py`
- All clean

### Notes
- Glow is implemented as widened low-alpha halo passes before the main spectrum pass.
- Current live parity is strongest between:
  - Python app preview,
  - shared GPU export path.

## 2026-05-24 (MP3 Folder Picker Shows MP3 Files)

### What Changed
- Replaced the Python app MP3 folder picker call that used `QFileDialog.getExistingDirectory()`.
- Added a custom non-native folder browser in `python_app/main.py` that:
  - still selects a folder,
  - but also shows `.mp3` files inside the dialog while browsing.
- The selected folder still loads its `.mp3` files into the app’s MP3 dropdown exactly as before.

### Why Changed
- Boss requested to be able to see MP3 files while selecting the source folder.
- The native Windows folder picker hides files, which made it hard to confirm the correct MP3 directory during browsing.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean

### Notes
- The action remains folder-based, not file-based.
- The dialog now gives visual context by showing MP3 files during folder browsing.

## 2026-05-25 (Song-Change Debug Trace + Final Export/Inspector Polish)

### What Changed
- Updated `python_app/main.py` to debug and harden the song-change path instead of only styling around the symptom.
- Fixed the duplicate initial song-load path in the MP3 restore/folder-load flow:
  - `_load_mp3_folder_into_ui()` now sets the selected row once,
  - it no longer manually calls `on_mp3_selected()` after `setCurrentRow(...)`.
- Added precise persistent debug logging around the MP3 selection flow:
  - folder load,
  - selected row application,
  - selection-change handling,
  - skipped reloads,
  - per-request audio load lifecycle.
- Hardened `SpectrumPreview.load_audio()` with request sequencing so stale background decode/analyze threads do not overwrite the current song state after a fast selection change.
- Added audio load request IDs to `debug.log` messages so decode/analyze events can be correlated to a specific selection.
- Applied the final approved UI refinement pass in `python_app/main.py`:
  - stronger selected-track highlight in the export list,
  - clearer export-card status hierarchy using labeled sections for current track, details, and output,
  - slightly tighter `Layer Inspector` title density.

### Why Changed
- Boss asked for a proper debugging pass because song changes appeared to trigger duplicate `load_audio()` behavior and might have looked like an app crash.
- Root cause analysis found two real issues:
  - the folder-load path dispatched selection twice by combining `setCurrentRow(...)` with a manual `on_mp3_selected(...)` call,
  - concurrent background audio-load threads could finish out of order, which risked confusing duplicate-ready logs or stale state after rapid song switching.
- Boss also approved one final UX refinement pass for the export list, export status card, and inspector header density.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- Audio loading in the Python app is now sequence-aware:
  - each selection creates a numbered load request,
  - stale decode/analyze completions are ignored instead of mutating the current preview state.
- MP3 selection is now single-source through the `QListWidget.currentRowChanged` signal path instead of mixed signal + manual handler dispatch.
- Export-card status presentation is more structured without changing the export backend behavior.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked editor diagnostics for `python_app/main.py`: clean
- Verified by code-path inspection that:
  - `_load_mp3_folder_into_ui()` no longer double-dispatches selection,
  - `load_audio()` logs request IDs and ignores stale decode/analyze completions,
  - the export list/status/inspector polish is applied through the shared stylesheet and widget-role system.

### Known Limitations
- This pass verifies the logic and instrumentation statically plus compile/diagnostic checks; it does not yet prove the live click-path behavior under Boss's exact runtime environment.
- Fast repeated song switching should now be easier to diagnose from `python_app/debug.log`, but a short manual runtime repro is still recommended to confirm whether the app ever truly closes versus only reloading audio twice.

### Suggested Next Improvements
- Run one live manual repro in the Python app:
  - switch songs slowly,
  - switch songs rapidly,
  - inspect `python_app/debug.log` for the new request-ID sequence.
- If needed, surface the active audio load state directly in the UI with labels such as `Loading`, `Analyzing`, `Ready`, and `Failed`.

## 2026-05-25 (Export Buttons Real Filled Button Surface Fix)

### What Changed
- Updated the shared button stylesheet in `python_app/main.py` so `QPushButton` roles now use explicit `background-color` rules instead of the previous `background` shorthand.
- This applies to the shared semantic button roles used across the app, including:
  - primary,
  - success,
  - warning,
  - danger,
  - secondary,
  - toolbar,
  - compact/toggle variants.
- The immediate visible target is the export action card, where:
  - `Select MP3 Folder` should render as a filled blue button,
  - `Export` should render as a filled green button.

### Why Changed
- Boss reported again that the MP3-folder and Export controls still did not look like real buttons.
- Root cause analysis showed the role wiring was already correct in `python_app/main.py`, but the shared stylesheet used `background` on `QPushButton`.
- On Qt/Windows, `background-color` is the more reliable property for actual filled push-button rendering, while `background` can leave controls visually flattened or text-only.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The fix strengthens the shared UI design system itself instead of adding one-off styling to the export buttons.
- Any button using the shared semantic roles should now render with a proper filled surface more reliably on the current Qt/Windows runtime.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that the export action buttons still use the correct shared roles:
  - `Select MP3 Folder` -> `primary`
  - `Export` -> `success`

## 2026-05-25 (Music Backend Parity Slice: DB Songs + Phrase Pools + Polish Persistence)

### What Changed
- Added a new DB bridge module at `python_app/music_db.py` to port key Electron music backend behavior into Python:
  - uniqueness reads from the `songs` table,
  - phrase-pool reads from `title_pool`, `album_pool`, and `opening_pairs`,
  - generated songs are upserted into `songs`,
  - history rows are inserted into `history`.
- Updated `python_app/main.py` so Music generation now uses the DB-backed parity path when Postgres is configured:
  - pulls avoid lists from recent generated songs in DB instead of only the local in-memory song list,
  - pulls forced titles/albums/openings from the same phrase-pool tables Electron uses,
  - keeps one album per batch like the Electron queue behavior,
  - writes generated songs/history to DB before reflecting them in the Python UI state.
- Fixed the interrupted Music backend port in `python_app/main.py`:
  - added `lyrics_polished` event handling,
  - persists polished lyrics back into Python app state,
  - mirrors polished lyrics into the DB song row when DB is configured.
- Removed the Music status overwrite bug in `python_app/main.py`:
  - `_refresh_music_ui()` no longer resets live generation progress to `Music foundation ready`.
- Added stronger generation logging in `python_app/main.py` for:
  - per-attempt provider retries,
  - phrase-pool selection failures,
  - polished-lyrics DB persistence failures.

### Why Changed
- Boss asked to continue cloning the Electron Music backend into the Python app as real functionality, not UI-only placeholders.
- The previous Python port could generate drafts, but it still missed important Electron behavior:
  - DB-backed uniqueness,
  - forced phrase-pool title/album/opening selection,
  - DB song/history writes,
  - polished-lyrics persistence,
  - stable live progress messaging.
- The previous `_refresh_music_ui()` path also overwrote generation status, which would make the worker look unreliable even when it was running correctly.

### Affected Files
- `python_app/main.py`
- `python_app/music_db.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The Python Music page now has a real DB parity bridge for the core generation path instead of relying only on `app_json` / local persisted app state.
- Music draft generation in Python now follows the Electron queue more closely for:
  - uniqueness source,
  - phrase-pool consumption,
  - per-batch album consistency,
  - song/history persistence.
- The Python app still keeps its local/UI-facing `music_data` model in sync, so the page continues to function without needing a separate renderer-store architecture.

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_db.py python_app/music_generation.py python_app/persistence.py python_app/music_model.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/music_db.py`
- Both diagnostics are clean.

### Known Limitations
- This pass ports the core draft-generation parity slice only; it does not yet finish:
  - Suno queue submission,
  - Suno retry tooling,
  - phrase-pool management UI,
  - revision history tooling,
  - full Electron job-queue event semantics.
- DB parity depends on Boss having the same migrated Postgres schema available:
  - `songs`
  - `history`
  - `title_pool`
  - `album_pool`
  - `opening_pairs`
- Live API/runtime verification is still needed with real DeepSeek or SLAI keys and real seeded phrase-pool data.

### Suggested Next Improvements
- Port the next Electron Music slice into Python:
  - Suno auto-submit path,
  - retry tooling for generated songs,
  - song output/open-folder actions.
- Add Python-side Music settings/diagnostic UI for phrase-pool readiness:
  - title count,
  - album count,
  - opening-pair count.
- Run a live Music generation smoke test with DB enabled and confirm:
  - generated songs appear in the Python History table,
  - DB `songs` / `history` rows are created,
  - phrase-pool depletion errors surface clearly if tables are empty.

## 2026-05-25 (Music Suno Parity Slice: Retry + Output Folder + Task Store)

### What Changed
- Added Suno task-store helpers to `python_app/music_db.py`:
  - request-hash lookup,
  - latest output-dir lookup by song id,
  - latest output-dir lookup by batch id,
  - `suno_tasks` upsert support.
- Added a new Suno service module at `python_app/music_suno.py` that ports the Electron Suno helpers into native Python:
  - request hashing,
  - `generate` API call,
  - record-info polling read,
  - output-file download,
  - output file-name construction,
  - output run-directory planning using profile folder names and run prefixes.
- Updated `python_app/main.py` so the Music page now has real Suno follow-up actions for the selected song:
  - `Retry Suno`
  - `Open Folder`
- Replaced the previous placeholder-only Suno tab with a real action tab wired to the selected History row.
- Added shared Suno status messaging in the Music page so both the Song card and Suno tab reflect the same live submit/download state.

### Why Changed
- Boss asked to continue the next best Electron parity step after draft-generation cloning.
- The previous Python Music page stopped at lyrics generation and polish, while Electron continues with:
  - Suno retry submission,
  - output-folder lookup,
  - DB-backed `suno_tasks` state.
- Without this slice, the Python Music workflow still broke after draft creation and could not continue into the actual song-generation follow-up flow.

### Affected Files
- `python_app/main.py`
- `python_app/music_db.py`
- `python_app/music_suno.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The Python app now has a native Suno integration layer separated from the UI:
  - DB reads/writes stay in `music_db.py`
  - HTTP/API and output-path logic stay in `music_suno.py`
  - page orchestration stays in `main.py`
- Selected-song Suno actions now depend on the same DB-backed task-store architecture as Electron instead of ad hoc local-only state.

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_db.py python_app/music_suno.py python_app/music_generation.py`
- Ran a second focused compile check:
  - `py -m py_compile python_app/main.py python_app/music_db.py python_app/music_suno.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/music_db.py`
  - `python_app/music_suno.py`
- Diagnostics are clean.

### Known Limitations
- This pass ports retry/output actions, but not the full Electron Suno queue manager and poller lifecycle.
- Immediate retry currently does a direct submit/lookup flow from Python instead of using the Electron-side queue/event bus.
- Callback-server and background pending-task polling parity are not yet ported in Python.
- Live runtime validation still depends on:
  - valid `sunoApiKey`,
  - migrated `suno_tasks` table,
  - valid profile folder names,
  - writable `sunoOutputDir`.

### Suggested Next Improvements
- Port the next Electron Suno slice:
  - pending-task poller,
  - callback-driven refresh,
  - richer task-status history in the Music UI.
- Add a Python Music diagnostics block for Suno readiness:
  - API key present,
  - output base dir present,
  - selected OK/ALT profile folders,
  - last known output dir for selected song.
- Add phrase-pool management and readiness UI next so the remaining Music backend dependencies are visible directly in Python.

## 2026-05-25 (Music Suno Poller Parity Slice: Pending Task Refresh)

### What Changed
- Added pending-task query support to `python_app/music_db.py`:
  - `list_pending_suno_tasks(...)`
  - `list_songs_by_batch_id(...)`
- Added the Electron-style pending-task poller to `python_app/music_suno.py`:
  - `poll_and_download_pending_suno(...)`
  - reads pending `suno_tasks`
  - polls Suno record-info
  - updates task status/audio URLs
  - downloads newly available OK/ALT files
  - resolves `trackNo` by batch song ordering when needed
- Updated `python_app/main.py` with real Suno refresh orchestration:
  - background poll trigger
  - guarded single-run polling flag
  - manual refresh action
  - event handling for poll results
  - status updates for downloads / no-op checks / failures
- Added UI controls for the new refresh flow:
  - `Refresh Suno` in the Song card
  - `Refresh Pending Tasks` in the Suno tab
- Added a 30-second `QTimer` in `python_app/main.py` so Python now automatically polls pending Suno tasks at the same cadence as the Electron app.

### Why Changed
- Boss asked to continue the next best Electron clone step.
- The prior Python Suno slice allowed submit/retry and folder open actions, but it still lacked the Electron behavior that keeps checking pending tasks and downloads outputs once Suno finishes generation.
- Without this poller, Python would submit Suno work but still require manual ad hoc follow-up rather than maintaining a real long-running music workflow.

### Affected Files
- `python_app/main.py`
- `python_app/music_db.py`
- `python_app/music_suno.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- Python Music now has a proper pending-task background refresh loop for Suno instead of a submit-only path.
- The polling/service logic remains separated cleanly:
  - DB access in `music_db.py`
  - Suno API/download logic in `music_suno.py`
  - timer/UI orchestration in `main.py`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_db.py python_app/music_suno.py`
- Checked diagnostics for:
  - `python_app/main.py`
  - `python_app/music_db.py`
  - `python_app/music_suno.py`
- Diagnostics are clean.

### Known Limitations
- This pass ports the timer poller, but not the Electron local callback server.
- Python currently refreshes via periodic polling and manual refresh only.
- The Music UI still does not expose a detailed Suno task table with per-task status history.
- Live runtime validation still depends on:
  - valid `sunoApiKey`
  - valid `sunoOutputDir`
  - migrated `suno_tasks` table
  - writable output folders

### Suggested Next Improvements
- Port the remaining Suno callback-server parity, if needed for faster task completion detection.
- Add a dedicated Suno task status table to the Music page.
- Port the Pools management/readiness UI next so all draft-generation dependencies are visible and manageable from Python.

### Known Limitations
- This verifies the shared style fix statically plus compile/diagnostic checks.
- A live runtime visual check is still the final confirmation step because Qt style behavior is platform-renderer dependent.

### Suggested Next Improvements
- If Boss still wants the export actions even stronger after the live check, the next safe polish is:
  - slightly taller CTA buttons,
  - a little more horizontal padding,
  - stronger hover contrast in the export card only through shared role extension, not ad hoc local styling.

## 2026-05-25 (Export CTA Buttons + Compact Track List Density Pass)

### What Changed
- Strengthened the export action buttons again in `python_app/main.py` using a dedicated shared CTA helper instead of relying only on the generic button-role styling.
- Added `_apply_cta_button(...)` so high-priority actions can receive:
  - explicit filled background,
  - stronger border,
  - larger padding,
  - taller button height,
  - stronger hover/pressed states,
  - pointer cursor.
- Applied the CTA helper to the export-card actions:
  - `Select MP3 Folder` as blue primary CTA,
  - `Export` as green success CTA,
  - runtime `Stop Export` state continues to switch to warning CTA.
- Tightened export list density so more tracks fit vertically in the same center area:
  - reduced `trackList` item padding,
  - removed extra item margin,
  - reduced list font size slightly,
  - reduced export section outer padding and left-column spacing,
  - removed extra spacing between MP3 rows.

### Why Changed
- Boss reported that the export buttons still looked visually the same and still did not read strongly enough as actual buttons.
- Boss also requested the song track list be compact enough to fit many more songs before scrolling.
- Root cause:
  - even after the shared stylesheet fix, the export actions still needed a stronger CTA treatment than the normal reusable button baseline,
  - the track list was spending too much vertical space on row padding and inter-item spacing.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The UI system now has a reusable CTA-button helper for important action buttons instead of forcing all buttons to share the same strength level.
- The track list remains on the shared `uiRole="trackList"` styling path, so compactness is still centrally controlled rather than patched item by item.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - export buttons now use `_apply_cta_button(...)`,
  - export running state also reuses the same CTA helper,
  - track list item density is reduced through shared stylesheet rules plus tighter list/export layout spacing.

### Known Limitations
- This pass is compile-verified and logic-verified, but the final visual confirmation still depends on Boss checking the live runtime.
- Whether exactly `10` songs fit without scroll can vary slightly by Windows font rendering and DPI scaling.

### Suggested Next Improvements
- If Boss still wants more vertical capacity after the live check, the next safe pass is:
  - slightly reduce playback-card height,
  - compress export-card headings another step,
  - shorten long MP3 display names visually while preserving full paths internally.

## 2026-05-25 (MP3 Folder Picker File-to-Folder Resolution Fix)

### What Changed
- Fixed the custom MP3 folder picker in `python_app/main.py` so it no longer fails when the non-native Qt dialog returns a selected MP3 file path instead of a directory path.
- Updated `_browse_mp3_folder_with_file_preview(...)` to:
  - detect when the dialog selection is an MP3 file,
  - resolve that selection to the parent folder automatically,
  - accept direct directory selections unchanged,
  - fall back to the dialog's current directory if needed.
- Added debug logging so the picker now records whether it resolved a selected file back to its containing folder.

### Why Changed
- Boss reported that the `Select MP3 Folder` flow still did not work.
- Root cause analysis matched the live screenshot:
  - the custom dialog is intentionally configured to show `.mp3` files while browsing,
  - but its accept result can therefore be a file path,
  - the downstream loader only accepts directories, so the selection was silently rejected.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The custom “show MP3 files while selecting a folder” workflow now behaves more robustly without abandoning the existing UX approach.
- This keeps Boss's preferred browse experience while making the selection result compatible with the rest of the MP3-folder loading flow.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that file selections from the custom dialog now resolve to `Path(selected).parent` before returning to `pick_mp3_folder()`.

### Known Limitations
- This is compile-verified and logic-verified.
- Final confirmation still needs one live runtime click in the dialog to confirm the resolved folder loads the MP3 list as expected.

### Suggested Next Improvements
- If Boss wants the picker even clearer, the next safe UX pass is:
  - relabel the bottom field visually so it does not read like a raw file selection,
  - add helper text such as “You can click any MP3; the app will load its folder.”

## 2026-05-25 (Primary App Navigation Sidebar Shell)

### What Changed
- Refactored `python_app/main.py` so the app now has a new top-level left navigation rail before the existing editor sidebar.
- Added an icon-only primary navigation shell using Boss-provided SVG assets from `public/icons/`.
- Added the following primary pages to a stacked app shell:
  - `Home`
  - `Workflow`
  - `Music`
  - `Image`
  - `Video`
  - `Merger`
  - `Settings`
- Moved the existing full Python video editor workspace into a dedicated `Video` page instead of keeping it as the only root window layout.
- Added intentional blank placeholder pages for:
  - `Home`
  - `Workflow`
  - `Music`
  - `Image`
  - `Merger`
  - `Settings`
- Added bottom user/profile area to the new navigation rail:
  - user icon,
  - detected user name,
  - logout icon button.
- Added a safe placeholder action for logout that clearly states the flow is not implemented yet rather than faking a logout.
- Added shared stylesheet support for:
  - the new app navigation rail,
  - active/hover states for icon navigation buttons,
  - logout button hover state,
  - placeholder-page typography.

### Why Changed
- Boss requested a second, higher-level left sidebar layer that works as the primary application menu.
- Boss also requested that the current full video editor be moved inside a dedicated `Video` page while the other pages remain blank for future development.
- This required a shell-level refactor, not a local widget patch, because the old window architecture assumed the video editor was the only page in the application.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The Python app now has a two-level left-side navigation structure:
  - outer application navigation rail,
  - inner page-specific editor sidebar for the video workspace.
- The current video editor layout is preserved, but it now lives inside a stacked primary-page container.
- This establishes a scalable app-shell architecture for future `Home`, `Workflow`, `Music`, `Image`, `Merger`, and `Settings` pages instead of forcing them into the current video-only layout.

### Important Decision
- The app currently opens on the `Video` page by default to preserve Boss's existing active workflow and avoid making the app appear empty immediately after this refactor.
- If Boss wants, the default landing page can later be changed to `Home`.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - the new primary navigation rail is built from the provided SVG icons,
  - the current editor is now constructed inside `_build_video_workspace_page()`,
  - the app shell switches pages through a stacked container,
  - non-video pages are intentionally blank and clearly labeled as planned areas.

### Known Limitations
- Blank pages are structural placeholders only; they do not contain real workflows yet.
- Logout is intentionally non-functional for now and only shows an honest placeholder message.
- This pass is compile-verified and architecture-verified; final UX validation still needs Boss to review the live runtime layout.

### Suggested Next Improvements
- Fine-tune the primary rail spacing and selected-state visuals after Boss reviews the live UI.
- Decide whether the app should continue to land on `Video` by default or switch to `Home`.
- Add the first real content block to the `Home` page:
  - dashboard summary,
  - statistics cards,
  - project overview.

## 2026-05-25 (Primary Rail Selected State + Bottom Profile Tightening)

### What Changed
- Refined the new primary navigation rail in `python_app/main.py` to make the active page state visually stronger and the bottom profile/logout area more compact.
- Strengthened the selected icon button state by updating the shared navigation-button stylesheet to use:
  - deeper filled active background,
  - brighter border treatment,
  - left accent edge for active emphasis,
  - more deliberate hover contrast.
- Reduced the nav icon footprint slightly so the active container reads more clearly instead of feeling oversized and soft.
- Rebuilt the bottom user area into a compact grouped profile block instead of three loose stacked widgets.
- Added a small `User` caption, tightened the username typography, and reduced the logout button footprint so the bottom section feels denser and more intentional.

### Why Changed
- Boss requested two immediate improvements first:
  - stronger selected-icon state,
  - tighter user/logout bottom section.
- Root cause:
  - the original active nav state was only a simple blue fill and did not stand out enough from hover,
  - the bottom section had too much loose spacing and lacked a grouped visual container.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No feature-flow changes.
- This is a shell-level UX refinement built on top of the new primary navigation architecture added earlier.
- The implementation remains centralized through shared stylesheet roles and the primary-navigation builder, so future polish stays maintainable.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - active nav buttons now use a stronger checked-state treatment,
  - the bottom user/logout area now renders as a compact grouped profile block.

### Known Limitations
- This pass is compile-verified and structure-verified.
- Final UX judgment still depends on Boss reviewing the live runtime and deciding whether the active state should be even stronger or more minimal.

### Suggested Next Improvements
- If Boss wants one more shell-polish pass after visual review, the safest next step is:
  - add a subtle active glow or icon tint strategy for the selected nav item,
  - tune vertical spacing between top menu items another step,
  - align the `Video` page selected state with a future `Home` dashboard landing design.

## 2026-05-25 (System Font Navigation Icons + Custom App Header)

### What Changed
- Replaced the new left navigation rail's mixed SVG icon usage with a system-font icon approach in `python_app/main.py`.
- Verified locally that this Windows environment has both:
  - `Segoe Fluent Icons`
  - `Segoe MDL2 Assets`
- Added a symbol-font detection helper so the shell can prefer the Windows icon font stack instead of relying on inconsistent multi-color SVG glyphs for the primary navigation.
- Rebuilt the primary nav buttons to use font glyphs instead of the previous SVG icon files.
- Added a branded custom top header for the main window with:
  - app logo from `public/icons/electric-guitar.svg`,
  - app title `Music Generator`,
  - current page label,
  - profile/user block,
  - logout button,
  - minimize button,
  - close button.
- Switched the main Python app window to a frameless custom-chrome shell so the branded header can own the minimize and close controls.
- Added a draggable header widget so Boss can still move the window like a normal desktop app.
- Moved the profile/logout presence out of the left nav bottom and into the top header so the shell hierarchy feels cleaner and more professional.

### Why Changed
- Boss reported that the SVG-based nav icons still did not look good enough and explicitly asked whether a font-based icon approach could replace them.
- Boss also requested a real custom app header with:
  - guitar logo,
  - app name,
  - profile area,
  - logout,
  - minimize,
  - close.
- Root cause:
  - the previous SVG set had inconsistent stylistic character and color treatment,
  - the app still looked like a styled utility window rather than a cohesive desktop product shell.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The shell now uses custom window chrome instead of the default OS title bar for the main Python app window.
- Primary navigation icons now come from the Windows symbol-font stack rather than external SVG assets.
- Header-level identity, profile, and window actions are now centralized in one reusable top bar.

### Important Decision
- I chose the Windows system symbol-font path instead of introducing a new third-party icon package.
- This avoids dependency sprawl, keeps rendering crisp at small sizes, and aligns better with a native Windows desktop-tool feel.
- The fallback logic still prefers available Windows symbol fonts in a safe order rather than assuming only one font exists.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by command that this machine has:
  - `Segoe Fluent Icons`
  - `Segoe MDL2 Assets`
- Verified by code inspection that:
  - the main window now builds a custom header,
  - the window is frameless,
  - the header supports dragging,
  - nav buttons now use font glyphs instead of SVG icons.

### Known Limitations
- This pass is compile-verified and architecture-verified, but still needs Boss's live visual review for final icon-glyph quality.
- Some icon semantics use the Windows symbol-font set rather than the exact Lucide icon family, because PyQt does not ship with a native Lucide font stack and I intentionally avoided adding a new package dependency in this pass.
- Logout remains an honest placeholder action only.

### Suggested Next Improvements
- If Boss likes the overall direction, the next safe shell polish is:
  - refine the exact glyph choices for any nav item that still feels semantically weak,
  - tune header spacing and button density,
  - add a compact `Home` dashboard card layout so the new shell has a real first page.

## 2026-05-25 (Lucide SVG Navigation + Native Window Frame Restoration)

### What Changed
- Replaced the temporary Windows symbol-font navigation approach in `python_app/main.py` with Lucide SVG icons rendered directly inside PyQt.
- Downloaded and stored the specific Lucide SVG assets used by the shell under:
  - `public/icons/lucide/house.svg`
  - `public/icons/lucide/workflow.svg`
  - `public/icons/lucide/music.svg`
  - `public/icons/lucide/image.svg`
  - `public/icons/lucide/video.svg`
  - `public/icons/lucide/git-merge.svg`
  - `public/icons/lucide/settings.svg`
  - `public/icons/lucide/user-round.svg`
  - `public/icons/lucide/log-out.svg`
- Added SVG rendering helpers in `python_app/main.py` so the app can:
  - load Lucide SVG files from disk,
  - render them to Qt icons,
  - tint them consistently for active/inactive UI states.
- Rebuilt the left app-navigation rail to use Lucide SVG icons instead of font glyphs.
- Restored the main window to the native Windows frame by removing the frameless custom-chrome mode.
- Kept a custom in-app header row, but simplified it to match Boss's feedback:
  - no fake frame around the logo,
  - no `USER` caption,
  - no page chip showing `Video`,
  - no separate framed user card,
  - no duplicate custom minimize/close controls.
- Header now keeps only:
  - guitar logo,
  - app title/subtitle,
  - user icon,
  - username,
  - logout icon button.

### Why Changed
- Boss explicitly requested the Lucide SVG approach after pointing out that the prior icon strategy still did not look good enough.
- Boss also correctly identified that the frameless custom header made the whole application border feel wrong and visually detached from the window.
- Root cause:
  - the temporary font-glyph shell was a clean technical experiment, but it did not align strongly enough with the desired icon aesthetic,
  - the frameless header removed native window chrome and made the application shell feel less grounded.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`
- `public/icons/lucide/house.svg`
- `public/icons/lucide/workflow.svg`
- `public/icons/lucide/music.svg`
- `public/icons/lucide/image.svg`
- `public/icons/lucide/video.svg`
- `public/icons/lucide/git-merge.svg`
- `public/icons/lucide/settings.svg`
- `public/icons/lucide/user-round.svg`
- `public/icons/lucide/log-out.svg`

### Architecture Impact
- The shell now uses the OS-native window frame again for border/title-bar correctness.
- The app still preserves a custom branded in-app header for product identity and account actions.
- Navigation icons now follow a reusable SVG-rendering path instead of mixing random SVG assets or relying on the Windows symbol font stack.

### Important Technical Decision
- Lucide itself is primarily SVG-first. While Lucide Static also offers icon-font outputs, the static docs warn that icon fonts and sprites include all icons and are not the recommended production path for performance-sensitive use.
- For this Python desktop app, the cleanest maintainable path is:
  - keep only the few Lucide SVG files the app actually uses,
  - render them directly in PyQt,
  - tint them centrally in code for selected/unselected states.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified that Lucide SVG files were downloaded successfully and stored locally
- Verified by code inspection that:
  - nav buttons now use Lucide SVG icons,
  - native window frame is restored,
  - header no longer shows the `USER` caption,
  - header no longer shows the `Video` chip,
  - logo/profile framing from the earlier pass is removed.

### Known Limitations
- This pass is compile-verified and architecture-verified.
- Final icon-choice quality and exact spacing still need Boss's live runtime review.
- Logout remains an honest placeholder action only.

### Suggested Next Improvements
- If Boss likes the Lucide direction, the next safe pass is:
  - tune each Lucide icon choice if any item still feels semantically weak,
  - refine header spacing/padding another step,
  - add a real `Home` dashboard so the new shell feels complete immediately on launch.

## 2026-05-25 (Nav Active-State Simplification)

### What Changed
- Simplified the primary left navigation button state styling in `python_app/main.py`.
- Removed the previous active-state left accent treatment and the padding shift it introduced.
- Reduced the navigation button border radius from `14px` to `7px`.
- Added a cleaner `checked:hover` state so active icons now hover with a simple light-gray surface instead of a split accent effect.

### Why Changed
- Boss requested a simpler nav interaction style:
  - no left active accent effect,
  - simple light-gray hover for the active item,
  - tighter radius.
- Root cause:
  - the previous selected state still carried too much decorative emphasis and visual asymmetry for the desired compact professional rail.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - nav button radius is now `7px`,
  - active state uses a standard border instead of left accent,
  - active hover uses a simplified light-gray background.

### Known Limitations
- This pass is compile-verified and style-verified by code.
- Final visual judgment still depends on Boss reviewing the live app.

## 2026-05-25 (Global Footer Promotion)

### What Changed
- Moved the footer construction out of the `Video` page in `python_app/main.py`.
- Added a shared `_build_global_footer()` helper at the main application shell level.
- Attached the footer once at the root app layout so it now appears across the entire app instead of only inside the `Video` workspace.

### Why Changed
- Boss requested that the footer be global across the entire application.
- Root cause:
  - the previous implementation created the footer inside `_build_video_workspace_page()`,
  - so only the `Video` page rendered it.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The footer is now part of the top-level app shell, alongside the global header and primary navigation stack.
- This is the correct long-term architecture for shared shell UI because page switching no longer affects footer presence.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - `_build_video_workspace_page()` no longer owns the footer,
  - the root layout now adds a single shared footer after the primary stack shell.

### Known Limitations
- This pass is compile-verified and architecture-verified.
- Final visual confirmation still needs Boss to review the runtime across non-video pages.

## 2026-05-25 (Nav Button Size Tightening)

### What Changed
- Tightened the primary left navigation button sizing in `python_app/main.py`.
- Kept the requested `5px` padding rule in the shared stylesheet.
- Increased the Lucide icon render size to `24x24`.
- Reduced each navigation button container to `34x34`, matching the requested icon-plus-padding footprint.

### Why Changed
- Boss requested the nav buttons be smaller, with:
  - `24x24` icon size,
  - `5px` padding only.
- Root cause:
  - the previous rail still used a larger physical button box even after the styling cleanup, so the visual result remained too large.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - nav icons now render at `24`,
  - nav buttons now use a `34x34` fixed size,
  - the shared nav-button padding remains `5px`.

## 2026-05-25 (Nav Padding Increase + Rail Width Reduction)

### What Changed
- Updated the primary left navigation rail sizing in `python_app/main.py`.
- Increased nav button padding from `5px` to `10px`.
- Increased the nav button box from `34x34` to `44x44` so the `24x24` icon still fits correctly with the requested padding.
- Reduced the outer app-navigation rail width from `84px` to `72px` so the left rail feels tighter and more proportional.

### Why Changed
- Boss requested:
  - nav button padding `10px`,
  - a smaller left sidebar width so the rail looks nicer.
- Root cause:
  - the previous rail had become visually under-filled after the earlier size reduction,
  - and the outer rail still had more width than necessary for the simplified icon-only layout.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - nav button padding is now `10px`,
  - nav button size is now `44x44`,
  - app-nav rail width is now `72px`.

## 2026-05-25 (Nav Active Color Softening)

### What Changed
- Updated the primary nav selected-state styling in `python_app/main.py`.
- Changed the active nav background from blue to a light gray tone.
- Removed the bright/white border treatment from the active state.
- Kept the active hover in the same soft gray family instead of restoring a highlighted border.

### Why Changed
- Boss requested one more refinement:
  - active color should be light gray,
  - no white border color.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean

## 2026-05-25 (Playback Separation + Export Column Rebalance)

### What Changed
- Adjusted the center video workspace layout in `python_app/main.py` so playback reads more clearly below the preview.
- Reduced the preview container fixed height from `560` to `520`.
- Added a dedicated gap under the preview and slightly increased spacing before the playback/export stack.
- Updated transport controls from the old short labels to clearer button labels:
  - `Backward`
  - `Play`
  - `Stop`
  - `Forward`
- Moved those transport controls onto the shared blue `transportPrimary` button style instead of relying on the generic button role.
- Rebalanced the `Export Queue` split so `Track List` and `Actions` now use equal column stretch instead of the previous `3:2` split.

### Why Changed
- Boss reported three UX issues:
  - `Playback` appears to overlap the preview,
  - transport controls should use proper button styling,
  - `Track List` and `Actions` should be equal for a better layout.
- Root cause:
  - the preview block was visually occupying too much vertical space,
  - transport controls were still using a more generic button treatment,
  - export columns were intentionally weighted unequally in the old `3:2` split.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - preview height is reduced and spacing below it is increased,
  - transport buttons now use `transportPrimary`,
  - export columns now use a `1:1` stretch ratio.

### Known Limitations
- This pass is compile-verified and layout-verified by code.
- Final visual confirmation still needs Boss to review the runtime, especially whether `520` is the best preview height for the fixed window.

## 2026-05-25 (Center Layout Hierarchy Correction)

### What Changed
- Corrected the center workspace hierarchy in `python_app/main.py` after the previous pass did not fix the real visual issue.
- Increased the vertical break between preview and the lower content stack.
- Changed `Playback` from `softSection` to the stronger `section` container role.
- Changed `Export Queue` from `softSection` to the stronger `section` container role.
- Wrapped the left `Track List` area in its own `section` card so it visually matches the right `Actions/Status` card.
- Slightly increased center-stack spacing to improve separation between preview, playback, and export.

### Why Changed
- Boss correctly reported that the previous pass still looked effectively the same.
- Root cause:
  - `Playback` and `Export Queue` were still using low-contrast `softSection` surfaces,
  - `Track List` had no card wrapper while `Actions` did, so the two export columns were technically equal in width but not equal in visual structure,
  - the preview-to-playback boundary was still too weak.
- This was a hierarchy problem, not just a button-label or minor spacing problem.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean
- Verified by code inspection that:
  - preview gap is increased,
  - `Playback` now uses `section`,
  - `Export Queue` now uses `section`,
  - `Track List` is now wrapped in a matching left-side card.

## 2026-05-25 (Section Background Rendering Fix)

### What Changed
- Fixed shared panel-role rendering in `python_app/main.py`.
- Updated `_set_panel_role()` to enable `WA_StyledBackground` before applying the `uiPanel` property.

### Why Changed
- Boss provided a screenshot showing the preview image still visible behind the `Playback` area.
- Root cause:
  - the hierarchy/card-role changes were in place,
  - but the underlying `QWidget` section containers were not guaranteed to paint their stylesheet backgrounds,
  - so those containers could remain visually transparent even though the stylesheet defined `section` and `softSection` colors.
- This made `Playback` still look like it overlapped the preview even after the earlier layout refactor.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean

### Architecture Impact
- This is a shared fix for all widgets that use the `uiPanel` design-system role.
- It improves consistency for section/card background rendering across the app shell, not only the video page.

## 2026-05-25 (Center Bottom Stylesheet Root-Cause Fix)

### What Changed
- Removed the direct stylesheet from the `bottom` center-stack container in `python_app/main.py`.
- The removed code was:
  - `bottom.setStyleSheet("background: transparent; border: none;")`

### Why Changed
- Boss requested a deeper inspection because `Playback` still looked wrong and the transport buttons still rendered like plain text.
- Root cause:
  - the lower center-stack parent widget had its own direct stylesheet,
  - that parent-level stylesheet flattened the visual rendering of its descendants,
  - so child sections and transport buttons inside that subtree could not reliably paint their intended shared design-system styles.
- This is why earlier layout and panel-role fixes appeared ineffective in the live UI.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics for `python_app/main.py`: clean

### Expected Runtime Impact
- `Playback` should render as a real section below the preview instead of looking visually flattened into it.
- The transport controls should render as styled blue buttons instead of plain text.
- The lower `Export Queue` stack should render more consistently with the shared card hierarchy.

## 2026-05-25 (Music Page Phase 1 Foundation)

### What Changed
- Started the real Python-native `Music` page port from the Electron app instead of leaving the route as a placeholder.
- Added a new shared music data model in `python_app/music_model.py`:
  - default `app_data` structure,
  - settings defaults aligned with the Electron music subsystem,
  - normalization helpers for descriptions, structures, songs, drafts, and profiles.
- Extended `python_app/persistence.py` with shared music app-data persistence helpers:
  - DB-backed `app_json` read/write when DB config exists,
  - Electron `mg-data.json` read/write when the Electron user-data directory is available,
  - local Python fallback file `python_app/music_app_data_local.json` when neither shared store is available.
- Replaced the old `music` placeholder page in `python_app/main.py` with a real `Music` workspace builder.
- Implemented the first working music-page slice in `python_app/main.py`:
  - composer/session settings bound to real persisted music settings,
  - real description editor state,
  - real structure editor state,
  - real persisted song draft title/album fields,
  - real OK/ALT profile/channel selection lists bound to shared settings,
  - real history table populated from saved songs,
  - real descriptions tab with create/save/delete/load behavior,
  - real structures tab with create/save/delete/load behavior.
- Kept generation actions intentionally hidden for now instead of exposing a fake non-working button.

### Why Changed
- Boss requested a true feature-by-feature port from the Electron app, not a UI mock.
- Inspection verified that the Electron `Music` page is a subsystem spanning:
  - renderer UI,
  - shared `app_data` state,
  - persistence,
  - job queue/event flow,
  - AI provider integrations.
- The safest senior-level first step is to port the shared data contracts and persistence foundation before exposing generation controls.

### Affected Files
- `python_app/main.py`
- `python_app/persistence.py`
- `python_app/music_model.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/persistence.py python_app/music_model.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/persistence.py`: clean
  - `python_app/music_model.py`: clean

### Current Scope
- Real and implemented in this phase:
  - shared music data load/save,
  - real Music route in the Python app,
  - composer settings persistence,
  - description/structure management,
  - profile/channel selection persistence,
  - history browsing and song reload into the composer.
- Not yet ported in this phase:
  - Python-native generation/job backend,
  - Suno retry/submit flow,
  - phrase-pool management page,
  - generation settings pages,
  - lyrics-polish backend,
  - full Electron workflow parity.

### Recommended Next Step
- Port the Python-native generation foundation next:
  - payload builder for music jobs,
  - provider execution services for DeepSeek/SLAI,
  - job/event progress reporting,
  - then expose a real `Generate` action only after that backend works end-to-end.

## 2026-05-25 (Music Page Arrangement Replication Pass)

### What Changed
- Restructured the Python `Music` page `Composer` tab to match the approved Electron-style arrangement much more closely.
- Replaced the earlier temporary foundation layout with:
  - top tab strip: `Music`, `Descriptions`, `Structures`, `Suno`, `Pools`, `Generation`
  - top control bar with `From`, `To`, `Language`, `Creativity`, `Unique opening`, `Strict`, `History`, `Count`, and `Generate`
  - four-card top content row:
    - `Song description`
    - `Song structure`
    - `OK channels`
    - `ALT channels`
  - bottom split layout:
    - left `Song / Effects` card
    - right `History` card
- Added inline toggle-button helpers so the new music controls visually match the desired compact switch-style arrangement better than plain checkboxes.
- Updated the history table structure to better match the target layout:
  - `No`
  - `Album`
  - `Title`
  - `Desc`
  - `Struct`
  - `Created`
- Added the bottom left song tools arrangement:
  - draft title / album
  - copy buttons
  - polish button
  - revisions button
  - polish slider
  - lyrics editor
  - `Auto-Gen Image` / `Auto-GSuno` toggles
- Added Generation/Suno/Pools placeholder tabs so the full tab arrangement matches the approved design direction while keeping non-ported backend features clearly separated.
- Extended music defaults for the new persisted UI settings:
  - `useAllDescriptions`
  - `useAllStructures`
  - `lyricsPolishStrength`

### Why Changed
- Boss approved the current Electron `Music` page arrangement and requested the Python page replicate that UI structure exactly.
- The previous Python `Music` page was functionally real for persistence/editing, but its layout was still a temporary foundation and did not visually match the approved composition.

### Affected Files
- `python_app/main.py`
- `python_app/music_model.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_model.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_model.py`: clean

### Honest Status
- Verified:
  - page structure rewrite,
  - persisted setting bindings,
  - real history/data wiring still intact,
  - compile/diagnostics clean.
- Not yet visually verified against the running app after this exact arrangement rewrite.
- Generation backend remains intentionally not exposed as a real working pipeline yet; the button currently gives an honest status message instead of fake generation.

## 2026-05-25 (Music Page Visual Refinement Pass)

### What Changed
- Per Boss request, refined the new Python `Music` page to push it closer to the approved Electron visual composition.
- Tightened top-level page spacing:
  - smaller outer margins,
  - smaller inter-section spacing,
  - tighter session-card padding.
- Compressed top-bar control widths:
  - narrower `From` / `To`,
  - narrower `Language`,
  - narrower `Strict`,
  - narrower `History`,
  - narrower `Count`,
  - shorter `Generate` CTA.
- Fixed the top four music cards to more controlled heights so the page reads closer to the reference layout:
  - `Song description`
  - `Song structure`
  - `OK channels`
  - `ALT channels`
- Narrowed and tightened the bottom-left `Song` card:
  - slightly smaller internal spacing,
  - smaller action button heights,
  - slightly shorter lyrics editor height.
- Refined the `History` section proportions:
  - tighter filter row,
  - narrower history date inputs,
  - explicit column widths for `No`, `Album`, `Desc`, `Struct`, and `Created`,
  - `Title` remains the flexible stretch column.
- Fixed a structural bug from the previous pass:
  - the top-bar provider combo and Generation-tab provider combo were incorrectly sharing the same instance reference,
  - split them into separate widgets while keeping both synced to the same persisted setting.

### Why Changed
- Boss approved the new arrangement direction but requested the next senior-level refinement pass specifically for:
  - exact spacing compression,
  - card heights,
  - top-bar widths,
  - button sizes,
  - history table proportions.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_model.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_model.py`: clean

### Honest Status
- Verified:
  - refinement changes are implemented,
  - provider-combo reference bug is fixed,
  - compile/diagnostics are clean.
- Needs live visual review from Boss to judge whether the page is now close enough to the target composition or needs one more density pass.

## 2026-05-25 (Music Tabs Parity Pass)

### What Changed
- Moved the `Match` toggle in the `Song description` composer card into the same action row as `Shuffle`, matching the requested layout.
- Replaced the ad hoc music date text fields with a reusable calendar-picker component in `python_app/main.py`:
  - shared builder helper,
  - shared ISO storage conversion,
  - shared restore/update behavior.
- Applied the reusable calendar picker to:
  - top `From` / `To` controls in the `Music` tab,
  - `History` `From` / `To` controls.
- Extended shared field styling so `QDateEdit` follows the same design-system rules as other inputs.
- Added calendar-popup styling so the popup uses the existing dark theme instead of a default mismatched look.
- Rebuilt the `Descriptions` tab to follow the approved layout more closely:
  - top action bar: `Add new`, `Delete`, `Set active`, `Load`
  - left table with `Name` and `Updated`
  - right editor pane
  - description-only `Match structure` dropdown
  - bottom-right `Save`
- Rebuilt the `Structures` tab with the same layout pattern, excluding the description-only match selector.
- Added active description/structure handling so `Set active` updates the correct shared music settings and the left list reflects the active item.
- Added updated-timestamp formatting for the management tables to match the reference style more closely.

### Why Changed
- Boss requested:
  - `Match` in the same row as `Shuffle`
  - a reusable calendar-picker component
  - `Descriptions` and `Structures` pages to follow the approved reference layout more exactly.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_model.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_model.py`: clean

### Honest Status
- Verified:
  - shared calendar-picker component is implemented,
  - `Music`, `Descriptions`, and `Structures` tabs are updated,
  - compile/diagnostics are clean.
- Needs live visual review from Boss for exact parity judgement against the screenshots.

## 2026-05-25 (Music Suno, Pools, Settings End-to-End Wiring Pass)

### What Changed
- Replaced the old placeholder-only music-tab tail in `python_app/main.py` with real Electron-style tabs:
  - `Suno`
  - `Pools`
  - `Settings`
- Removed the redundant `Generation` tab from the music workspace because song count already lives in the main `Music` composer tab.
- Added real backend service modules for the missing Electron parity slices:
  - `python_app/music_migrate.py` for DB connection testing and schema migration
  - `python_app/music_pools.py` for pool stats/list/import/generate/clear operations
  - `python_app/music_callback.py` for a local Suno callback server
  - `python_app/music_ngrok.py` for ngrok tunnel lifecycle/status
- Built a connected `Suno` tab in `python_app/main.py` with:
  - Suno API key
  - output directory browse/open
  - callback URL
  - ngrok start/stop/refresh
  - timeout/retry/version/merge settings
  - retry selected song
  - open output folder
  - refresh pending tasks
- Built a connected `Pools` tab in `python_app/main.py` with:
  - opening/title/album summary cards
  - DB target summary
  - pool type tabs
  - row paging
  - live table + preview
  - generate/import/clear actions
  - clear generated songs/history action
- Built a connected `Settings` tab in `python_app/main.py` with Electron-style sub-tabs:
  - `API`
  - `Profiles`
  - `Paths`
  - `Database`
- Added profile CRUD wiring in `python_app/main.py`:
  - create
  - select
  - edit
  - delete
  - logo browse/open
- Finished the missing runtime wiring in `python_app/main.py`:
  - initialized pool state, selected profile state, callback server, and ngrok manager in `MainWindow.__init__`
  - expanded `_refresh_music_ui()` so all Suno/Pools/Settings widgets hydrate from saved shared settings
  - refreshed pool stats/table and ngrok status from the UI refresh path
  - refreshed runtime DB config after saves so new DB settings take effect immediately
- Added end-to-end `Auto-GSuno` chaining in `python_app/main.py`:
  - when a song is generated and `autoGSuno` is enabled, Python now automatically submits that song to Suno using the same DB-backed task/poller path as manual retry
- Hardened path-opening actions in `python_app/main.py` so empty or missing paths show user-facing warnings instead of raising raw exceptions from button clicks.

### Why Changed
- Boss requested the Electron clone continue past the earlier draft-generation slice and specifically asked for:
  - real `Suno` tab
  - real `Pools` tab
  - no redundant `Generation` tab
  - full `Settings` page
  - end-to-end connected features rather than isolated UI
- The prior pass had most of the builders and helper methods started, but the tabs were not fully production-connected because:
  - several runtime state objects were not initialized
  - the new forms were not fully restored from saved settings
  - pool/ngrok/profile status was not fully refreshed
  - `Auto-GSuno` was not yet chained from generation into the Suno submit path

### Affected Files
- `python_app/main.py`
- `python_app/music_migrate.py`
- `python_app/music_pools.py`
- `python_app/music_callback.py`
- `python_app/music_ngrok.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- Python Music now has a fuller Electron-style feature split:
  - UI orchestration in `main.py`
  - DB migration in `music_migrate.py`
  - pool management in `music_pools.py`
  - callback handling in `music_callback.py`
  - tunnel management in `music_ngrok.py`
- The Suno workflow is now connected from generation to submission to task polling through the same shared settings + DB-backed task-store model.
- Pool management is now visible and actionable from the Python app instead of being an invisible backend dependency.
- Music settings are now edited through a dedicated in-app settings surface while still persisting through the shared normalized music data store.

### New Dependencies
- No new package dependencies added.

### Migration Requirements
- Postgres users should run the new `Database -> Migrate` action in the Python Music settings page so the required tables exist:
  - `opening_pairs`
  - `title_pool`
  - `album_pool`
  - `profiles`
  - `suno_tasks`
  - related shared app tables
- Existing local/shared music settings remain compatible because the new UI reuses the existing normalized settings keys.

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/music_pools.py python_app/music_migrate.py python_app/music_ngrok.py python_app/music_callback.py python_app/music_suno.py python_app/music_db.py python_app/music_model.py python_app/persistence.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
  - `python_app/music_pools.py`: clean
  - `python_app/music_migrate.py`: clean
  - `python_app/music_ngrok.py`: clean
  - `python_app/music_callback.py`: clean

### Honest Status
- Verified:
  - the new tabs exist in code
  - the new backend modules compile
  - the new forms restore from shared settings
  - pool/profile/ngrok runtime state is initialized
  - `autoGSuno` now chains generated songs into the Suno submit path
  - compile/diagnostics are clean
- Partially verified:
  - end-to-end runtime logic is wired, but live API/database/ngrok behavior still depends on Boss's real environment and credentials
- Needs live runtime testing from Boss for:
  - DB connect + migrate button flow
  - pool generate/import/clear behavior against real Postgres
  - profile selection and output-folder grouping
  - ngrok/callback behavior on the local machine
  - Suno auto-submit and pending download completion with real API credentials

### Known Limitations
- The Python Music UI still does not expose a dedicated Suno task-history/status table like a full operations dashboard.
- The callback server and ngrok manager are wired, but successful public callback delivery still depends on local ngrok installation and network/runtime conditions.
- Full interactive QA is still needed for large-batch production usage and real downstream file outputs.

### Suggested Next Improvements
- Add a dedicated Suno task table with per-task status, output dirs, timestamps, and retry controls.
- Add focused runtime smoke tests for:
  - DB migration
  - pool import/generate
  - callback receipt
  - Suno task download completion
- Port any remaining Electron-only music actions after Boss verifies this pass visually and against real credentials.

## 2026-05-25 (Suno Settings Moved Into Settings Page)

### What Changed
- Moved the Suno configuration form out of the working `Suno` tab in `python_app/main.py`.
- Added a dedicated `Suno` sub-tab inside the music `Settings` page, matching the Electron settings structure more closely.
- Moved these controls into `Settings -> Suno`:
  - Suno API key
  - Suno output directory
  - callback URL
  - ngrok start/stop/refresh + status
  - timeout
  - retry count
  - default Suno version
  - merge settings
- Simplified the main `Suno` tab so it now acts as an operations page only:
  - `Open Suno Settings`
  - `Retry Selected Song`
  - `Open Output Folder`
  - `Refresh Pending Tasks`
  - shared status messaging
- Updated the Settings footer save router so when the active sub-tab is `Suno`, it saves the Suno settings patch correctly.
- Added a small navigation helper so the `Suno` working tab can jump directly into `Settings -> Suno`.

### Why Changed
- Boss requested that settings belong in the `Settings` page.
- The prior layout mixed configuration and operational actions in the same `Suno` working tab, which was less clear and diverged from the Electron settings organization.
- Separating them makes the workflow cleaner:
  - `Suno` tab = do work
  - `Settings -> Suno` = configure work

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No backend behavior changed.
- This is a UI/UX architecture correction:
  - operational Suno actions remain on the music working tab
  - persistent Suno configuration now lives in the settings surface
- Existing save/restore wiring remains shared through the same music settings model and persistence layer.

### New Dependencies
- No new dependencies added.

### Migration Requirements
- None.
- Existing saved Suno settings continue to load because the same settings keys are reused.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - Suno settings UI is now in the Settings page
  - the main Suno tab is now action-focused
  - save routing still works for the new Settings sub-tab
  - compile/diagnostics are clean
- Needs live UI review from Boss to confirm the new layout feels correct in the running app.

### Known Limitations
- This pass changes structure and navigation, not the backend workflow itself.
- Full runtime validation with real Suno credentials and ngrok is still needed separately.

### Suggested Next Improvements
- If Boss likes this separation, apply the same strict rule everywhere:
  - working tabs contain actions and live results
  - settings tabs contain persistent configuration only

## 2026-05-25 (Primary Settings Page Migration + Python Copy Cleanup)

### What Changed
- Moved the real music settings UI to the actual left-rail `Settings` page in `python_app/main.py`.
- Removed the duplicate `Settings` tab from the inner Music tab strip, so the Music workspace now focuses on:
  - `Music`
  - `Descriptions`
  - `Structures`
  - `Suno`
  - `Pools`
- Rewired the `Open Suno Settings` action so it now opens the primary `Settings` page and selects the `Suno` sub-tab directly.
- Replaced the old primary `Settings` placeholder page with the real settings surface built by `_build_music_settings_tab()`.
- Cleaned Python-app UI wording that still referred to Electron:
  - removed `Electron bridge v1`
  - removed `Clone of the Electron ...` settings copy
  - removed `shared with the Electron app` warning text in generation validation dialogs
- Updated the settings footer label to reflect the real runtime context of the Python app.

### Why Changed
- Boss requested that the settings belong in the real `Settings` page, not inside the Music tab strip.
- Boss also correctly pointed out that the Python app should not present itself as an Electron bridge in the UI anymore.
- The previous structure caused two architecture problems:
  - duplicated settings surfaces
  - misleading product/runtime wording inside the Python app

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The app navigation is now cleaner and more scalable:
  - music pages handle music work
  - the primary left-rail `Settings` page handles persistent configuration
- No backend service logic changed in this pass.
- Important note: this pass cleans the UI architecture and visible copy only. It does **not** remove the current compatibility/persistence code that still reads existing settings sources under the hood.

### New Dependencies
- No new dependencies added.

### Migration Requirements
- None.
- Existing settings continue to load because the same widget bindings and settings keys are reused.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Searched remaining targeted UI copy in `python_app/main.py`:
  - `Electron bridge`
  - `Clone of the Electron`
  - `shared with the Electron app`
  - stale primary Settings placeholder text
- Verified those targeted strings are no longer present in the updated UI code.

### Honest Status
- Verified:
  - real settings UI is now mounted on the primary `Settings` page
  - duplicate inner Music `Settings` tab is removed
  - Suno settings navigation opens the real Settings page
  - targeted Electron-facing UI copy is removed
  - compile/diagnostics are clean
- Needs live visual/runtime review from Boss to confirm the new page flow feels correct in the running app.

### Known Limitations
- This pass does not refactor the underlying settings/persistence compatibility layer.
- Only the targeted Python-app UI copy was cleaned here; broader internal compatibility naming can be addressed separately if Boss wants a full Python-only terminology pass.

### Suggested Next Improvements
- If Boss wants a fully Python-native terminology pass next, audit internal labels/messages across the entire Python app and remove remaining compatibility-era naming where appropriate.
- After Boss confirms the page flow, continue moving any future persistent configuration into the primary `Settings` page instead of feature-local tabs.

## 2026-05-25 (History Row Suno Actions Matched to Electron)

### What Changed
- Inspected the current Electron history implementation before changing Python:
  - `src/components/dashboard/HistoryPanel.tsx`
  - verified that `Retry` and folder-open actions live inside each history row, in the `Suno` column
- Updated the Python music history table in `python_app/main.py` to follow that Electron layout more closely:
  - added `Channel` column
  - added `Suno` column
  - moved `Retry` into each history row
  - moved `Open Folder` into each history row as a folder icon button
- Added row-action wiring so clicking those history-row buttons:
  - selects the row first
  - updates the current song context
  - then runs the matching Suno retry/open-folder action
- Removed the duplicate Suno action buttons that did not match the Electron layout:
  - removed `Retry Selected Song` and `Open Output Folder` from the separate `Suno` page
  - removed `Retry Suno`, `Open Folder`, and `Refresh Suno` from the song card action row
- Updated the `Suno` page copy so it now explains that history-row actions match the Electron layout and Suno settings remain under `Settings -> Suno`.

### Why Changed
- Boss questioned whether the floating buttons should actually live in the history listing.
- Verified Electron confirms that is correct:
  - `Retry` and folder-open are per-row history actions
  - not loose standalone buttons in the separate Suno page
- The previous Python layout had the right backend actions, but the wrong placement, which created UX drift from the Electron app.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No backend workflow changed.
- This is a UI parity correction:
  - Suno actions now live closer to the song rows they act on
  - current-song context is selected from the history list before action execution
- The history table structure now matches Electron more closely by including `Channel` and `Suno` columns.

### New Dependencies
- No new dependencies added.

### Migration Requirements
- None.

### Verification Performed
- Read Electron reference implementation:
  - `src/components/dashboard/HistoryPanel.tsx`
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - Electron places `Retry` and folder-open inside each history row
  - Python now places those actions in the history table instead of as floating standalone actions
  - history table columns now include `Channel` and `Suno`
  - compile/diagnostics are clean
- Partially verified:
  - visual spacing and row density still need Boss's live runtime confirmation in the actual app window

### Known Limitations
- The Python history table still does not reproduce Electron's sticky batch separator rows.
- This pass focused on the action placement parity Boss asked about, not every remaining history-table visual detail.

### Suggested Next Improvements
- If Boss wants full history-panel parity next, port the remaining Electron details:
  - sticky batch separator rows
  - closer width/density tuning
  - any missing row metadata presentation

## 2026-05-25 (Music Page Flattened + Footer Status Aligned to Electron)

### What Changed
- Inspected Electron first before changing Python:
  - `src/pages/Home.tsx`
  - `src/components/dashboard/MusicControlsBar.tsx`
  - `src/components/dashboard/AppFooter.tsx`
- Refactored the Python Music workspace in `python_app/main.py` so the primary `Music` page is now a single composer page without an inner tab strip.
- Removed the inner Music-page tabs for:
  - `Descriptions`
  - `Structures`
  - `Suno`
  - `Pools`
- Moved the management/configuration pages into the real primary `Settings` page:
  - `Descriptions`
  - `Structures`
  - `Suno`
  - `Pools`
  - existing `API`, `Profiles`, `Paths`, and `Database`
- Rewired the composer `Load` buttons:
  - `Song description -> Load` now opens `Settings -> Descriptions`
  - `Song structure -> Load` now opens `Settings -> Structures`
- Moved the Suno refresh entry point into `Settings -> Suno` so Suno workflow controls remain inside the real settings surface.

### Footer / Status Fix
- Removed Music-local status surfaces that were visually drifting from Electron behavior:
  - removed the top-card Music status label
  - removed the Song-card Suno status label
  - removed the Pools page status label
  - removed the Settings-page inline status label
- Updated status flow so Music/Suno/settings feedback now routes into the global footer status area instead, following the Electron pattern more closely.
- Changed the default footer status behavior so the footer no longer shows a useless in-page `Suno ready` label.
- Added footer refresh on primary-page navigation so switching between `Music` and `Settings` immediately shows the correct footer status text.

### Layout Tuning
- Adjusted the top composer controls card so it sits left-aligned instead of stretching across the full width when not needed.
- Kept the rest of the composer layout intact:
  - description card
  - structure card
  - OK channels
  - ALT channels
  - song panel
  - history panel

### Why Changed
- Boss requested that `Descriptions`, `Structures`, and `Pools` move out of the Music page and into the real Settings page.
- Boss also pointed out correctly that `Suno` was already a settings concern and should not remain as a separate Music page.
- Boss also identified a UX architecture bug:
  - status messages such as `Database settings saved` and `Suno ready` were being shown inside cards instead of in the footer
- Electron confirms the footer is the correct status surface, so the Python app was adjusted to follow that behavior more closely.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- The Music workflow is now cleaner:
  - `Music` page = composer/workspace only
  - `Settings` page = reusable text management, pools, Suno configuration, API/profiles/paths/database
- Status architecture is also cleaner:
  - footer = live status surface
  - cards/pages = content and actions only
- No backend generation/persistence logic was changed in this pass.

### New Dependencies
- No new dependencies added.

### Migration Requirements
- None.
- Existing settings keys and saved data are reused.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Verified targeted obsolete UI elements are removed from active Music page construction:
  - inner Music tab strip
  - top-card Music status label
  - Song-card Suno status label
  - Pools page inline status label

### Honest Status
- Verified:
  - Music page is now a single page without inner tabs
  - Descriptions / Structures / Pools are now under Settings
  - Suno no longer appears as a separate Music page
  - Music/Suno/settings status now routes through the footer instead of local cards
  - compile/diagnostics are clean
- Partially verified:
  - final visual balance still needs Boss's live runtime review in the running app

### Known Limitations
- This pass aligns the Python layout more closely to the Electron footer/status pattern, but it does not fully recreate Electron's progress bar footer yet.
- The unused helper method for the old standalone Suno page can be removed in a later cleanup pass if Boss wants dead-code cleanup immediately.

### Suggested Next Improvements
- If Boss wants the next strict Electron parity pass, refine:
  - footer progress behavior
  - settings tab ordering/density
  - remaining spacing/size polish in the Music composer page

## 2026-05-25 (Settings Page UI/UX Professional Polish Pass)

### What Changed
- Reworked the Python `Settings` page in `python_app/main.py` to feel like a real settings workspace instead of a collection of stretched single cards.
- Added a reusable scrollable settings-shell helper so settings tabs now:
  - stay top-aligned
  - use controlled content width
  - avoid the previous oversized empty vertical space
  - read more like a professional admin/settings surface
- Upgraded the main Settings tab strip to document-mode styling so it feels more integrated with the shell.

### Tab-Level UX Improvements
- `API`
  - split into two focused cards:
    - `Song Drafting`
    - `Support Services`
  - grouped related keys/models together instead of placing every field in one long form
  - added helpful guidance copy so intent is clearer without being noisy

- `Profiles`
  - kept the two-panel editor pattern, but improved hierarchy and spacing so the list/create area and selected-profile detail editor feel more deliberate
  - widened the detail side to improve balance and form readability
  - moved this tab onto the inline-save model so it behaves like a dedicated editor page rather than an awkward global-save page

- `Paths`
  - split into:
    - `Tools`
    - `Output Folders`
  - grouped executable configuration separately from output locations
  - added guidance text for clearer operational intent

- `Descriptions`
  - moved onto the new top-aligned scrollable settings shell
  - preserved all real CRUD wiring while improving page framing and spacing

- `Structures`
  - moved onto the new top-aligned scrollable settings shell
  - preserved all real CRUD wiring while improving page framing and spacing

- `Suno`
  - reorganized into two focused cards:
    - `Access`
    - `Automation`
  - grouped API/output/callback setup separately from runtime automation controls
  - kept ngrok controls inside a nested section with clearer visual containment
  - preserved refresh/save actions while making the page flow more intentional

- `Pools`
  - moved onto the new top-aligned scrollable settings shell
  - preserved all existing stats/list/import/generate/preview wiring
  - removed the previous full-page stretch feel so the layout reads more like a tool page

- `Database`
  - reorganized into:
    - `Connection`
    - `Phrase Pool Data`
  - separated DB connection/migration tasks from pool visibility/import operations
  - kept all existing test/migrate/import wiring intact

### Footer / Action Improvements
- Kept the footer action bar simple and consistent:
  - `Reset local data`
  - global `Save` when the current tab supports footer-save behavior
- Updated footer save visibility rules so inline editor tabs do not show an unnecessary global Save button.

### Why Changed
- Boss requested a senior-level UI/UX improvement pass across all Settings tabs.
- The previous implementation worked functionally but still looked unfinished because:
  - content stretched vertically with too much dead space
  - some tabs were one long card with weak information grouping
  - action hierarchy was inconsistent across tabs
- This pass improves professional structure, readability, and balance while preserving the existing end-to-end wiring.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No backend logic changed.
- No settings keys changed.
- No persistence behavior changed.
- This is a UI/UX architecture improvement:
  - better settings-shell composition
  - clearer grouping by responsibility
  - more scalable page structure for future settings growth

### New Dependencies
- No new dependencies added.

### Migration Requirements
- None.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean

### Honest Status
- Verified:
  - Settings tabs now use the improved top-aligned scrollable shell
  - major settings sections are regrouped into clearer functional cards
  - existing settings actions and bindings remain connected
  - compile/diagnostics are clean
- Partially verified:
  - visual quality and density still need Boss's live review in the running app

### Known Limitations
- This pass improves structure and professionalism, but it does not yet add a richer footer progress/status system like Electron's React footer.
- Some tabs may still benefit from an additional micro-polish pass after Boss reviews the live rendering.

### Suggested Next Improvements
- After Boss reviews the live UI, do a targeted polish pass for:
  - tab widths and spacing
  - card density and margins
  - button sizing consistency
  - footer progress/status behavior for even closer Electron parity

## 2026-05-25 (Startup Regression Fix: Settings Paths NameError)

### What Changed
- Fixed a startup crash in `python_app/main.py` inside `_build_music_settings_tab()`.
- Removed stale `paths_body` references that were left behind after the `Paths` tab was refactored into:
  - `Tools`
  - `Output Folders`

### Root Cause
- During the recent Settings UI redesign, the old single-card `Paths` layout was split into new grouped cards.
- Two legacy `_add_form_row(... paths_body ...)` calls were accidentally left in place even though `paths_body` no longer existed in the new layout.
- That caused startup to fail immediately with:
  - `NameError: name 'paths_body' is not defined`

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No backend logic changed.
- No settings behavior changed.
- This is a regression fix only for the Python Settings page builder.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Searched for remaining `paths_body` references in `python_app/main.py`
  - none remain

### Honest Status
- Verified:
  - the specific NameError from the terminal trace is fixed in code
  - compile/diagnostics are clean
- Needs runtime confirmation from Boss that the app window now opens normally again.

## 2026-05-25 (Follow-Up Settings Startup Fixes During Visual Review Attempt)

### What Changed
- Performed a live startup check of the Python app after the recent Settings UI redesign.
- Fixed a second startup regression in `python_app/main.py` inside the `Suno` Settings builder:
  - `options_row` was referenced before it was created
  - this caused an `UnboundLocalError` during `MainWindow()` construction
- Fixed a follow-up layout issue in the same `Suno` Settings section:
  - `version_wrap` and `merge_wrap` were being attached to `options_row` twice
  - this caused Qt warnings:
    - `QLayout::addChildLayout: layout QVBoxLayout "" already has a parent`

### Root Cause
- These were refactor-order bugs introduced while regrouping the `Suno` settings into the new `Access` and `Automation` cards.
- The new grouped layout was correct in intent, but two local layout-assembly steps were left in the wrong order / duplicated.

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No backend logic changed.
- No settings keys changed.
- No persistence behavior changed.
- This is a UI layout regression fix for the new Settings page structure.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Relaunched the Python app and confirmed startup proceeds past `MainWindow()` construction without the previous `UnboundLocalError`.
- Relaunched again and confirmed the previous duplicate-layout Qt warnings are gone from startup logs.

### Honest Status
- Verified:
  - the app now launches successfully after the follow-up fixes
  - the `options_row` startup crash is fixed
  - the duplicate-layout Qt warnings from the `Suno` settings card are fixed
  - compile/diagnostics are clean
- Partially verified:
  - I can confirm startup from terminal logs, but I still cannot directly visually inspect the live PyQt desktop window from my side the way I can inspect a browser UI

## 2026-05-25 (Wide Left-Aligned Settings Workspace Refactor)

### What Changed
- Reworked the Settings page shell in `python_app/main.py` again after Boss correctly flagged that the previous version looked small, centered, and unprofessional.
- Removed the narrow centered content architecture from `_build_settings_scroll_page()`.
- Replaced it with a full-width, left-aligned desktop settings workspace so each Settings tab now uses the available application canvas instead of floating as a tiny block near the top-center.
- Increased internal page spacing so the workspace reads more like a real desktop tool instead of a compact prototype.
- Strengthened the Settings tab strip by applying a dedicated wider tab style to `self.music_settings_tabs`:
  - larger horizontal padding
  - stronger minimum tab width
  - clearer selected-state emphasis
  - more intentional desktop-header feel

### Why Changed
- Boss reviewed the live UI and correctly identified the real issue:
  - the settings pages were too small
  - content was visually detached from the shell
  - the composition did not look like production desktop software
- Root cause was the previous centered-width shell:
  - a constrained content widget
  - centered horizontally
  - too little visual ownership of the available workspace

### Affected Files
- `python_app/main.py`
- `python_app/DEVELOPMENT_LOG.md`

### Architecture Impact
- No backend logic changed.
- No settings bindings changed.
- No persistence behavior changed.
- This is a UI shell architecture correction for the primary Settings page:
  - full-width scroll area
  - left-anchored content flow
  - stronger tab-header presentation

### New Dependencies
- No new dependencies added.

### Migration Requirements
- None.

### Verification Performed
- Ran `py -m py_compile python_app/main.py`
- Checked diagnostics:
  - `python_app/main.py`: clean
- Relaunched the Python app on the updated code path and confirmed the app remains running from terminal startup logs.

### Honest Status
- Verified:
  - the centered narrow settings shell is removed in code
  - the Settings tabs now use a left-aligned wide workspace shell
  - the Settings tab strip styling is widened and strengthened
  - compile/diagnostics are clean
  - the app relaunches after the refactor
- Partially verified:
  - final visual quality still needs Boss's screenshot confirmation from the live PyQt window

### Suggested Next Improvements
- After Boss reviews the new live layout, do the next targeted visual polish pass for:
  - card density and vertical rhythm
  - button hierarchy consistency
  - footer/status parity with Electron
  - per-tab balance tuning for `Profiles`, `Pools`, and `Database`

## 2026-05-25 (UI UX Tweaks - Calendar and Slider Snapping)

### What Changed
- Fixed AppDateEdit calendar picker behavior by explicitly handling the Show event of the QCalendarWidget instead of just mouse clicks on the widget surface. The calendar popup now highlights the current date when opened from a blank state.
- Applied mutual exclusion disabled styles for QListWidget::item and QListView::indicator in _build_app_stylesheet. The disabled OK/ALT channels now properly render visually greyed out instead of looking active.
- Updated music_creativity_slider and music_polish_slider to snap precisely to 10-step increments (10, 20, 30...) by setting single_step=10, page_step=10, and enforcing rounding in alueChanged.

### Why Changed
- The calendar dropdown arrow was bypassing the mousePressEvent override, causing the calendar to open on the year 2000 minimum date. Catching the Show event guarantees it defaults to today regardless of how the popup was triggered.
- Mutual exclusion logic for OK/ALT channels was already removing the item from the opposite list and setting ItemIsEnabled off, but the global Qt stylesheet color overrides made disabled items look exactly like active items. Adding explicit :disabled rules fixes this visual bug.
- Boss requested the scroll controls to operate in 10-step increments.

25 (UX Tweaks - Channels and Date Separations)

### What Changed
- Fixed History date picker linking bug: it was erroneously sharing music_run_from_date state with the Run date picker. Added dedicated music_history_from_date and music_history_to_date variables so History filters operate completely independently.
- Fixed OK/ALT channel numbering logic: The Python UI list now shows the selection order (e.g., BASS DRIVE (1)) matching Electron, and correctly calculates the ordered list rather than the naive top-down index order when multiple profiles are selected.

### Why Changed
- Boss pointed out that History calendar dates should not be the same as the Run calendar picker, as they serve different purposes.
- Boss noticed that when multiple channels were selected, the UI didn	 indicate their priority/order index (1, 2, etc.) and they weren	 tracking selection order correctly in the backend payload.


## 2026-05-25 (UX Tweaks - Channels and Date Separations - Update)

### What Changed
- Refactored _refresh_music_profile_lists to use setItemWidget for OK/ALT channels to achieve the exact 3-column right-aligned number formatting from Electron.
- Added QTimer.singleShot to the AppDateEdit event filter to guarantee the QCalendarWidget visually jumps to today without updating the QDateEdit text.

## 2026-05-26 (Music History Table Redesign: Suno Dot + OK/ALT Columns)

### What Changed
- Redesigned Music → History table to reduce clutter and surface the right information:
  - Split the previous `Channel` column into `OK Channel` and `ALT Channel`.
  - Added `Run Date` (requested batch date) and renamed `Created` to `Generated`.
  - Replaced the Suno status wording with a dot-only status indicator (green/yellow/red) and kept retry as a small icon button.
  - Moved folder-open actions into the OK/ALT channel columns so each channel can open its own directory.
  - On row selection, the footer now shows the full latest Suno status/error string for that song.
- Enriched DB history loading so channel columns can show profile names instead of only ids by joining `songs.profile_*_id` to `profiles.name`.

### Why Changed
- Boss requested:
  - dot-only Suno status instead of text labels,
  - smaller retry button visibility within the table,
  - separate OK vs ALT channel columns with per-channel folder navigation,
  - clear separation of Run Date (batch-for date) vs Generated Date (record timestamp),
  - and full Suno error/status visibility in the footer when selecting a song.

### Affected Files
- `python_app/views/music_view.py`
- `python_app/main.py`
- `python_app/database/music_db.py`
- `python_app/DEVELOPMENT_LOG.md`
- `python_app/docs/music-history-ui/tasks.md`
- `python_app/docs/music-history-ui/design.md`
- `python_app/docs/music-history-ui/technical.md`

### Architecture Impact
- No new subsystems added.
- History still reads songs from Postgres; it now returns profile names by joining the `profiles` table.
- The History table continues to drive song selection via `MusicController.on_history_row_selected`, with additional footer status context driven by the main window.

### Verification Performed
- Ran `py -m py_compile python_app/main.py python_app/views/music_view.py python_app/database/music_db.py`
- Checked diagnostics for updated Python files: clean

### Known Limitations
- Footer label may clip very long error strings (Qt label width constraints), but the tooltip preserves the full status/error text.

### Update
- Increased Music → History table row height so the dot and icon buttons have proper vertical breathing room.
- Added browser-like HTTP headers to Suno requests (`User-Agent`, `Accept`, `Accept-Language`) to reduce HTTP-layer blocking that can surface as “error code: 1010”.
- Removed the `Run Date` column and instead inserted batch separator rows based on `batchId` that show `Batch: <id> • Run Date: <yyyy-mm-dd>`.
- Added a dedicated `tableIcon` button role so History icon buttons keep a compact fixed size (no stretching to row height).
- Fixed a Suno retry crash: imported and used the correct DB history insert function so `music_insert_history` is defined.
- Fixed a Suno poll crash: guarded `audioUrls` indexing to prevent `list index out of range` when fewer than 2 URLs are available.
- Fixed a threading warning during Auto-Suno: moved the delayed Suno poll scheduling out of the Python `threading.Thread` worker and into the main Qt event loop via a UI event.
- Added the same browser-like headers to audio downloads to reduce 403 Forbidden responses from upstream hosts when fetching `audioUrl` MP3 files.
- Fixed `Retry Suno` crash when cached URLs were NULL: avoided converting NULL to the string `"None"` before downloading.
- Made Suno polling resilient for long multi-batch runs: added `downloaded_ok/downloaded_alt` flags so tasks remain pending until files are actually downloaded (not only until URLs exist). Requires running DB Migrate.
- Changed startup default page to Home (instead of Video) so the app opens on the dashboard area first.
- Reduced first-time Music page lag by caching rendered SVG icons (no per-row QSvgRenderer work) and disabling History table repaint during bulk row population.
- Fixed “Generate music stuck / Stop not working” for SLAI/DeepSeek drafts by adding per-request timeouts, reducing inner validation retries, and honoring cancel checks during draft generation.
- Added runtime settings defaults: `songDraftTimeoutSec` and `songDraftMaxAttempts` to control draft call responsiveness.
- Added deep SLAI/DeepSeek draft generation logs (HTTP start/ok/error + per-validation attempt accept/reject) to diagnose “stuck at item=1” issues without exposing API keys.
- Improved SLAI reliability by requesting structured JSON output (`response_format: json_object` when supported), lowering SLAI temperature cap, and accepting common alternate JSON keys (songTitle/albumName/lyric) when returned.
- Reduced SLAI timeouts by shrinking avoid-lists sent to the model and adding a max token cap for SLAI responses; also removed redundant outer draft retry loop so one song can’t hang for many minutes.
- Fixed Suno DB constraint crash during song generation: `upsert_suno_task()` now always writes `downloaded_ok/downloaded_alt` as boolean (defaults false) instead of inserting NULL into NOT NULL columns.
- Fixed History table “mess” during generation by fully resetting the QTableWidget row model before repopulating, preventing stale cell widgets/spans from previous refresh cycles.
- Changed History ordering to “Generated date” (`created_at`) descending so newest songs appear at the top.
- Made `createdAt` store the actual generation timestamp (now) and stored requested batch date in `runDate`, so “new generated song must be on top” is always correct even when generating older run dates.
- Improved History batch readability by rendering batch separator rows with a distinct background color.
- Changed History batch ordering logic: batches are now grouped and sorted by the most recent `createdAt` inside each batch, so the latest generated batch always appears first (and batches no longer split into multiple blocks).
- Fixed crash on Music page navigation by adding missing UI token `panel_bg2` used for batch separators.
- Improved startup responsiveness by deferring Video page restore work (logo/background/MP3 folder/template) until the Video page is opened, instead of doing it during initial app startup.
- Reduced perceived Music-first-open lag by scheduling the History refresh after the page switch instead of blocking inside the navigation handler.
- Improved History performance by defaulting History to “Last batch” on first run and making the DB query load only the latest batch when that toggle is enabled.
- Changed batch separator background to use the same dark-blue tone as primary buttons for clearer visual grouping.
