## UX

### Entry Point
- Progress page → right click a row → context menu.

### New Action
- Label: **Start YouTube Upload**
- Placement: beside existing YouTube actions (Retry/Cancel/Open URL).

### Enablement Rules
- Enabled only when:
  - Database is configured
  - Selected row has a valid output folder
  - Merge column contains a merged filename (not `—`) and the file exists inside the output folder
- Additionally:
  - If a YouTube job already exists, the action is disabled only while it is `PENDING`/`RUNNING` (use Cancel if needed). For `FAILED/BLOCKED/CANCELLED`, it can be used to queue again.
- Disabled otherwise.

### Behavior
- On click:
  - If profile is not connected to YouTube: show blocking warning dialog instructing to connect first.
  - If merged file missing/unready: show warning dialog.
  - Otherwise enqueue the YouTube upload job and show a short status message (same style as other Progress actions).

### Non-goals
- No file picker UI.
- No automatic Connect flow.
- No changes to the YouTube Uploads page.
