# Progress Page (Technical)

## Existing Architecture (Code References)
- Primary navigation shell: [core_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/core_view.py)
- Main stacked pages: [main.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L5472-L5488)
- Music batch generation:
  - Generator: [music_controller.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py)
  - UI event bus: [main.py:_on_music_event](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L3202-L3333)
- Image job persistence and status:
  - DB: [image_db.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/image_db.py)
  - Worker: [image_generation.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/image_generation.py)
- Auto-Video export+merge:
  - Scheduler + exporter + merge: [main.py:_auto_video_tick/_try_start_auto_video_channel/_merge_mp4s](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1609-L1999)

## Data Sources
- Batch list:
  - Use `list_batches_for_history()` for recent batches (DB-backed).
- Music progress:
  - Song count per batchId from DB (`songs` table).
  - Expected song count for active batches from runtime meta (`_auto_video_batches[batchId].songsPerBatch`).
- Image progress:
  - Read `image_jobs` rows for (batchId, profileId, kind in {background, thumbnail}).
- Converter/Merge progress:
  - Derive output directories using `get_batch_run_dirs_by_batch_id()` with fallback to `get_latest_suno_output_dirs_by_batch_id()`.
  - MP3 count: `*.mp3`
  - MP4 count: `*.mp4` excluding `MERGED_*.mp4`
  - Merge existence: `MERGED_*.mp4`

## Derived Stage Logic (Per Role)
Stage order: Music → Image → Converter → Merge → Done
- If songs_saved < expected: stage=Music
- Else if BG/TH not ready: stage=Image
- Else if MP4 count < expected: stage=Converter
- Else if no MERGED file: stage=Merge
- Else stage=Done

## Refresh Strategy
- Manual refresh button triggers a full recompute.
- Optional auto-refresh timer (e.g., every 2s–5s) while the Progress page is visible.
- Refresh must be safe when DB is not configured (show a friendly message instead of exceptions).
- Date filters map to `list_batches_for_history(from_ymd, to_ymd)` to limit DB work to only the requested time window.

## Context Actions (Right Click)
- Per-row context menu provides operational restart controls:
  - Restart Image (BG/TH): resets the related `image_jobs` rows back to PENDING for the selected batch+channel.
  - Restart Converter: re-runs Auto-Video export for missing MP4 outputs (optionally force rebuild by deleting MP4s).
  - Restart Merge Only: re-merges existing MP4s without re-exporting.

## Implementation Plan
- Add new `ProgressViewMixin` to build the UI.
- Add `progress_view.py` to `python_app/views/`.
- Add a lightweight DB helper for fetching image job statuses for a batch+profiles (to avoid N× per-row queries).
