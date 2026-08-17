# Progress: skip disk scans on idle Long completed rows

**Date:** 2026-08-17  
**Surfaces:** `camxora_python` (desktop)  
**Branch:** `bugfix/progress-skip-idle-disk-scans`

## Summary

Progress felt frozen (right-click did nothing) because every poll listed and
stat'd every run folder — including albums that already showed **Long
completed** — and the context menu walked `F:\Suno\...` on the UI thread
before it could open.

## Product impact

- Idle Long completed / Completed / `pipeline_complete` rows are not re-scanned
  on Progress or auto-video polls.
- Right-click uses overlay counters and the last worker cache only. The menu
  should open immediately.
- **Regenerate one track** appears when the last scan already knew the MP3
  names. Repair / Force still work without that submenu.
- Unfinished Export/Merge rows still scan as before.
- **Active only** hides idle Long completed / Merge+Completed rows. YouTube
  and Error stay visible. Idle long-complete rows show stage **Completed**.
- Unfinished run folders reuse the last directory listing while mtime is
  unchanged (one list/stat per poll cycle, not three).

## Technical impact

- `row_skip_disk_scan()` / `row_is_idle_progress_row()` in `video_runtime_inspection.py`.
- `build_video_run_inspection_map` skips listings for idle rows and caches
  unfinished inspections by directory mtime.
- Overlay skips `count_channel_mp3_files` / asset resolve for those rows.
- Context menu uses `count_missing_role_mp3s_from_meta` and cached `mp3_paths`.
- Active only uses idle detection; presentation promotes idle rows to Completed.

## Files touched

- `camxora_python/shared/lib/video_runtime_inspection.py`
- `camxora_python/shared/lib/progress_local_overlay.py`
- `camxora_python/shared/lib/missing_mp3.py`
- `camxora_python/shared/workers/data_workers.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/features/progress/widgets/operational_rows_card.py`
- `camxora_python/tests/test_video_runtime_inspection.py`
- `camxora_python/tests/test_progress_local_overlay.py`
- `camxora_python/tests/test_missing_mp3.py`
- `CHANGELOG.md`

## Migration / deploy

Desktop-only. Restart `python main.py production` (or the next installer).
No API / sandbox / production server deploy.

## Tests

- `pytest camxora_python/tests/test_video_runtime_inspection.py camxora_python/tests/test_progress_local_overlay.py camxora_python/tests/test_missing_mp3.py camxora_python/tests/test_desktop_video_automation.py -q`
