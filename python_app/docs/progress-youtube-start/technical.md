## Existing Architecture

### Progress Context Menu
- Built in [MainWindow._on_progress_table_context_menu](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L6356-L6496)
- Current YouTube actions depend on `meta["youtubeJobUid"]` and `meta["youtubeUrl"]`.

### YouTube Upload Enqueue
- Jobs are inserted/updated via [db_enqueue_youtube_upload_job](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py#L189-L225).
- MainWindow uses [MainWindow._enqueue_youtube_upload_for_merge](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L5492-L5526) to create jobs for merged MP4 files.

## Proposed Change

### Context Menu Action
Add a new QAction: `Start YouTube Upload`.

### Source of MP4
- Use the selected Progress row’s:
  - `outDir` from `meta`
  - merge filename from the Progress table “Merge” column (index 7), expecting `MERGED_*.mp4`.
- Build full path: `Path(outDir) / merge_filename`.

### Validation & Guards
- Require `self.db_cfg` (already used by existing menu gates).
- Require `outDir` exists and merged file exists.
- If `youtubeJobUid` exists and its status is not `PENDING/RUNNING`, the action forces it back to `PENDING` (restart).
- If `youtubeJobUid` is empty, it creates a new job via `_enqueue_youtube_upload_for_merge(...)`.
- Check profile YouTube connection using `db_get_youtube_account(...)` and ensure refresh token exists; if not, show `QMessageBox.warning` and return without enqueue.
- Validate MP4 readiness using `self._youtube_is_mp4_ready_for_upload(path, deep=False)` to avoid re-queuing broken or incomplete output.

### Enqueue
- Call `self._enqueue_youtube_upload_for_merge(batch_id=..., profile_id=..., role=..., merged_mp4_path=...)`.
- Refresh UI via `self._refresh_progress_table_async(force=True)`.
- After enqueue/restart, trigger `self._youtube_upload_tick(force=True)` so manual Start/Retry works even when auto-upload is disabled.

## Risk / Notes
- This feature does not change OAuth/connect behavior.
- It relies on existing merge naming and the output folder path being correct.

## Implemented
- Implemented in [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L6356-L6530)
- Adds `Start YouTube Upload` action, enabled only when:
  - no existing `youtubeJobUid`
  - merged file exists at `outDir/mergeColumnValue`
- Click handler validates connection and enqueues via `_enqueue_youtube_upload_for_merge(...)`
