# Requirements Document

## Introduction

Bring the Python desktop app's YouTube and Publication features to parity with the Electron app by switching from local device OAuth and direct Google API calls to the platform API's server-mediated flow. This includes a dedicated YouTube connection tab in Settings, API-backed publication defaults via the profile's `youtube_config` field, playlist fetching from the platform API, and auto-upload orchestration using the existing `POST /youtube/profiles/{profile_id}/uploads/merge` and `POST /youtube/uploads/run` endpoints.

## Glossary

- **Platform_API**: The FastAPI backend at `platform_api/` providing authenticated REST endpoints for YouTube connections, profiles, uploads, and settings.
- **Desktop_App**: The PyQt6 desktop application at `python_app/` targeting Windows.
- **YouTube_Connection_Client**: A new service client class in `python_app/services/` that wraps Platform_API YouTube endpoints using the same pattern as `ProfileClient`.
- **YouTube_Settings_Tab**: A new tab in the Desktop_App Settings page showing connection status, channel info, and action buttons for the selected profile.
- **Publication_Tab**: The existing Publication section in the Desktop_App Settings page, updated to read and write `youtube_config` via the Platform_API profile endpoint.
- **Auto_Upload_Coordinator**: A background timer-based coordinator in the Desktop_App that polls progress rows and enqueues YouTube uploads via the Platform_API.
- **Connection_Status**: One of `not_connected`, `pending_browser`, `awaiting_channel_selection`, `connected`, `error` as returned by `GET /youtube/connections`.
- **Profile**: A channel profile object managed via `GET /profiles` and `PUT /profiles/{profile_id}`, containing a `youtube_config` JSON field.
- **Token_Store**: The existing `TokenStore` service providing JWT access/refresh tokens for authenticated Platform_API requests.

## Requirements

### Requirement 1: YouTube Connection Client

**User Story:** As a developer, I want a reusable service client for YouTube Platform_API endpoints, so that all YouTube connection and upload operations go through a single authenticated client.

#### Acceptance Criteria

1. THE YouTube_Connection_Client SHALL expose the following methods mapped to Platform_API endpoints: `list_connections()`, `start_connection(profile_id)`, `select_channel(session_id, channel_id)`, `disconnect(profile_id)`, `resync(profile_id)`, `list_playlists(profile_id)`, `enqueue_upload(profile_id, batch_id, role, merged_mp4_path)`, and `run_uploads(batch_id, limit)`.
2. THE YouTube_Connection_Client SHALL authenticate every request by attaching a bearer token from the Token_Store; IF a request receives an HTTP 401 response, THEN THE YouTube_Connection_Client SHALL attempt exactly one token refresh via the auth_client and retry the original request with the new token.
3. IF token refresh fails or the retried request still returns HTTP 401, THEN THE YouTube_Connection_Client SHALL invoke the session-expired trigger and raise AuthenticationError.
4. THE YouTube_Connection_Client SHALL map HTTP error responses to structured exceptions: 401 to AuthenticationError, 422 to ValidationError (including per-field errors from the response body), and all other 4xx/5xx to PlatformAPIError — all from the existing api_errors module.
5. IF an httpx ConnectError, TimeoutException, or NetworkError occurs, THEN THE YouTube_Connection_Client SHALL raise NetworkError with the underlying exception message and a null status_code.
6. THE YouTube_Connection_Client SHALL accept `base_url` and `token_store` (conforming to TokenStorePort) via constructor injection, and use a default request timeout of 15 seconds.
7. THE YouTube_Connection_Client SHALL use synchronous httpx.Client calls consistent with ProfileClient, creating a single httpx.Client instance in the constructor and exposing a `close()` method for resource cleanup.

### Requirement 2: YouTube Settings Tab

**User Story:** As a user, I want a dedicated YouTube tab in Settings showing my channel connection state and actions, so that I can connect, disconnect, or resync my YouTube channel for each profile.

#### Acceptance Criteria

1. WHEN the YouTube Settings Tab is opened, THE Desktop_App SHALL display a profile selector dropdown populated from the user's channel profiles retrieved via the platform API.
2. WHEN a profile is selected, THE Desktop_App SHALL fetch the connection status from `GET /youtube/connections` and display: the `status` label, `channel_title`, and `channel_id` fields from the matching connection response.
3. WHILE the connection status is `not_connected`, THE Desktop_App SHALL enable a "Connect Channel" button and disable the "Resync Channel Data" and "Disconnect" buttons.
4. WHEN the user clicks "Connect Channel", THE Desktop_App SHALL call `POST /youtube/profiles/{profile_id}/connect` and open the returned `auth_url` in the system default browser.
5. WHILE the connection status is `pending_browser`, THE Desktop_App SHALL display "Waiting for browser sign-in" and enable a "Restart Sign-In" button.
6. WHEN the user clicks "Restart Sign-In", THE Desktop_App SHALL call `POST /youtube/profiles/{profile_id}/connect` to obtain a new `auth_url` and open it in the system default browser, replacing the current pending session.
7. WHILE the connection status is `awaiting_channel_selection`, THE Desktop_App SHALL display a channel selector dropdown populated from the connection response's `channels` array and an "Attach Channel" button.
8. WHEN the user selects a channel and clicks "Attach Channel", THE Desktop_App SHALL call `POST /youtube/connect-sessions/{session_id}/select-channel` with the chosen `channel_id`.
9. WHILE the connection status is `connected`, THE Desktop_App SHALL display the `channel_title` and `channel_id`, and enable "Resync Channel Data" and "Disconnect" buttons.
10. WHEN the user clicks "Resync Channel Data", THE Desktop_App SHALL call `POST /youtube/profiles/{profile_id}/resync` and update the displayed `channel_title` and `channel_id` from the response.
11. WHEN the user clicks "Disconnect", THE Desktop_App SHALL call `DELETE /youtube/profiles/{profile_id}/connection` and reset the display to the `not_connected` state.
12. WHILE the connection status is `error`, THE Desktop_App SHALL display the `message` field from the connection response and enable a "Try Again" button that initiates a new connection by calling `POST /youtube/profiles/{profile_id}/connect`.
13. THE Desktop_App SHALL poll `GET /youtube/connections` every 5 seconds while the connection status is `pending_browser`, up to a maximum duration of 300 seconds, after which it SHALL stop polling and display a timeout message with a "Try Again" button.
14. IF any YouTube API call returns an error response, THEN THE Desktop_App SHALL display an error message indicating the failure reason from the response and re-enable the action button that triggered the call.
15. IF the user has zero channel profiles, THEN THE Desktop_App SHALL display a message indicating no profiles are available and disable the profile selector dropdown.

### Requirement 3: Publication Tab API Integration

**User Story:** As a user, I want my publication defaults (visibility, category, tags, templates, etc.) to be saved to the platform API per profile, so that they persist across devices and are used by the server-mediated upload flow.

#### Acceptance Criteria

1. WHEN a profile is selected in the Publication_Tab, THE Desktop_App SHALL populate form fields from the profile's `youtube_config` object as returned by `GET /profiles`.
2. THE Publication_Tab SHALL include form fields for: visibility, publish-at hour, publish-at minute, made-for-kids toggle, AI use, category, playlist, channel description (keywords), tags, title template, and description template.
3. WHEN visibility is set to "scheduled", THE Publication_Tab SHALL display publish-at hour and minute selectors.
4. WHEN visibility is not "scheduled", THE Publication_Tab SHALL hide publish-at hour and minute selectors.
5. WHEN the user clicks "Save Publication", THE Desktop_App SHALL build the `youtube_config` object and call `PUT /profiles/{profile_id}` with the updated youtube_config field.
6. THE Publication_Tab SHALL track dirty state by comparing current form field values against the last-loaded profile values; the Save button SHALL be disabled when values are identical and enabled when any field differs.
7. WHILE the selected profile has Connection_Status equal to `connected`, THE Desktop_App SHALL enable the Playlist dropdown and populate it from `GET /youtube/profiles/{profile_id}/playlists`.
8. WHILE the selected profile has Connection_Status not equal to `connected`, THE Desktop_App SHALL disable the Playlist dropdown and display "Connect YouTube first" as placeholder text.
9. WHEN the save request succeeds, THE Desktop_App SHALL display a success status message and reset the dirty state.
10. IF the save request fails, THEN THE Desktop_App SHALL display an error message indicating the failure reason and keep the form fields unchanged so the user can retry.

### Requirement 4: Playlist Fetching via Platform API

**User Story:** As a user, I want playlists to be fetched from the platform API rather than direct Google API calls, so that the Desktop_App does not require local Google OAuth credentials for playlist access.

#### Acceptance Criteria

1. WHEN a connected profile is selected in the Publication_Tab, THE Desktop_App SHALL call `GET /youtube/profiles/{profile_id}/playlists` via the YouTube_Connection_Client within a 10-second timeout.
2. WHEN the playlists response is received, THE Desktop_App SHALL populate the Playlist dropdown with a "No playlist" option (value="") as the first item followed by each playlist's `id` and `title` from the response, and SHALL pre-select the entry matching the profile's saved `youtubePlaylistId` (or "No playlist" if no saved value exists).
3. IF the playlists request fails (network error, timeout, or non-2xx response), THEN THE Desktop_App SHALL display the Playlist dropdown with "No playlist" as the only option and log the error.
4. IF the profile's saved `youtubePlaylistId` does not match any `id` in the playlists response, THEN THE Desktop_App SHALL append a "Missing · {id}" entry to the dropdown using the saved ID and select it.

### Requirement 5: Auto YouTube Upload Orchestration via Platform API

**User Story:** As a user, I want the Desktop_App to automatically enqueue and trigger YouTube uploads through the platform API when merged MP4 files are ready, so that the upload flow is consistent with the Electron app.

#### Acceptance Criteria

1. WHILE the `autoUploadYouTube` setting is enabled, THE Auto_Upload_Coordinator SHALL poll active progress rows every 6 seconds to detect upload candidates.
2. THE Auto_Upload_Coordinator SHALL select the next candidate by finding progress rows where: a merged MP4 path exists, the row is not in a terminal stage (done/error), no YouTube upload is pending/running/succeeded/failed/blocked, and the profile_id matches a known profile; when multiple candidates exist, THE Auto_Upload_Coordinator SHALL select the oldest candidate by run date, then by batch_id alphabetical order as tiebreaker.
3. WHEN a candidate is found, THE Auto_Upload_Coordinator SHALL call `POST /youtube/profiles/{profile_id}/uploads/merge` with the batch_id, role, and merged_mp4_path, where the candidate key is defined as the combination of batch_id and role.
4. IF the enqueue response has status "blocked", THEN THE Auto_Upload_Coordinator SHALL apply a 60-second cooldown for that candidate key (batch_id + role), during which the candidate is excluded from selection.
5. WHEN the enqueue succeeds (status is not "blocked"), THE Auto_Upload_Coordinator SHALL call `POST /youtube/uploads/run` with the batch_id and limit of 1.
6. WHEN a successful enqueue-and-run cycle completes, THE Auto_Upload_Coordinator SHALL apply an 8-second cooldown for that candidate key.
7. IF any request in the enqueue-and-run cycle fails with an exception or returns a non-success HTTP response (4xx or 5xx), THEN THE Auto_Upload_Coordinator SHALL apply a 20-second cooldown for that candidate key.
8. THE Auto_Upload_Coordinator SHALL prevent concurrent orchestration cycles by maintaining a running flag; IF a poll tick fires while a previous enqueue-and-run cycle is still in flight, THEN THE Auto_Upload_Coordinator SHALL skip that tick without queuing another cycle.

### Requirement 6: Connection Status Polling Coordinator

**User Story:** As a user, I want the YouTube tab to automatically detect when the OAuth browser flow completes, so that I do not need to manually refresh the page.

#### Acceptance Criteria

1. WHILE Connection_Status is `pending_browser` and the YouTube Settings Tab is the active visible tab, THE Desktop_App SHALL poll `GET /youtube/connections` every 5 seconds.
2. WHEN polling detects a status change from `pending_browser` to another status, THE Desktop_App SHALL stop polling and update the displayed Connection_Status label, channel title, and channel ID to reflect the new connection state.
3. WHEN the YouTube Settings Tab is no longer the active tab, the settings window is closed, or a different profile is selected, THE Desktop_App SHALL stop the active polling timer within 1 second.
4. IF a polling request fails due to a network error or non-2xx response, THEN THE Desktop_App SHALL continue polling at the next scheduled interval without displaying an error to the user, for up to 3 consecutive failures.
5. IF 3 consecutive polling requests fail, THEN THE Desktop_App SHALL stop polling and display a connection status indicating the poll could not reach the server.

### Requirement 7: YouTube Uploads Workspace Table

**User Story:** As a user, I want the existing YouTube Uploads workspace page to display jobs from the platform API upload system, so that I can see the status of API-enqueued uploads.

#### Acceptance Criteria

1. THE YouTube Uploads workspace page SHALL display upload job rows with columns: Batch, Profile, Role, File, Status, Attempts, YouTube URL, and Error, sorted by most recently updated first.
2. WHEN the user clicks "Refresh", THE Desktop_App SHALL re-fetch upload job data from the Platform_API and update the table within 5 seconds.
3. WHEN the user clicks "Retry" with a job in "failed" or "cancelled" status selected, THE Desktop_App SHALL re-enqueue the job by resetting its status to "pending" via the Platform_API and display a confirmation indicator in the Status column.
4. IF the user clicks "Retry" with a job that is not in "failed" or "cancelled" status, THEN THE Desktop_App SHALL keep the "Retry" button disabled for that selection.
5. WHEN the user clicks "Cancel" with a job in "pending" or "blocked" status selected, THE Desktop_App SHALL request cancellation via the Platform_API, set the job status to "cancelled", and update the row in the table.
6. IF the user clicks "Cancel" with a job that is not in "pending" or "blocked" status, THEN THE Desktop_App SHALL keep the "Cancel" button disabled for that selection.
