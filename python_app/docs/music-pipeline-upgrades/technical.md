# Music Pipeline Upgrades (Technical)

## Existing Architecture (Code References)

### Bulk Song Generation
- Orchestrator: [MusicController.generate_music_batch](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py#L224-L433)
- UI trigger: [_on_music_generate_clicked](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L3286-L3349)
- Events:
  - Generated song event handled in [_on_music_event](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L3146-L3168)
  - Auto submit to Suno occurs here when `autoGSuno` is enabled: [_on_music_event](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L3161-L3163)

### History Rendering
- DB query for history rows: [list_songs_for_history](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/music_db.py#L365-L444)
- UI render + separators: [_refresh_music_history_table](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L4482-L4773)

### MP3 → MP4 Export
- Export job wrapper: [ExportJob](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/video_export.py#L31-L124)
- Visualizer entry: [visualizer/main.py](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/main.py#L31-L245)
- Video page workers: export uses parallel workers in [_start_export_workers](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L6558-L6583)
- Auto-Video after Suno exports serially today (bottleneck): [_try_start_auto_video_channel](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1685-L1715)

### Merge
- Auto-Video merge: [_merge_mp4s](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1747-L1860)
- Current hardening:
  - preflight stable file checks
  - optional ffprobe duration checks
  - safe temp hardlink/copy renaming

## Root Causes Observed (Why “10 requested → 8/9 generated”)

### 1) Draft retry loop currently runs only once
- In [generate_music_batch](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py#L295-L355), the loop is `for attempt in range(1, 2)`, which prevents retries even though settings include `songDraftMaxAttempts`.
- When the provider call fails once, the song is marked failed and the batch proceeds, producing fewer songs than requested.

### 2) Pool selection failures immediately skip a song index
- Pool selection failure increments `failed` and continues, reducing completed count.

## Proposed Changes

### A) Batch Integrity Guarantee (per batchId)
Goal: when Boss requests `songs_per_batch=10`, each batchId should finish with 10 song rows persisted (unless hard-blocked by config, such as empty pools).

Implementation approach:
- Replace “fail and continue” behavior with “retry until song is produced or a strict cap is hit”.
- For each `song_index`:
  - Retry pool selection (repick) up to `poolPickMaxAttempts` (new setting, default 5).
  - Retry provider generation up to `songDraftMaxAttempts` (existing setting).
  - If still failing, continue attempting additional picks until the batch reaches the requested count or a batch-level cap is reached (e.g., `batchMaxExtraAttempts`, default 2× songs_per_batch).
- After batch loop, verify actual DB count for that `batch_id`:
  - If short, attempt to backfill until count reaches target or cap reached.
- Album consistency within the batch:
  - Lock `album` once per `batch_id` (use the first successful album) and force all subsequent songs to use the same album while still generating unique titles.

Code targets:
- Update [MusicController.generate_music_batch](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py#L224-L433).
- Add small helper functions inside controller to avoid duplicating logic.

### B) Random Merge Order (Always Random)
Goal: merged output order is shuffled each time.

Implementation:
- In [_merge_mp4s](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/main.py#L1747-L1860), shuffle `valid_files` before creating the temp renamed list.
- Write `MERGE_ORDER_<timestamp>.txt` into the output folder containing:
  - original filenames (before renaming)
  - final ordering

### C) Faster MP3→MP4 Export (Workers + Speed Mode)
Goal: increase throughput for bulk export/Auto-Video.

Implementation:
- Apply worker concurrency to Auto-Video:
  - Use the existing `_export_workers` (Video page “Workers”) as the concurrency limit for Auto-Video export.
  - Start up to N `ExportJob`s concurrently and wait for completion.
- Add “speed mode” settings:
  - `videoExportSpeedMode`: `balanced|fast|very_fast`
  - Pass this mode down into `visualizer.main` via a new CLI flag (e.g., `--speedMode fast`).
  - In [visualizer/main.py](file:///d:/Development/Projects/Electron/MusicGenerator/visualizer/main.py#L190-L226), map `speedMode` to:
    - NVENC preset (`p1/p3/p5`) and CQ (`23/21/19`)
    - x264 preset (`ultrafast/superfast/veryfast`) and CRF (`24/22/20`)

### D) Split AI Providers + Suno Lyrics Integration
Goal: separate concerns and allow Suno lyrics provider.

Implementation approach:
- New settings keys:
  - `titleAlbumProvider`: `deepseek|slai`
  - `lyricsProvider`: `deepseek|slai|suno`
  - `sunoApiBaseUrl` (default `https://api.sunoapi.org`) and `sunoApiKey` (reuse if compatible, otherwise add `sunoApiOrgKey`)
- Refactor draft generation into two steps:
  1) Title+Album generation:
     - Use pools as context/inspiration (sample items) + avoid lists.
     - Provider generates a unique title+album JSON.
  2) Lyrics generation:
     - If `lyricsProvider=suno`, call `POST /suno-api/generate-lyrics` per docs.
     - Else use existing LLM-based lyric generation path in [music_generation.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/music_generation.py).
- Ensure saved song record still stores:
  - `lyricsRaw` and `lyricsPolished`

Code targets:
- New Suno lyrics client module under `python_app/services/` (e.g., `suno_lyrics.py`).
- Update [music_controller.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py) generation path.
- Update Settings UI in [music_view.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/views/music_view.py) to expose the new split provider controls.

## Risks / Mitigations
- Provider latency: add timeouts and backoff; avoid infinite loops via strict caps.
- Pool depletion: fail fast with clear message; optionally add “Generate pool items” tool later.
- Export overload: clamp worker count; add warning if user sets workers too high.
