# Implementation Tasks

## Task 1: Create YouTubeConnectionClient service

### Description
Create `python_app/services/youtube_connection_client.py` — an authenticated httpx sync client wrapping all Platform API YouTube endpoints. Follow the exact same pattern as `ProfileClient` (bearer auth, 401 refresh retry, session-expired trigger, structured error raising).

### Files to Create
- `python_app/services/youtube_connection_client.py`

### Requirements Addressed
- Requirement 1 (all acceptance criteria)

### Acceptance Criteria
- [x] 1.1 Client class `YouTubeConnectionClient` accepts `token_store: TokenStorePort`, `base_url: str`, `timeout: float` via constructor
- [x] 1.2 `list_connections()` → GET `/youtube/connections`, returns list of connection dicts
- [x] 1.3 `start_connection(profile_id: str)` → POST `/youtube/profiles/{profile_id}/connect`, returns `{session_id, auth_url, status}`
- [x] 1.4 `select_channel(session_id: str, channel_id: str)` → POST `/youtube/connect-sessions/{session_id}/select-channel`, returns connection dict
- [x] 1.5 `disconnect(profile_id: str)` → DELETE `/youtube/profiles/{profile_id}/connection`
- [x] 1.6 `resync(profile_id: str)` → POST `/youtube/profiles/{profile_id}/resync`, returns connection dict
- [x] 1.7 `list_playlists(profile_id: str)` → GET `/youtube/profiles/{profile_id}/playlists`, returns list of playlist dicts
- [x] 1.8 `enqueue_upload(profile_id: str, *, batch_id: str, role: str, merged_mp4_path: str)` → POST `/youtube/profiles/{profile_id}/uploads/merge`, returns response dict
- [x] 1.9 `run_uploads(*, batch_id: str | None = None, limit: int = 1)` → POST `/youtube/uploads/run`, returns response dict
- [x] 1.10 Internal `_request()` method mirrors ProfileClient: bearer token from TokenStore, 401 triggers refresh attempt, raises `AuthenticationError`/`NetworkError`/`PlatformAPIError`/`ValidationError`
- [x] 1.11 Has a `close()` method to shut down the httpx client

---

## Task 2: Wire YouTubeConnectionClient into bootstrap

### Description
Instantiate `YouTubeConnectionClient` in `bootstrap.py` and set it as a QApplication property so that controllers can access it.

### Files to Modify
- `python_app/app/bootstrap.py`

### Requirements Addressed
- Requirement 1 (AC 4: constructor injection)

### Acceptance Criteria
- [x] 2.1 Import `YouTubeConnectionClient` in bootstrap.py
- [x] 2.2 Instantiate with `base_url=platform_api_base_url` and `token_store=token_store`
- [x] 2.3 Set as `app.setProperty("youtube_connection_client", youtube_connection_client)`
- [x] 2.4 No startup errors — the client is lightweight to construct

---

## Task 3: Create YouTube Connection Controller

### Description
Create `python_app/features/youtube/connection_controller.py` — a UI controller that manages the YouTube Settings Tab interactions: profile selection, connection actions, status polling, and channel selection.

### Files to Create
- `python_app/features/youtube/connection_controller.py`

### Requirements Addressed
- Requirement 2 (all acceptance criteria)
- Requirement 6 (polling logic)

### Acceptance Criteria
- [x] 3.1 Class `YouTubeConnectionController` with constructor accepting: widget accessor callable, youtube_connection_client, profile_list accessor, logger
- [x] 3.2 `refresh_connection_state(profile_id: str)` fetches connections and updates UI widgets
- [x] 3.3 `on_connect(profile_id: str)` calls `start_connection`, opens auth_url in system browser via `webbrowser.open()`, starts polling timer
- [x] 3.4 `on_restart(profile_id: str)` same as on_connect (starts fresh session)
- [x] 3.5 `on_select_channel(session_id: str, channel_id: str)` calls `select_channel`, refreshes UI
- [x] 3.6 `on_resync(profile_id: str)` calls `resync`, refreshes displayed channel info
- [x] 3.7 `on_disconnect(profile_id: str)` calls `disconnect`, resets UI to not_connected state
- [x] 3.8 Polling timer (5s interval QTimer) active only while status is `pending_browser` — polls `list_connections` and detects status changes
- [x] 3.9 Polling stops when: status changes from pending_browser, tab is hidden, or different profile selected
- [x] 3.10 All API errors are caught, logged, and displayed in a status label — no unhandled exceptions

---

## Task 4: Build YouTube Settings Tab UI

### Description
Replace the existing YouTube tab content in `settings_view.py` with a two-panel layout: Channel Connection (left) and Channel Access (right). Keep the existing OAuth Apps UI available via a sub-section or collapsible area.

### Files to Modify
- `python_app/views/settings_view.py`

### Requirements Addressed
- Requirement 2 (UI acceptance criteria)

### Acceptance Criteria
- [x] 4.1 Left panel "Channel Connection" contains: profile selector dropdown, connection status label, channel display (title + ID), channel selector dropdown (hidden unless awaiting_channel_selection), action buttons row
- [x] 4.2 Right panel "Channel Access" contains: 3 info labels (Selected profile, Returned channels, Session state), current state text, connected channel text, help text
- [x] 4.3 Action buttons dynamically enable/disable based on connection status: Connect (when not_connected), Restart (when pending_browser), Try Again (when error), Resync (when connected), Disconnect (when not not_connected)
- [x] 4.4 Channel selector dropdown is only visible when status is `awaiting_channel_selection`, populated from connection's channels array
- [x] 4.5 "Attach Channel" button next to channel selector, enabled only when a channel is selected
- [x] 4.6 Profile selector populated from cached profiles list
- [x] 4.7 Existing OAuth Apps sub-section preserved (moved into a collapsible card or kept below the connection panels)
- [x] 4.8 All widgets stored as instance attributes for controller access (e.g., `self.yt_conn_status_label`, `self.yt_conn_channel_display`, etc.)

---

## Task 5: Wire YouTube Connection Controller to UI

### Description
Connect the `YouTubeConnectionController` to the YouTube Settings Tab widgets in `init_orchestrator.py`. Ensure profile selection triggers connection state refresh, and button clicks route to controller actions.

### Files to Modify
- `python_app/app/init_orchestrator.py`
- `python_app/app/main_window.py` (if needed for wiring)

### Requirements Addressed
- Requirement 2, Requirement 6

### Acceptance Criteria
- [x] 5.1 `YouTubeConnectionController` instantiated after main window is built, with access to widgets and `youtube_connection_client`
- [x] 5.2 Profile selector `currentIndexChanged` signal triggers `refresh_connection_state` for the selected profile
- [x] 5.3 Connect/Restart/Try Again button click routes to `on_connect`
- [x] 5.4 "Attach Channel" button click routes to `on_select_channel` with selected session_id and channel_id
- [x] 5.5 "Resync" button click routes to `on_resync`
- [x] 5.6 "Disconnect" button click routes to `on_disconnect` (with confirmation dialog)
- [x] 5.7 Controller polling timer properly starts/stops with tab visibility changes

---

## Task 6: Update Publication Tab to use Platform API youtube_config

### Description
Update the Publication tab to read publication defaults from the profile's `youtube_config` (already parsed by `map_api_profile_to_runtime`) and save changes via `ProfileClient.update_profile()` using `build_api_profile_payload()`. Add dirty-state tracking and a dedicated Save button.

### Files to Modify
- `python_app/views/settings_view.py` (UI additions: Save Publication button, dirty indicator)
- `python_app/app/music_ui_handlers.py` (save logic, dirty tracking, data loading)

### Requirements Addressed
- Requirement 3 (all acceptance criteria)

### Acceptance Criteria
- [x] 6.1 When a profile is selected in Publication tab, form fields populate from the runtime profile's youtube fields (youtubeVisibilityMode, youtubeCategoryId, youtubeTags, etc.)
- [x] 6.2 Visibility "scheduled" shows hour/minute selectors; other values hide them
- [x] 6.3 "Save Publication" button calls `ProfileClient.update_profile(profile_id, build_api_profile_payload(runtime_profile))` with updated youtube_config
- [x] 6.4 Dirty-state tracking: Save button disabled when no changes detected, enabled when form values differ from loaded values
- [x] 6.5 Success/error feedback shown in status label after save attempt
- [x] 6.6 Keywords field added if not already present (maps to youtube_config description/keywords)

---

## Task 7: Implement Playlist fetching via Platform API

### Description
Update the Publication tab's Playlist dropdown to fetch playlists from `GET /youtube/profiles/{profile_id}/playlists` via `YouTubeConnectionClient` instead of local Google API calls.

### Files to Modify
- `python_app/app/music_ui_handlers.py` (or relevant handler that manages playlist population)
- `python_app/views/settings_view.py` (ensure playlist dropdown has correct placeholder text)

### Requirements Addressed
- Requirement 4 (all acceptance criteria)
- Requirement 3 (AC 7, AC 8: playlist enabled/disabled based on connection status)

### Acceptance Criteria
- [x] 7.1 When a connected profile is selected in Publication tab, `list_playlists(profile_id)` is called via `YouTubeConnectionClient`
- [x] 7.2 Playlist dropdown populated with `id` and `title` from the response
- [x] 7.3 When profile is not connected, playlist dropdown is disabled with placeholder "Connect YouTube first"
- [x] 7.4 If playlist fetch fails (network error, 4xx), dropdown shows "No playlist" as only option and error is logged
- [x] 7.5 A "No playlist" option (value="") is always the first item in the dropdown

---

## Task 8: Create Auto Upload Coordinator

### Description
Create `python_app/features/youtube/auto_upload_coordinator.py` — a timer-based background coordinator that polls progress rows, selects YouTube upload candidates, and enqueues/triggers uploads via Platform API endpoints.

### Files to Create
- `python_app/features/youtube/auto_upload_coordinator.py`

### Requirements Addressed
- Requirement 5 (all acceptance criteria)

### Acceptance Criteria
- [x] 8.1 Class `AutoUploadCoordinator` with constructor accepting: youtube_connection_client, settings_accessor, progress_rows_accessor, profiles_accessor, timer_factory, logger
- [x] 8.2 Creates a timer (6s interval) that calls `_tick()`
- [x] 8.3 `_tick()` checks `autoUploadYouTube` setting — returns early if disabled
- [x] 8.4 Candidate selection logic mirrors Electron's `selectNextAutoYouTubeCandidate`: checks merged MP4 exists, row not in terminal stage, no active/completed YouTube status, profile_id is known
- [x] 8.5 Per-key cooldown map prevents re-processing within cooldown windows
- [x] 8.6 When candidate found: call `enqueue_upload(profile_id, batch_id, role, merged_mp4_path)`
- [x] 8.7 If enqueue returns status "blocked" → 60s cooldown, skip run_uploads
- [x] 8.8 If enqueue succeeds → call `run_uploads(batch_id=batch_id, limit=1)` → 8s cooldown
- [x] 8.9 On any exception → 20s cooldown, log error
- [x] 8.10 Concurrency guard: `_running` flag prevents overlapping tick execution
- [x] 8.11 Uses `threading.Thread(daemon=True)` for the HTTP calls to avoid blocking the Qt event loop
- [x] 8.12 `start()` and `stop()` methods to control the timer lifecycle
- [x] 8.13 `sync_with_settings()` method that starts/stops the timer based on the `autoUploadYouTube` setting

---

## Task 9: Wire Auto Upload Coordinator into app lifecycle

### Description
Instantiate `AutoUploadCoordinator` in the main window lifecycle, start it after authentication, and stop it on app close. Sync its timer with settings changes.

### Files to Modify
- `python_app/app/init_orchestrator.py`
- `python_app/app/main_window.py` (lifecycle hooks)
- `python_app/features/youtube/coordinator.py` (delegate to new coordinator when platform API mode active)

### Requirements Addressed
- Requirement 5 (operational lifecycle)

### Acceptance Criteria
- [x] 9.1 `AutoUploadCoordinator` instantiated in `init_orchestrator` with proper dependencies
- [x] 9.2 Coordinator `start()` called after main window is shown and authentication is confirmed
- [x] 9.3 Coordinator `stop()` called during app shutdown (before closing event)
- [x] 9.4 When `autoUploadYouTube` setting changes, `sync_with_settings()` is called to start/stop the timer accordingly
- [x] 9.5 Progress rows accessor provides current active progress data from the existing progress coordinator or DB

---

## Task 10: Update YouTube Uploads workspace page for Platform API data

### Description
Ensure the existing YouTube Uploads workspace table (`youtube_view.py`) can display jobs enqueued via the Platform API. The Refresh/Retry/Cancel buttons should work with API-sourced data.

### Files to Modify
- `python_app/views/youtube_view.py`
- `python_app/features/youtube/coordinator.py` (refresh logic adaptation)

### Requirements Addressed
- Requirement 7 (all acceptance criteria)

### Acceptance Criteria
- [x] 10.1 Table continues showing columns: Batch, Profile, Role, File, Status, Attempts, YouTube URL, Error
- [x] 10.2 Refresh button re-fetches job data (from local DB or Platform API depending on source)
- [x] 10.3 Retry button for failed jobs re-enqueues via `YouTubeConnectionClient.enqueue_upload()` and triggers `run_uploads()`
- [x] 10.4 Cancel button for pending/running jobs is supported (if the Platform API supports cancellation, otherwise disabled with tooltip explaining limitation)
- [x] 10.5 Jobs from both local upload path and platform API path are displayed in the same table
