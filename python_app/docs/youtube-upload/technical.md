## YouTube Upload — Technical

## Existing Architecture (verified)
- Profiles are stored in Postgres and loaded into memory (`music_data["profiles"]`).
- Each profile already maps to a `videoTemplateId` for correct template selection.
- Video pipeline produces a merged MP4 per channel folder.
- YouTube OAuth connect stores an encrypted refresh token per Profile in `youtube_accounts`.
- Upload worker uses YouTube Data API v3 `videos.insert` with resumable upload and updates `youtube_upload_jobs`.

## Provider API
- Use YouTube Data API v3 `videos.insert` for uploads.
- Use **resumable upload** for reliability and recovery on timeouts.
- OAuth scopes:
  - required: `https://www.googleapis.com/auth/youtube.upload`
  - recommended: `https://www.googleapis.com/auth/youtube.readonly` (for `channels.list` during connect)
  - required for playlist auto-add: `https://www.googleapis.com/auth/youtube.force-ssl` (for `playlistItems.insert`)
 - Thumbnail API:
  - `thumbnails.set` after successful `videos.insert`

References:
- Upload guide: https://developers.google.com/youtube/v3/guides/uploading_a_video
- OAuth installed apps: https://developers.google.com/youtube/v3/guides/auth/installed-apps
- videos.insert doc: https://developers.google.com/youtube/v3/docs/videos/insert

## New Data Model (Postgres)
### Table: `youtube_accounts`
- `id` (uuid/text) primary key
- `profile_id` (text) unique, references profiles.uid (logical)
- `channel_id` text
- `channel_title` text
- `refresh_token_enc` text (DPAPI-encrypted, base64)
- `scopes` text
- `created_at`, `updated_at`

### Table: `youtube_upload_jobs`
- `id` serial primary key
- `job_uid` text unique (e.g., `yt-{batchId}-{profileId}-{role}`)
- `batch_id` text
- `profile_id` text
- `role` text (OK/ALT)
- `file_path` text (merged mp4 path)
- `status` text (PENDING/RUNNING/READY/FAILED)
- `attempt_count` int
- `error` text
- `youtube_video_id` text
- `youtube_url` text
- `created_at`, `updated_at`

### Table: `youtube_upload_history` (optional Phase 2)
- to prevent duplicates if the same file is regenerated

## Token Storage (Security)
- Do not log OAuth tokens.
- Store refresh tokens in Postgres **encrypted with Windows DPAPI** (no extra crypto dependency), per profile.
- Store OAuth client credentials (client_id/client_secret) in app Settings fields:
  - `youtubeClientId`, `youtubeClientSecret`
  - do not log these values
 - Use a single OAuth client for the app to connect multiple Google accounts/channels.

## OAuth Flow (Desktop App)
- Use “Installed App / Loopback” redirect method:
  1) Launch browser to Google consent screen
  2) Local loopback server receives authorization code
  3) Exchange code → access_token + refresh_token
  4) Store refresh_token for that profile

## Multi-Channel Selection (new)
- Problem: a single Google login may manage multiple YouTube channels (including Brand Accounts).
- Target behavior:
  - Run OAuth once to obtain a refresh token
  - Query `channels.list(mine=true)` after authentication
  - If exactly one channel is returned, bind it to the Profile automatically
  - If multiple channels are returned, present a UI picker and store the selected channel id/title alongside the refresh token for the Profile
- Data:
  - Keep storing one connected YouTube identity per Profile via `youtube_accounts(profile_id unique)`.
  - Store `channel_id` + `channel_title` for display and for future audit/debug (no secrets).

## Upload Engine
- Implement `services/youtube_uploader.py`:
  - `ensure_youtube_auth(profile_id)` returns access token (refresh if expired)
  - `start_resumable_upload(file_path, metadata)` creates upload session
  - `upload_chunks(session_url, chunk_size)` with retry on 5xx/timeouts
  - `finalize` returns `youtubeVideoId`
- Metadata:
  - `privacyStatus`: `private` | `unlisted` | `public`
  - `publishAt` (RFC3339, optional): only when scheduling; computed as `batchDate + profilePublishTime`.
  - `containsSyntheticMedia` (boolean): maps to `status.containsSyntheticMedia` (AI use / altered or synthetic content disclosure).

## Category Handling
- Store `youtubeCategoryId` as the numeric category id string (e.g. `10` for Music).
- UI provides a dropdown of common categories plus a custom override option.

## Playlist Handling
- Profile stores a default `youtubePlaylistId`.
- UI fetches playlists for the connected channel via `playlists.list(mine=true)` and shows them in a dropdown.
- Upload worker adds the uploaded video to the selected `youtubePlaylistId` using `playlistItems.insert` when a playlist is selected.
- If the connected YouTube account scopes do not include `youtube.force-ssl`, playlist auto-add will fail until the profile reconnects and grants the updated scopes.

## Scheduling (Batch Date)
- Profile stores publish time only (HH:MM) in the existing `youtubePublishAt` field for backward compatibility:
  - If the stored value contains a full datetime, extract and show its time in UI.
  - New saves store only HH:MM when visibility is Scheduled.
- Upload worker parses `batchDate` from `batchId` and combines it with the profile time to create the final RFC3339 publishAt.
- If multiple batches share the same batchDate, the app blocks schedule collisions for the same profile/time with an actionable error.

## Thumbnail Upload
- Resolve thumbnail for a YouTube job from the batch run folder for its role (OK/ALT).
- Preferred candidates:
  - `thumbnail_<batchSuffix>.png`
  - `thumbnail.png`
  - newest file under `thumbnails/`
- After `videos.insert` returns `videoId`, call `thumbnails.set(videoId, media_body=<thumbnail>)`.

## Scheduler + Orchestration
- Add a 30s scheduler (QTimer) similar to image/video schedulers:
  - scans for READY merged mp4 outputs per (batchId, profileId, role)
  - if Auto-Upload is enabled and profile has YouTube account:
    - enqueue `youtube_upload_jobs` row if not exists
    - run a worker thread to upload, updating job status

## Failure Handling
- Retry transient failures (timeouts, 5xx) with exponential backoff and max attempts (e.g., 5).
- Non-retryable failures:
  - invalid_grant (refresh token revoked) → require reconnect
  - quota exceeded → require next-day retry or quota increase

## Dependencies (decision)
Recommended (official Google libs):
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

Alternative (fewer deps, more engineering risk):
- implement OAuth + resumable upload protocol manually with `urllib.request`
