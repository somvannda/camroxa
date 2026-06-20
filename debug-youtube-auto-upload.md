# Debug Session: YouTube Auto Upload

- Session ID: `youtube-auto-upload`
- Status: OPEN
- Created: 2026-06-07

## User Report
- YouTube upload started unexpectedly.
- Terminal evidence selected by user:
  - `[10:09:39] Primary page changed: progress`
  - `[10:09:40] Primary page changed: music`
  - `[10:09:59] YouTube uploading: 2026-06-06-3-1780649479111 p:c200753707-ALT 6%`
  - `[10:10:06] Primary page changed: progress`
- User expectation: upload should not start unless explicitly intended.
- Requested improvement: clear all upload jobs when application closes.

## Initial Hypotheses
1. Auto-upload polling is enabled by persisted settings, so background timers are claiming pending YouTube jobs without any manual action.
2. There were already pending upload jobs in the database from an earlier session, and startup/page-change/timer logic resumed them automatically.
3. Page navigation indirectly triggers a refresh path that starts or resumes the YouTube auto worker.
4. Upload job state is not cleared on app shutdown, so stale pending/running jobs survive across sessions.
5. A background queue scanner is promoting merged outputs into upload jobs earlier than expected.

## Evidence To Collect
- Where auto-upload timers start and what gates them.
- Whether startup restore logic or page-change handlers call YouTube poll/claim functions.
- Whether persisted settings include `autoUploadYouTube`.
- Whether pending jobs are resumed from database state.
- Whether app shutdown currently clears or cancels YouTube jobs.

## Resolution Update (2026-06-08)
- Confirmed static root cause in `python_app/app/main_window.py`:
  - persisted `autoUploadYouTube=true` was restored on launch
  - `_refresh_music_ui()` -> `_refresh_music_runtime_controls()` -> `_sync_youtube_auto_poll_timer()` started the poll timer immediately
  - `_enqueue_youtube_upload_for_merge()` also scheduled `QTimer.singleShot(0, self._youtube_upload_tick)` for pending merged MP4 jobs
- Implemented startup manual-resume policy:
  - app now resets persisted `autoUploadYouTube` to `False` during startup hydration before music UI refresh
  - this keeps the toggle and runtime state aligned and prevents silent resume on launch/page refresh
- Implemented shutdown cleanup policy:
  - app now cancels unfinished Image/YouTube DB jobs during `closeEvent()`
  - active in-memory YouTube worker cancel events are signalled before shutdown completes
- Added visible Progress page action:
  - `Cancel All Jobs` button now appears beside `Refresh` and reuses the existing cancel-all handler

## Next Step
- Run manual UI verification: relaunch app, confirm YouTube auto-upload stays OFF on startup, then re-enable manually and verify cancel-all / shutdown cleanup behavior.
