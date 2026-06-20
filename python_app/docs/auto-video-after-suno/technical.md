## Auto-Video After Auto-Suno — Technical

### Readiness Inputs
- Batch folders come from `batch_run_dirs` via:
  - `get_batch_run_dirs_by_batch_id(db_cfg, batch_id)` (OK/ALT dirs)
- Background readiness comes from image job queue:
  - `get_ready_background_output(db_cfg, batch_id, profile_id)`
- Profile → template mapping:
  - profile field `videoTemplateId` (stored in `profiles.video_template_id`)
  - template loaded from `video_templates` via `db_get_video_template` or local fallback

### Scheduler
- Add a 30s `QTimer` in `MainWindow` that:
  - checks if `autoVideoAfterSuno` is enabled
  - iterates over recent known batchIds (captured during song generation)
  - for each batch/channel, if ready, starts export+merge
  - waits until the channel folder contains the full expected MP3 count for the batch (so we don’t export/merge partial batches)

### Export Execution (headless)
- Use `ExportJob` directly (no dependency on Video page widgets):
  - `mp3_path`
  - `template` (dict)
  - `background_path` (generated background_*.png)
  - `logo_path` (profile.logoPath if present)
  - `output_dir` (channel folder)
  - `ffmpeg_path` (from settings)

### Merge Execution (headless)
- Reuse existing merge strategy from MainWindow:
  - concat demuxer with stream copy first
  - duration verification via ffprobe
  - fallback to re-encode concat
- Output path must be inside the same channel folder.

### Interaction With Image Retry
- Auto-Video should only begin after background is READY.
- Image worker will retry transient failures every 30 seconds to maximize end-to-end success.
