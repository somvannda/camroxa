# YouTube Progress + Remove YouTube Page — design

## Product Goals
- Boss can monitor end-to-end pipeline progress from one place (Progress page).
- YouTube upload shows live progress percent while uploading.
- Per-profile/channel defaults are the source of truth for uploading.
- Remove the YouTube workspace page to reduce confusion once Progress covers it.

## Progress Page UX

### New Column: YouTube
- Column label: `YouTube`
- Display values:
  - `—` (no job)
  - `Queued`
  - `Uploading 0%` … `Uploading 100%`
  - `Done`
  - `Failed`

### Tooltips
- When available, show:
  - `jobUid`
  - `YouTube URL`
  - error message (for Failed)

### Context Menu (row)
- `Retry YouTube Upload`
- `Cancel YouTube Upload`
- `Open YouTube URL` (only if URL exists)

## Upload Correctness (Source of truth)
- Upload metadata must come from the selected Music Profile (per channel) settings:
  - visibility mode, schedule time
  - title/description templates
  - tags, category, made-for-kids
  - AI use disclosure
  - playlist (if configured)

## Page Removal
- After the above is working, remove the standalone YouTube page from navigation.
- The Profile settings (Settings → Profiles) remains for Connect/Disconnect and default values.

## Known Limitation (acceptable for now)
- Upload `%` is live and in-memory.
  - If app restarts mid-upload, Progress can still show RUNNING/FAILED/READY from DB, but `%` resets.
