# MainWindow Extraction Map

## Purpose
Provide a prioritized extraction map for reducing `app/main_window.py` from a 10k+ line god object into a composition shell backed by feature coordinators.

---

## Verified Current Risk
`MainWindow` currently combines:
- page composition
- UI event handling
- feature workflow coordination
- direct DB calls
- external service calls
- timer/thread/subprocess ownership
- profile/template management
- YouTube queue/upload lifecycle handling
- progress actions
- video workspace orchestration

The extraction plan below is intentionally incremental.

---

## Extraction Principles
1. Preserve visible app behavior.
2. Extract orchestration before chasing file-size cosmetics.
3. Remove direct DB/service calls from host only after coordinator path exists.
4. Prefer feature ownership over generic helper dumping.
5. Leave `MainWindow` as shell glue, not a second coordinator.

---

## Priority Tiers

### Tier 1 — Highest value, lowest conceptual risk
These areas have strong business boundaries and should move first.

#### A. ProfileCoordinator
Move out of `MainWindow`:
- profile load/save orchestration
- profile validation/default application
- profile-image config coordination
- profile-level feature toggle workflows

Why first:
- clear feature boundary
- high frequency of edits
- directly related to settings/template behavior

#### B. VideoTemplateCoordinator
Move out of `MainWindow`:
- template save/load/list/delete orchestration
- local-vs-DB template resolution
- template application to video workspace state
- template import/export policy if added later

Why first:
- clear entity boundary
- highly coupled to current host state
- important for future video/lyric/template features

#### C. DB Settings / PersistenceCoordinator
Move out of `MainWindow`:
- database connect/initialize/migrate flows
- loading persisted app state
- persistence status handling
- app start hydration decisions

Why first:
- foundational, reusable, and risky to leave scattered

---

### Tier 2 — High value, medium risk

#### D. YouTubeCoordinator
Move out of `MainWindow`:
- profile-channel connection flow
- OAuth start/finish state handling
- upload queue policy
- manual start/retry/cancel actions
- pending/running/failed upload transitions
- worker kick/poll policy

Why now:
- feature already has `features/youtube/`
- currently one of the most stateful and failure-prone flows
- benefits strongly from dedicated ownership

#### E. ProgressCoordinator
Move out of `MainWindow`:
- progress row refresh orchestration
- context-menu action dispatch
- queue action rules
- row-to-feature command routing

Why now:
- progress page touches many workflows
- should become a central feature bridge rather than host-level logic cluster

---

### Tier 3 — High complexity, do after earlier wins

#### F. MusicGenerationCoordinator
Move out of `MainWindow`:
- music enqueue/start orchestration
- provider selection policy
- callback/result handling at feature level
- batch/channel-level state transitions

#### G. ImageGenerationCoordinator
Move out of `MainWindow`:
- image job enqueue logic
- sample selection policy coordination
- random/manual sample behavior
- generation refresh actions

#### H. VideoWorkspaceCoordinator
Move out of `MainWindow`:
- video preview state orchestration
- resolution/template/bg/logo/spectrum coordination
- export handoff prep
- timeline/text/lyric state application later

Why later:
- high coupling to view state
- easier once profile/template coordinators already exist

---

## Not first-wave extraction targets

### `views/components.py`
Do not split this first.
Reason:
- shrinking `MainWindow` first gives clearer UI boundaries.
- otherwise you risk just moving confusion sideways.

### `visualizer/gpu_render.py`
Do not merge into the early app-shell refactor.
Reason:
- it is a subsystem with performance-sensitive rendering concerns.
- should be handled through interface hardening, not early scatter refactor.

---

## Suggested Target Homes

### Proposed feature homes
- `features/profiles/coordinator.py`
- `features/templates/coordinator.py`
- `features/youtube/coordinator.py`
- `features/progress/coordinator.py`
- `features/music/coordinator.py`
- `features/image/coordinator.py`
- `features/video_workspace/coordinator.py`
- optional `features/persistence/coordinator.py`

If you prefer fewer folders early, combine tightly related ones first:
- profiles + templates
- youtube auth + queue/upload

---

## Extraction Sequence Recommendation

### Slice 1
- Add coordinator skeletons and interfaces only
- Wire `MainWindow` delegation points
- No behavior move yet except thin wrappers

### Slice 2
- Move ProfileCoordinator + VideoTemplateCoordinator logic
- Keep host glue methods as thin delegators

### Slice 3
- Move DB Settings / PersistenceCoordinator logic
- Reduce startup/hydration burden in `MainWindow`

### Slice 4
- Move YouTubeCoordinator logic
- Consolidate upload queue and OAuth state ownership

### Slice 5
- Move context-menu dispatch, cancel-row/cancel-all flows, and image restart actions out of `MainWindow`
- Preserve deeper converter/merge routing and YouTube-linked progress actions on the host seam temporarily

### Slice 6
- Reduce the remaining public Progress entrypoints in `MainWindow` to coordinator delegators
- Move converter restart routing, merge-only restart routing, and safe YouTube row actions behind `features/progress/coordinator.py`
- Keep deeper auto-video internals, merge-worker orchestration, and YouTube upload runtime helpers on host-side `*_impl` seams until a later extraction

### Slice 7
- Add a dedicated `YouTubeCoordinator` for the first safe YouTube workspace/profile extraction slice
- Move jobs-table refresh/rendering, selected-job lookup, retry/cancel UI entry routing, and profile connect/disconnect entrypoints out of `MainWindow`
- Keep OAuth connect worker lifecycle, upload queue/tick runtime orchestration, timer sync, and active cancel-state internals on host-side seams for now

### Slice 8
- Move YouTube timer creation and auto-poll routing behind `features/youtube/coordinator.py`
- Preserve host timer attribute names `_youtube_auto_poll_timer` and `_youtube_live_refresh_timer` so shutdown/runtime shell logic remains stable
- Keep OAuth connect worker lifecycle, upload queue/enqueue behavior, upload tick/runtime orchestration, and active cancel-state internals on host-side seams until a later extraction

### Slice 9
- Move YouTube OAuth connect start/cancel worker lifecycle behind `features/youtube/coordinator.py`
- Preserve the host-owned `_youtube_connect_cancel_events` storage, emitted `youtube_connect_done` / `youtube_connect_select_channel` payload contracts, and current visible button/status behavior
- Keep bus-event result handling for `youtube_connect_select_channel` / `youtube_connect_done`, upload queue/enqueue behavior, upload tick/runtime orchestration, and deeper active-upload cancel-state internals on host-side seams

### Slice 10
- Move YouTube connect-result bus-event handling for `youtube_connect_select_channel` / `youtube_connect_done` behind `features/youtube/coordinator.py`
- Preserve the existing event payload contracts, channel-selection dialog behavior, selected-channel DB upsert payload, status updates, playlist-cache clearing, selected-profile detail refresh, and guarded `_youtube_scan_for_merged_outputs()` trigger
- Keep upload queue/enqueue behavior, upload tick/runtime orchestration, deeper active-upload cancel-state internals, playlist fetch/cache result handling, upload status/progress/done bus-event handling, and merged-output scan/enqueue routing on host-side seams

### Slice 11
- Move YouTube playlist fetch/cache result handling behind `features/youtube/coordinator.py`
- Preserve host-owned `_youtube_playlists_cache`, the `music_settings_profile_youtube_playlist` combo target, `No playlist` default rendering, `Missing · <id>` fallback rendering, unchanged `youtube_playlists_loaded` payload contracts, and selected-profile refresh matching behavior
- Keep upload queue/enqueue behavior, upload tick/runtime orchestration, deeper active-upload cancel-state internals, upload status/progress/done bus-event handling, and merged-output scan/enqueue routing on host-side seams

### Slice 12
- Move YouTube upload bus-event handling for `youtube_upload_status`, `youtube_upload_progress`, and `youtube_upload_done` behind `features/youtube/coordinator.py`
- Preserve the current event payload contracts, host-owned `_youtube_progress_by_job_uid` cache semantics, `_youtube_render_terminal_progress()` calls, progress-page row status updates, final row text transitions (`Done`, `Failed`, `Queued`), and retry suffix behavior in failed YouTube status text
- Keep upload queue/enqueue behavior, upload runtime/tick orchestration, deeper active-upload cancel-state internals, merged-output scan/enqueue routing, and any remaining YouTube runtime helpers on host-side seams

### Slice 13
- Move merged-output scan/enqueue routing behind `features/youtube/coordinator.py`
- Preserve public host method names `_youtube_scan_for_merged_outputs()` and `_enqueue_youtube_upload_for_merge(...)` as thin delegators
- Preserve startup/manual-resume safeguards, `autoUploadYouTube` / `db_cfg` gating, shallow MP4 readiness checks, deterministic job uid generation, blocked-vs-pending queue status behavior, DB-layer duplicate/upsert semantics, and immediate `QTimer.singleShot(0, ...)` scheduling for upload tick / jobs-table refresh
- Keep upload queue claiming policy / pending-job claim execution, upload runtime/tick orchestration, deeper active-upload cancel-state internals, and remaining YouTube runtime helpers on host-side seams

### Slice 14
- Move YouTube upload tick orchestration and pending-job queue-claiming policy behind `features/youtube/coordinator.py`
- Preserve public host method `_youtube_upload_tick(...)` as a thin delegator so existing timer and caller wiring stays stable
- Preserve host `_youtube_worker_state = {"jobs": {...}}` shape, dead-thread cleanup behavior, `_youtube_worker_limit()` enforcement, `db_claim_pending_youtube_upload_jobs(..., max_jobs=need, max_running=limit)` claim semantics, and `threading.Event()` / `threading.Thread(..., daemon=True)` worker start pattern
- Keep host-owned `_run_one_youtube_upload_job(...)`, active-upload cancel-state internals, and any deeper runtime helpers on host-side seams

### Slice 15
- Move the shared YouTube runtime helper cluster behind `features/youtube/coordinator.py`
- Preserve public host method names `_youtube_worker_limit()`, `_short_youtube_job_uid(...)`, `_youtube_render_terminal_progress()`, and `_youtube_is_mp4_ready_for_upload(..., deep=False)` as thin delegators
- Preserve worker-limit clamping/default behavior, short job UID formatting rules, terminal progress rendering against host `_youtube_worker_state` / `_youtube_progress_by_job_uid`, and shallow/deep MP4 readiness validation behavior
- Keep host-owned `_run_one_youtube_upload_job(...)`, active-upload cancel-state internals, and any remaining deeper YouTube runtime helpers on host-side seams

### Slice 16
- Move the active-upload cancel/runtime-state seam behind `features/youtube/coordinator.py`
- Preserve `_youtube_worker_state = {"jobs": {...}}` host storage shape, shutdown cleanup `summary['youtube_runtime']` counting semantics, `_youtube_upload_running` behavior, active worker cancel-event signaling, and `_youtube_auto_poll_timer` stop behavior during shutdown cleanup
- Keep `_cancel_youtube_upload_impl()` as a thin delegator if retained for compatibility
- Keep host-owned `_run_one_youtube_upload_job(...)` deeper per-job execution intact except for finally-block runtime cleanup delegation

### Slice 17
- Move throttled upload-progress callback creation out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`
- Preserve exact progress callback behavior: clamp `0..100`, first emit immediately, always emit at `100`, emit when `>= 0.25s` since last emit, and emit when integer progress advances by at least `1`
- Preserve callback-local throttle state storage via `_last_ts` / `_last_pct` attributes and preserve the existing `youtube_upload_progress` bus payload contract
- Keep all remaining per-job preparation/upload/update logic host-owned for this slice

### Slice 18
- Move YouTube OAuth credential loading cluster out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`
- The coordinator now owns `get_upload_credentials(profile_id, profile, settings)` which loads the YouTube account, decrypts the refresh token, resolves the OAuth app (profile-level or fallback from settings), and returns `(refresh_token, client_id, client_secret)`
- Remove unused `db_get_youtube_account`, `db_get_youtube_oauth_app`, and local `dpapi_decrypt_from_base64` imports from `_run_one_youtube_upload_job`
- Keep all remaining per-job preparation/upload/update logic host-owned for this slice

### Slice 19
- Move YouTube upload metadata rendering cluster out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`
- The coordinator now owns `render_upload_metadata(profile, batch_id, role)` which renders title/description from template placeholders, computes privacy mode and scheduled publish datetime, and extracts tags/category/kids/synth/playlist settings
- Keep the scheduled same-day batch collision warning host-owned since it depends on `self.bus` and `db_list_youtube_upload_jobs`
- Keep all remaining per-job file resolution, thumbnail discovery, upload API calls, post-upload DB updates, error handling host-owned for this slice

### Slice 20
- Move thumbnail path resolution cluster out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`
- The coordinator now owns `resolve_thumbnail_path(batch_id, role, file_path)` which looks up the batch run directory from the database, falls back to inferring from the file path, and searches for thumbnails in priority order
- The `_safe_batch_suffix` helper remains host-owned since it's also used elsewhere in the host
- Keep all remaining per-job upload status notification, upload API calls, post-upload DB updates, error handling host-owned for this slice

### Slice 21
- Move upload warning builder cluster out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`
- The coordinator now owns `build_upload_warnings(thumbnail_error, playlist_error, processing_status, upload_status)` which joins error/warning components into a human-readable string
- Both the `existing_video_id` path and fresh-upload path in the host now delegate to this method, eliminating duplication
- Keep all remaining per-job upload status notification, upload API calls, post-upload DB updates, error handling, cancel-state handling host-owned for this slice

### Slices 22–24
- Move three small pure-computation helpers out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`:
  - `resolve_scopes(scopes_str)` — resolves scopes from account with default fallback
  - `is_processing_failed(processing_status, upload_status)` — checks post-upload processing failure
  - `classify_upload_exception(exc)` — classifies HTTP/IO exceptions as transient (retryable) or not
- Keep all remaining debug-point HTTP calls, cancel-state DB updates, bus event emissions, DB mark-ready/failed/pending orchestration, and retry orchestration flow host-owned for these slices

### Slices 25–27
- Move upload-start status message builder, post-upload notification message builder, and retry decision logic out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`:
  - `build_upload_start_status_message(profile_name, role, visibility_mode, publish_at)` — builds upload-start status message string
  - `build_post_upload_notification_messages(thumb_err, pl_err, has_playlist_id)` — builds post-upload status notification event dicts
  - `compute_retry_action(attempt_no, is_transient)` — computes whether to retry or fail after upload exception
- Keep all remaining debug-point HTTP calls, cancel-state DB updates, direct bus event emissions (upload_done), DB mark-ready/failed/pending orchestration, and existing-video-id retry path host-owned for these slices

### Slice 28
- Move profile lookup, same-day collision detection, and existing-video retry path out of `_run_one_youtube_upload_job(...)` and behind `features/youtube/coordinator.py`:
  - `resolve_profile_for_upload(profile_id, db_cfg)` — resolves profile dict from DB first, falls back to host
  - `detect_same_day_collision(db_cfg, batch_id, profile_id, current_job_uid)` — detects same-profile same-day already-published job
  - `retry_existing_video_upload(...)` — handles re-upload of thumbnail and playlist for existing YouTube video
- **Status:** `_run_one_youtube_upload_job` is now ~85 lines (down from ~260 original). Remaining code is tightly coupled to execution flow (DB calls, bus emissions, cancel checks) — further extraction would require passing the bus and DB through the coordinator, which would over-complicate the architecture.
- The YouTube coordinator extraction is considered complete for now.

### Future Slices (Beyond YouTube)
- Consider extracting progress coordinator deeper internals or other feature coordinators

### Slice 29
- Create `AutoVideoCoordinator` in `features/auto_video/coordinator.py`:
  - `resolve_channel_plan(batch_id, profile_id, role, output_dir, settings)` — resolves all inputs (ffmpeg, MP3 scan, background image, template, output resolution, worker count) into `AutoVideoChannelPlan` dataclass
  - `build_export_progress_message(role, current, total, workers)` — status message
  - `build_export_complete_message(role, batch_name, mp4_count)` — completion message
- Refactored `_try_start_auto_video_channel` to use `plan` object instead of scattered local variables

### Slice 30
- Create `MergeWorker` in `features/merge/worker.py`:
  - `merge(ffmpeg_path, mp4_paths, target_path)` — handles file validation (size, stability, ffprobe duration), shuffle with order log, FFmpeg concat demuxer with re-encode fallback, temp cleanup
- Deleted `_merge_mp4s` (~156 lines) from `main_window.py`
- Updated `_start_merge_only_thread` to use `self.merge_worker.merge()` instead of `self._merge_mp4s`

---

## Validation After Each Slice
- app launches
- navigation still works
- profiles load/save correctly
- templates load/apply/save correctly
- YouTube connect/upload actions still work
- progress page actions still work
- preview/export still work
- no new direct DB/service calls added back into host during the slice

---

## Definition of Success
`MainWindow` is successful after extraction when it mostly reads like:
- construct pages
- connect signals
- delegate to coordinators
- reflect app-level state
- manage shell concerns only

If feature policy still lives there, extraction is incomplete.
