# Design Document

## Overview

This design adds platform-API-mediated YouTube connection management, publication defaults persistence, playlist fetching, and auto-upload orchestration to the Python desktop app — achieving feature parity with the Electron app's YouTube/Publication functionality.

All changes are confined to the Python desktop app (`python_app/`). No new platform API endpoints are created.

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Desktop App (python_app/)                                       │
│                                                                  │
│  ┌──────────────────────┐     ┌──────────────────────────────┐  │
│  │  Settings View        │     │  YouTube Uploads View         │  │
│  │  ├─ YouTube Tab (new) │     │  (existing, updated)          │  │
│  │  └─ Publication Tab   │     └──────────────────────────────┘  │
│  │     (updated)         │                                       │
│  └──────────┬────────────┘                                       │
│             │ uses                                                │
│  ┌──────────▼────────────┐     ┌──────────────────────────────┐  │
│  │  YouTubeConnection     │     │  AutoUploadCoordinator        │  │
│  │  Controller (new)      │     │  (new coordinator)            │  │
│  └──────────┬────────────┘     └──────────┬───────────────────┘  │
│             │ uses                          │ uses                 │
│  ┌──────────▼─────────────────────────────▼───────────────────┐  │
│  │  YouTubeConnectionClient (new service client)               │  │
│  │  Methods: list_connections, start_connection,               │  │
│  │  select_channel, disconnect, resync, list_playlists,        │  │
│  │  enqueue_upload, run_uploads                                │  │
│  └──────────┬─────────────────────────────────────────────────┘  │
│             │ httpx (sync, authenticated)                         │
└─────────────┼────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  Platform API            │
│  GET  /youtube/connections           │
│  POST /youtube/profiles/{id}/connect │
│  POST /youtube/connect-sessions/{id}/select-channel │
│  DELETE /youtube/profiles/{id}/connection │
│  POST /youtube/profiles/{id}/resync  │
│  GET  /youtube/profiles/{id}/playlists │
│  POST /youtube/profiles/{id}/uploads/merge │
│  POST /youtube/uploads/run           │
│  GET  /profiles                      │
│  PUT  /profiles/{id}                 │
└─────────────────────────┘
```

## New Files

| File | Purpose |
|------|---------|
| `python_app/services/youtube_connection_client.py` | Authenticated httpx client wrapping all Platform API YouTube endpoints |
| `python_app/features/youtube/connection_controller.py` | UI controller for the YouTube Settings Tab (connection flow logic) |
| `python_app/features/youtube/auto_upload_coordinator.py` | Timer-based background coordinator for auto-enqueue/run via Platform API |

## Modified Files

| File | Change |
|------|--------|
| `python_app/views/settings_view.py` | Replace the existing YouTube tab content with the Connection Panel UI; update Publication tab to read/write from profile youtube_config via API |
| `python_app/app/bootstrap.py` | Instantiate `YouTubeConnectionClient` and set as app property |
| `python_app/app/init_orchestrator.py` | Wire `ConnectionController` and `AutoUploadCoordinator` into the main window lifecycle |
| `python_app/views/youtube_view.py` | (Minor) ensure table refresh can accept API-sourced job data |
| `python_app/features/youtube/coordinator.py` | Add method to delegate auto-upload to the new `AutoUploadCoordinator` when Platform API mode is active |

## Detailed Design

### 1. YouTubeConnectionClient (`python_app/services/youtube_connection_client.py`)

Follows the exact same pattern as `ProfileClient`:
- Constructor: `__init__(*, token_store: TokenStorePort, base_url: str, timeout: float)`
- Internal `_request(method, path, **kwargs)` with bearer auth, 401-refresh retry, session-expired trigger
- Methods return typed dicts or dataclasses

```python
class YouTubeConnectionClient:
    def list_connections(self) -> list[dict]:
        """GET /youtube/connections → connections list"""

    def start_connection(self, profile_id: str) -> dict:
        """POST /youtube/profiles/{profile_id}/connect → {session_id, auth_url, status}"""

    def select_channel(self, session_id: str, channel_id: str) -> dict:
        """POST /youtube/connect-sessions/{session_id}/select-channel"""

    def disconnect(self, profile_id: str) -> None:
        """DELETE /youtube/profiles/{profile_id}/connection"""

    def resync(self, profile_id: str) -> dict:
        """POST /youtube/profiles/{profile_id}/resync"""

    def list_playlists(self, profile_id: str) -> list[dict]:
        """GET /youtube/profiles/{profile_id}/playlists → playlists list"""

    def enqueue_upload(self, profile_id: str, *, batch_id: str, role: str, merged_mp4_path: str) -> dict:
        """POST /youtube/profiles/{profile_id}/uploads/merge"""

    def run_uploads(self, *, batch_id: str | None = None, limit: int = 1) -> dict:
        """POST /youtube/uploads/run"""
```

### 2. YouTube Connection Controller (`python_app/features/youtube/connection_controller.py`)

A UI controller (not a coordinator — it handles user-driven actions, not background orchestration) that:

- Manages the YouTube Settings Tab state
- Holds a reference to `YouTubeConnectionClient`, the profile list, and the current profile selection
- Implements action handlers: `on_connect`, `on_restart`, `on_select_channel`, `on_resync`, `on_disconnect`
- Manages a QTimer for polling during `pending_browser` state (5s interval)
- Updates widget state via direct widget references (same pattern as existing `youtube_oauth_controller.py`)

State machine:
```
not_connected → [Connect] → pending_browser → [OAuth callback detected] → awaiting_channel_selection or connected
pending_browser → [Restart] → pending_browser (new session)
awaiting_channel_selection → [Select Channel] → connected
connected → [Disconnect] → not_connected
connected → [Resync] → connected (refreshed)
error → [Try Again] → pending_browser
```

### 3. Auto Upload Coordinator (`python_app/features/youtube/auto_upload_coordinator.py`)

A background coordinator following the `ProgressCoordinator` pattern:

- Receives dependencies via constructor injection (host protocol, youtube_connection_client, settings_accessor, timer_factory, logger)
- Creates a QTimer (6s interval) that calls `_tick()`
- `_tick()` logic:
  1. If `_running` flag is set, skip (prevents concurrent execution)
  2. Check `autoUploadYouTube` setting — if disabled, return
  3. Get active progress rows from the host
  4. Apply candidate selection logic (mirrors `selectNextAutoYouTubeCandidate` from Electron)
  5. Check per-key cooldowns
  6. Set `_running = True`
  7. Call `enqueue_upload()` → if blocked, 60s cooldown
  8. Call `run_uploads()` → 8s cooldown on success
  9. On exception → 20s cooldown
  10. Set `_running = False`

Since the Python app is single-threaded Qt, the HTTP calls will block briefly. Use a `QThread` worker or `threading.Thread` to avoid freezing the UI (same pattern as existing YouTube uploader).

### 4. YouTube Settings Tab UI

Replace the existing "YouTube" tab in `settings_view.py` (which currently shows OAuth app management for local device flow) with a connection-focused UI:

**Left Panel — Channel Connection:**
- Profile selector dropdown
- Connection status label (MiniStat-style)
- Channel display (title + ID in a styled container)
- Channel selector dropdown (visible only during `awaiting_channel_selection`)
- Action buttons row: Connect/Restart/Try Again, Resync, Disconnect

**Right Panel — Channel Access:**
- 3 info labels: Selected profile, Returned channels count, Session state
- Current state text display
- Connected channel text display
- Help text about publication settings

### 5. Publication Tab Updates

The existing Publication tab already has the correct form fields. Changes needed:

1. **Data source**: Load field values from the profile's `youtube_config` (already done via `map_api_profile_to_runtime` in `ProfileClient`)
2. **Save action**: Build `youtube_config` payload and call `PUT /profiles/{profile_id}` (using existing `ProfileClient.update_profile()` with `build_api_profile_payload()`)
3. **Playlist dropdown**: Switch from local Google API fetch to `YouTubeConnectionClient.list_playlists(profile_id)`
4. **Connection status**: Fetch from `YouTubeConnectionClient.list_connections()` and display read-only status
5. **Dirty tracking**: Compare current form values against loaded values to enable/disable Save button

### 6. Bootstrap Wiring

In `bootstrap.py`, after creating `profile_client`:

```python
from python_app.services.youtube_connection_client import YouTubeConnectionClient

youtube_connection_client = YouTubeConnectionClient(
    base_url=platform_api_base_url,
    token_store=token_store,
)
app.setProperty("youtube_connection_client", youtube_connection_client)
```

In `init_orchestrator.py`, wire the controller and coordinator into the main window after construction.

## Correctness Properties

### Property 1: Connection State Machine Transitions

For all valid (current_status, action) pairs, applying the action to the YouTube Connection Controller produces a valid next state consistent with the state machine defined above.

### Property 2: Publication Save Round-Trip

For all valid youtube_config values, saving via `PUT /profiles/{profile_id}` and then loading via `GET /profiles` returns equivalent field values (round-trip property on the config serialization).

### Property 3: Auto Upload Candidate Selection Consistency

For all sets of progress rows, the Python `AutoUploadCoordinator` candidate selection logic produces the same candidate (or None) as the Electron `selectNextAutoYouTubeCandidate` function given equivalent input data.

### Property 4: Cooldown Enforcement

For all sequences of tick invocations, the Auto Upload Coordinator never initiates a new upload for a candidate key within its active cooldown window (8s/20s/60s depending on the previous result).

### Property 5: No Concurrent Orchestration

For all interleaving of timer ticks and completion callbacks, the Auto Upload Coordinator never has more than one enqueue-and-run cycle in flight simultaneously.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Network timeout on any Platform API call | Raise `NetworkError`, display in status label, no crash |
| 401 on first attempt | Attempt token refresh (same as ProfileClient), retry once |
| 401 after refresh | Trigger session-expired flow (return to login) |
| OAuth browser not opened (permission error) | Show error in connection status, log warning |
| Polling timer fires while previous poll is still in-flight | Skip (guard flag prevents re-entrance) |
| Enqueue returns "blocked" | Apply 60s cooldown, log reason, continue polling |
| Unknown status from API | Treat as "error" state, display raw message from API |

## Migration Path

The local device OAuth flow (`youtube_oauth.py`, `youtube_oauth_controller.py`) remains intact and functional. The new platform-API flow is an alternative that the connection controller uses. The existing local flow is not removed — it can serve as a fallback if the platform API is unreachable, but the new UI defaults to the platform API flow.

The `AutoUploadCoordinator` operates independently from the existing `YouTubeCoordinator` upload logic. When `autoUploadYouTube` is enabled and the platform API is reachable, the new coordinator handles enqueue/run. The old coordinator's local upload path remains for manual/retry operations.
