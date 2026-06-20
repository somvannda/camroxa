# YouTube Upload — Requirements

## Goal
- After a channel folder finishes producing a merged MP4, automatically upload that merged MP4 to YouTube for the corresponding channel profile.
- The upload must be profile-aware (each Profile maps to a specific YouTube account/channel and upload configuration).

## User Stories
1) As Boss, I can connect a YouTube account to each Profile so uploads go to the correct YouTube channel.
2) As Boss, I can set per-profile YouTube defaults (privacy, title template, description template, tags, category).
3) As Boss, I can enable Auto-Upload so the pipeline runs end-to-end: Music → Image → Video Export → Merge → YouTube Upload.
4) As Boss, I can see upload status per batch/channel (queued/running/success/failed) and retry failures.
5) As Boss, I can pause/stop uploads and prevent duplicate uploads.
6) As Boss, if a Google login has multiple YouTube channels, I can select which channel to bind to a Profile.
7) As Boss, I can set the YouTube “AI use / altered or synthetic content” disclosure per Profile, and it is applied automatically on upload.

## Scope (Phase 1)
### Trigger
- Upload starts only when these are true for a given (batchId, profileId, role):
  - merged MP4 exists in that channel folder
  - profile has a YouTube account connected
  - Auto-Upload toggle is enabled

### Upload Behavior
- Upload uses YouTube Data API v3 `videos.insert` with resumable upload.
- Upload must support large files and unstable connections (resume/retry).
- Upload must store the resulting `youtubeVideoId` and the final URL.
- Upload visibility must be configurable per profile:
  - `unlisted` | `public` | `private`
  - `scheduled` (select time) where the app uploads as `private` and sets `publishAt`.

### Configuration (per Profile)
- `youtubeAccountId` (internal id referencing stored OAuth credentials)
- `visibilityMode`: `private` | `unlisted` | `public` | `scheduled`
- `publishAt` (optional; required when `visibilityMode=scheduled`, RFC3339, must be in the future)
- `categoryId` (default YouTube category id)
- `titleTemplate` and `descriptionTemplate`
  - must support placeholders like `{profileName}`, `{batchDate}`, `{songCount}`, `{templateName}`
- `tags` list (optional)
- `madeForKids` boolean (default false)
- `containsSyntheticMedia` boolean (default false)
  - maps to YouTube Data API `status.containsSyntheticMedia` (“AI use / altered or synthetic content” disclosure)

### UI/UX
- Settings → Profiles:
  - Add YouTube connection status (“Connected / Not connected”)
  - Add button: “Connect YouTube”
  - Add button: “Disconnect”
  - Show connected channel name and channel id
  - If OAuth login returns multiple channels, prompt the user to select the channel before saving the connection
  - Add “AI use” field (Yes/No) under the YouTube upload defaults
- Music page toggle row:
  - Auto-Upload YouTube
- A queue/table view (location decision):
  - Either in Image page footer area, or a new “YouTube” workspace tab.
  - Must show: profile, batch, file name, status, error, retry action.

## Constraints / Notes
- YouTube uploads require OAuth 2.0 user consent (API key is not sufficient).
- If the Google Cloud project is not verified for sensitive scopes, uploads may be restricted to `private`.
- Quota is limited; large-scale batch uploads may hit daily quota.
- No secrets (client secret, refresh token) should ever be logged.
- OAuth client id/secret are configured once for the app (single client) and used to connect multiple Google accounts/channels.

## Non-Goals (Phase 1)
- No automatic thumbnails upload.
- No playlist management.
