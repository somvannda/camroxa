## Progress → Start YouTube Upload (No Job)

### Goal
Add a context menu action on the Progress page that can enqueue a YouTube upload job when the selected row has no existing YouTube job.

### Scope
- Add a new right-click menu item in the Progress table: **Start YouTube Upload**
- Enabled for rows that:
  - have DB configured
  - have a merged MP4 value in the Merge column (file exists)
  - do not have an in-flight YouTube upload (`PENDING`/`RUNNING`)

### Tasks
- [x] Add new menu action in `MainWindow._on_progress_table_context_menu`
- [x] Determine merged MP4 path from selected row (Merge column + outDir)
- [x] Validate merged MP4 exists and is ready for upload
- [x] Validate YouTube account is connected for the profile; otherwise show warning and do not enqueue
- [x] Enqueue upload job using existing helper `_enqueue_youtube_upload_for_merge(...)`
- [x] Refresh Progress table after enqueue

### Validation
- [ ] Row with `YouTube = —` and `Merge != —` shows enabled “Start YouTube Upload”
- [ ] Clicking “Start YouTube Upload” creates a YouTube job and Progress row updates to `Queued` (or `Failed/Blocked` depending on worker result)
- [ ] If profile is not connected, show a warning and do not create a job
- [ ] Rows that already have YouTube job show Retry/Cancel behavior unchanged
