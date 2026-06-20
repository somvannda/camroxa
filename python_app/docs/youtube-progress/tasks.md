# YouTube Progress + Remove YouTube Page — tasks

## Goal
- Show YouTube upload status + live percent progress inside the **Progress** page table.
- Ensure upload uses per-profile YouTube defaults (per channel) from the Profile settings UI.
- Remove the standalone **YouTube** workspace page after the above is complete.

## Status
- needs review (implementation complete; manual verification still required)

## Phase 1 — Inspect (completed)
- [x] Locate YouTube upload worker loop and progress callback emission.
- [x] Locate Progress page row computation and table columns.
- [x] Verify per-profile settings exist in Settings → Profiles (Connect/Disconnect + defaults).

## Phase 2 — Design (pending)
- [x] Add a new Progress table column: **YouTube**
  - Values:
    - `Queued` / `Uploading 42%` / `Done` / `Failed`
    - If done, show `Done` (optionally include URL in tooltip).
- [x] Add minimal context-menu actions on Progress rows:
  - `Retry YouTube Upload`
  - `Cancel YouTube Upload`
  - `Open YouTube URL` (when available)

## Phase 3 — Data Plumbing (pending)
- [x] Add a batch-query helper for YouTube upload jobs (avoid scanning all jobs):
  - `database/youtube_db.py`: `list_youtube_upload_jobs_for_batches(cfg, batch_ids, profile_ids)`
- [x] Add in-memory progress cache:
  - `MainWindow._youtube_progress_by_job_uid: dict[str, float]`
  - Updated by the existing `youtube_upload_progress` event.
- [x] Enrich `_collect_progress_rows()` to attach YouTube status per row:
  - Match by `(batchId, profileId, role)` → `youtube_upload_jobs`.
  - For RUNNING jobs, show cached percent; for READY show 100%.

## Phase 4 — Correct Profile Settings Source (pending)
- [x] Ensure upload uses the latest persisted profile settings (not stale in-memory):
  - Re-resolve profile from DB before upload starts.
- [x] Add a safety status line on start:
  - Show channel name + visibility mode + scheduled time (if scheduled) to confirm correct profile is being used.

## Phase 5 — Remove YouTube Page (pending)
- [x] Remove left-nav “YouTube” entry.
- [x] Remove YouTube workspace page from stacked pages.
- [x] Remove `YouTubeViewMixin` import/inheritance (keep upload background worker).
- [x] Note: [youtube_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/youtube_view.py) still exists but is unused (safe to delete in a dedicated cleanup task).

## Phase 6 — Verify (pending)
- [ ] Start upload and confirm Progress page shows `Uploading XX%` live. (needs review)
- [ ] Confirm upload metadata matches profile defaults (title template, visibility, AI use, tags, category, playlist, schedule time). (needs review)
- [ ] Retry/cancel actions work from Progress page. (needs review)
- [ ] App has no YouTube page but uploads still run. (needs review)

## Phase 7 — Document (pending)
- [x] Update `python_app/DEVELOPMENT_LOG.md` with:
  - new Progress column behavior
  - YouTube page removal
  - known limitation: upload % is live (in-memory) and resets on app restart
