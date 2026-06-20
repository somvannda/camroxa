# YouTube Progress + Remove YouTube Page — technical

## Existing Code (Verified)

### Upload worker + progress callbacks
- Background auto-upload tick: [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1505-L1756)
- Progress callback emitted from upload thread:
  - `youtube_upload_progress` event: [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1691-L1693)
- Job table (DB): `youtube_upload_jobs` accessed via [youtube_db.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/youtube_db.py)

### Progress page
- UI columns: [progress_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/progress_view.py#L65-L76)
- Row generation: `_collect_progress_rows()` in [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L5582-L5742)
- Table rendering: `_apply_progress_rows()` in [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L5568-L5581)

### Profile defaults used for upload (current)
- Upload resolves profile using in-memory `self.music_data["profiles"]` via `self._music_profile_by_id(pid)`:
  - [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1559-L1561)
- It applies per-profile defaults:
  - title/description templates, visibility mode, schedule time, tags, category, made-for-kids, AI use, playlist:
  - [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1574-L1712)

## Proposed Changes

### 1) Add YouTube column to Progress table
- Update `progress_view.py`:
  - Increase column count by 1
  - Insert `YouTube` header (recommended placement: after `Merge`)
- Update `main.py` `_apply_progress_rows()` key list to include `youtube`.

### 2) Query YouTube jobs for the batches on screen
- Add `database/youtube_db.py` helper:
  - `list_youtube_upload_jobs_for_batches(cfg, batch_ids, profile_ids)` returning latest job per `(batch_id, profile_id, role)`.
- This avoids calling `db_list_youtube_upload_jobs(limit=2000)` and filtering in Python.

### 3) Live percent without DB schema change
- Add `MainWindow._youtube_progress_by_job_uid: dict[str, float]`:
  - Updated whenever `youtube_upload_progress` is received.
  - On `youtube_upload_done`, set to 1.0 (or clear).
- In `_collect_progress_rows()`:
  - join DB job status by `(batchId, profileId, role)`
  - show:
    - `Uploading {pct}%` when DB status is RUNNING and cache has value
    - `Done` when READY
    - `Failed` when FAILED/BLOCKED
    - `Queued` when PENDING

### 4) Ensure upload uses latest profile settings
- Before uploading, re-fetch profiles from DB and resolve the profile by `profileId`:
  - Use `db_list_profiles(self.db_cfg)` and find the matching id.
- This ensures “Profile settings page of each channel” is the real source of truth even if in-memory cache is stale.

### 5) Remove YouTube workspace page (UI only)
- Remove YouTube nav entry from [core_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/core_view.py).
- Remove YouTube stacked page and mixin from [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py).
- Keep the auto-upload worker/timer; Progress page becomes the monitoring surface.

## Risks & Mitigations
- **Progress % not persisted**: acceptable; DB status still accurate. Document limitation.
- **Duplicate YouTube jobs per row**: handle by picking most recent by `updated_at`.

## Validation Checklist
- Start an upload, keep Progress page open, confirm YouTube column updates as % changes.
- Confirm title/description/visibility/schedule/category/tags/AI use match the selected profile settings.
- Remove YouTube page; confirm app still uploads and Progress still shows it.
