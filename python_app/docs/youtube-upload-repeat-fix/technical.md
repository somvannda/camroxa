# YouTube Upload: Prevent Repeat Upload Loop (Technical)

## Root Cause (Verified)
- In `MainWindow._run_one_youtube_upload_job`, the pre-upload MP4 readiness check:
  - Calls `_youtube_is_mp4_ready_for_upload(file_path, deep=True)`.
  - When not ready, it sets the DB job back to `PENDING` **without incrementing `attempt_count`**.
- Result:
  - The job is reclaimed again on the next poll and repeats forever (especially when the output is invalid and will never become “ready”).

## Fix Strategy
- On “MP4 not ready”:
  - Persist the specific readiness reason in `error`.
  - Increment `attempt_count`.
  - Apply a max attempt threshold:
    - Higher threshold for “still writing/locked” cases.
    - Lower threshold for “invalid MP4” cases (duration/ffprobe errors).
  - Once threshold exceeded, mark job `FAILED` so it stops repeating.

## Affected Files
- `python_app/app/main_window.py`
- `python_app/docs/youtube-upload-repeat-fix/*`

