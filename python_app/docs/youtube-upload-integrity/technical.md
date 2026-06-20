## YouTube Upload Integrity + No-Reupload - Technical

### Root Cause (Verified)
Auto-scan enqueue uses an upsert rule that previously flipped `FAILED → PENDING`, causing repeated reuploads:
- [db_enqueue_youtube_upload_job](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py#L188-L217)

### Fix Summary (Implemented)

#### 1) Prevent auto-resurrect of FAILED jobs
- DB enqueue now only auto-unblocks `BLOCKED → PENDING` (after connecting YouTube).
- `FAILED` stays `FAILED` until explicit retry.

#### 2) MP4 Readiness validation
Added a readiness gate before enqueue and before upload:
- `MainWindow._youtube_is_mp4_ready_for_upload(...)` verifies:
  - exists + readable
  - minimum size
  - not “very recent” mtime
  - deep mode: stable stat + `ffprobe duration > 0`
- Enforced from:
  - scan path: [MainWindow._youtube_scan_for_merged_outputs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4956-L4987)
  - enqueue path: [MainWindow._enqueue_youtube_upload_for_merge](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L4924-L4955)
  - worker pick path: [MainWindow._youtube_upload_tick](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L1248-L1290)

#### 3) Skip reupload when `youtube_video_id` exists
- Pending job pick now includes `youtube_video_id`/`youtube_url`/`error`:
  - [db_pick_pending_youtube_upload_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py#L266-L293)
- Worker logic:
  - If `youtubeVideoId` exists: skip `videos.insert` and only run post actions:
    - set thumbnail (always)
    - add to playlist only if prior error indicates playlist failure

#### 4) YouTube processing status check
- After upload completes, query:
  - `videos.list(part=status,processingDetails)`
  - If processing fails/rejected, mark job FAILED (keeps `youtube_video_id` so Boss can investigate without reupload loops).

Implementation:
- [youtube_uploader.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/youtube_uploader.py) adds:
  - `get_video_processing_status`
  - `set_thumbnail`
  - `add_to_playlist`

