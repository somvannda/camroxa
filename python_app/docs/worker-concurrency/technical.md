# Worker Concurrency (Python App) — technical

## Existing Architecture (Codebase-aware)

### Settings store
- App settings are stored in `music_data["settings"]` and persisted via:
  - `_apply_settings_patch_to_database()` → `db_patch_settings()` in [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L676-L684)

### Current concurrency points
- Video export (subprocess pool) is already implemented:
  - `videoExportWorkers` limits concurrent `ExportJob` subprocesses.
  - Worker limit clamp 1..10 in [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L8963-L8973)
- Export merge currently runs as a single background thread:
  - `_start_auto_merge_export()` spawns one merge thread in [main_window.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/app/main_window.py#L9171-L9433)
- Image jobs are stored in Postgres table `image_jobs` and processed with a bounded worker pool:
  - Atomic claim in [image_db.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/database/image_db.py)
  - Worker pool in [image_generation.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/services/image_generation.py)
- Music generation runs in a single UI “start thread”, but executes batch units concurrently (bounded):
  - Bounded batch worker pool in [music_controller.py](file:///d:/Development/Projects/Electron/MusicGenerator/python_app/controllers/music_controller.py)

## New Settings Keys
- `perfMusicWorkers` (int)
- `perfImageWorkers` (int)
- `videoExportWorkers` (int, already exists; reused)
- `perfMergeWorkers` (int)
- `perfYouTubeWorkers` (int)

All keys stored via the existing settings store (no DB migration required).

## Settings UI Integration (Settings → Performance)
- Add a new `Performance` tab to `music_settings_tabs` in `views/music_view.py`.
- Add QSpinBox controls with min/max clamps matching design.md.
- On change: call the existing settings patch pipeline to persist immediately.
- On load: in `_apply_settings_to_controls()` (or equivalent), set spinbox values from settings.

## Images: Atomic Claim + Worker Pool

### Problem
Current flow is not safe for parallelism:
- Worker reads pending rows, then separately updates to RUNNING.
- With multiple workers, two threads can pick the same job.

### Solution
Implement a single SQL “claim” statement in `database/image_db.py`:
- Use a CTE with `FOR UPDATE SKIP LOCKED` to pick rows.
- Update those rows to `RUNNING` and return the full row set in the same statement.

Example structure (Postgres):
- `WITH cte AS (SELECT id FROM image_jobs WHERE ... FOR UPDATE SKIP LOCKED LIMIT %s) UPDATE image_jobs SET status='RUNNING' ... WHERE id IN (SELECT id FROM cte) RETURNING ...`

### Worker Execution
- Update `run_pending_image_jobs()` to:
  - claim up to `perfImageWorkers` jobs at a time
  - process with a bounded thread pool (I/O bound)
  - always mark READY/FAILED with existing functions

## Export Merge: Queue + Concurrency Cap
- Introduce an in-memory merge queue and merge-worker runner in `main.py`:
  - Enqueue merge tasks from:
    - Video page auto-merge
    - Progress page “Restart Merge Only”
  - Keep at most `perfMergeWorkers` concurrent merge tasks
  - Preserve existing cancel behavior by tracking per-task subprocess handles

## YouTube Upload: Atomic Claim + Worker Pool

### Problem
Current YouTube upload loop is effectively single-worker and not safe for parallel claiming:
- `db_pick_pending_youtube_upload_jobs()` selects PENDING rows without locking.
- `db_mark_youtube_upload_job_running()` happens later, so multiple workers could pick the same job.

### Solution
Implement a single SQL “claim” statement in `database/youtube_db.py`:
- Use a CTE with `FOR UPDATE SKIP LOCKED`.
- Update claimed rows to `RUNNING` and return them in the same statement.

### Worker Execution
- Replace `_youtube_upload_tick()` (single thread) with:
  - a bounded thread pool limited by `perfYouTubeWorkers`
  - each worker performs one job end-to-end, then marks READY/FAILED

## Music Generation: Bounded Batch Parallelism

### Constraint
Inside a single batch, multiple songs share a forced album and retry budget, so per-batch work stays sequential.

### Approach
- Create a batch task list for each `(ymd, okId/altId pair_index)` combination.
- Run those tasks in a thread pool limited by `perfMusicWorkers`.
- Each task emits progress events to the existing event bus.

### Risk Controls
- Keep default `perfMusicWorkers=1` (Balanced).
- If multiple workers are used, uniqueness constraints are “best effort” (race between workers) but still improved by DB history checks.

## Testing Strategy
- Unit-ish:
  - validate `claim_pending_image_jobs()` returns unique jobs when run concurrently.
- Manual:
  - enqueue many images and verify no duplicates + stable throughput.
  - run export+merge with higher concurrency and verify no freezes.
  - enqueue multiple YouTube uploads and verify:
    - no duplicates
    - max concurrency respected
    - stable retries
  - run music generation with `perfMusicWorkers>1` and confirm multiple batches progress simultaneously.
