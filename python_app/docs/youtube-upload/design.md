## YouTube Upload — Design

## Placement
- Settings → Profiles:
  - “Video template” (already exists)
  - “YouTube upload” section (new)
- Music page:
  - Add toggle beside Auto-Video: “Auto-Upload YouTube”
- Workspace:
  - New page/tab: “YouTube” (Recommended) showing upload queue and logs.

## Profile YouTube Section (Settings → Profiles)
### Fields
- Channel connection:
  - Status label: Connected / Not connected
  - Connected Channel: `<channelTitle> · <channelId>`
- Buttons:
  - Connect YouTube (opens browser OAuth flow)
  - Disconnect (revokes local stored credentials)
- Channel selection:
  - If the authenticated Google account has multiple YouTube channels, show a picker dialog:
    - List items: channel title + channel id
    - Confirm selection before saving the connection to the Profile
- Defaults:
  - Visibility dropdown (Private/Unlisted/Public/Scheduled)
  - Publish time picker (only when Scheduled; date is automatic from batchId)
  - Made for kids checkbox
  - Category dropdown (common categories, e.g. Music=10) with custom override
  - Playlist dropdown (fetched from YouTube for the connected channel)
    - When set, uploads automatically add the uploaded video to the selected playlist
  - Tags input (comma separated)
  - Title template text field
  - Description template multi-line field
  - AI use (altered/synthetic content) radio:
    - Yes → disclose via `status.containsSyntheticMedia = true`
    - No → `status.containsSyntheticMedia = false`

### Thumbnail
- Each batch run folder has its own thumbnail.
- Upload attaches the batch thumbnail automatically (no per-upload prompt):
  - prefer `thumbnail_<batchSuffix>.png`
  - else `thumbnail.png`
  - else newest file in `thumbnails/`

## YouTube Queue (New “YouTube” Page)
### Table columns
- Batch
- Profile
- Role
- File
- Status (PENDING/RUNNING/READY/FAILED)
- YouTube URL (when READY)
- Error (when FAILED)

### Actions
- Retry failed
- Cancel running
- Open YouTube link

## End-to-End Visual Flow
1) Music Generate → creates `batchId`
2) Auto-Gen Image → background/thumbnail
3) Auto-Video (after Suno) → per folder export + merge → produces merged MP4
4) Auto-Upload YouTube → detects merged MP4 → uploads for matching profile

## UX Safeguards
- If YouTube not connected for a profile, show “Waiting: YouTube not connected” instead of failing.
- If quota/auth fails, show explicit reason and require manual retry.
