## YouTube Upload Integrity + No-Reupload - Tasks

Status legend: pending | in progress | completed | blocked | needs review

---

## Phase 1 — Stop Reupload Loop (completed)
- [completed] Prevent enqueue upsert from flipping `FAILED → PENDING` automatically:
  - [youtube_db.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py)

## Phase 2 — Validate MP4 Before Upload (completed)
- [completed] Add MP4 readiness gate to prevent uploading incomplete merges:
  - [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py)

## Phase 3 — Skip Upload When Video Exists (completed)
- [completed] Include `youtube_video_id` in pending-job pick:
  - [db_pick_pending_youtube_upload_jobs](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py#L266-L293)
- [completed] If video id exists, skip reupload and run post-actions:
  - thumbnail update
  - playlist add (only when previously failed)

## Phase 4 — Post-Upload Processing Check (completed)
- [completed] Query `processingStatus` and mark job FAILED if YouTube reports failure/rejection.

## Phase 5 — QA (needs review)
- [needs review] Real-machine test with an actual channel:
  - Confirm no repeated uploads after a `FAILED`
  - Confirm upload doesn’t start while merge is still writing
  - Confirm “retry” on an existing job doesn’t reupload when `youtube_video_id` exists

