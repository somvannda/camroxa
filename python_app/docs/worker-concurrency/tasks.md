# Worker Concurrency (Python App) — tasks

## Goal
Increase throughput by adding configurable per-stage worker limits (Music / Images / Export / Merge) while preventing duplicate job pickup and avoiding PC overload.

## Status
- in progress

## Phase 1 — Inspect & Align (completed)
- [x] Inspect current worker/concurrency implementations:
  - Video export: `videoExportWorkers` subprocess concurrency.
  - Export merge: single-threaded merge.
  - Image jobs: Postgres queue, sequential processing.
  - Music generation: single worker thread, sequential per batch.

## Phase 2 — Design & Settings (pending)
- [x] Add Settings → Performance tab UI (central place) with worker controls:
  - Music Workers (1–5)
  - Image Workers (1–8)
  - Export Workers (1–10, reuse existing `videoExportWorkers`)
  - Merge Workers (1–2)
  - YouTube Upload Workers (1–5)
- [x] Persist settings via existing settings store (`db_patch_settings`).
- [x] Sync existing Video page “Workers” spinbox with the shared `videoExportWorkers` setting.

## Phase 3 — Images: Safe Parallel Workers (pending)
- [x] Add DB-atomic job claiming API to prevent duplicate pickup:
  - Implement `claim_pending_image_jobs(...)` in `database/image_db.py` using a single SQL statement.
- [x] Update image worker loop to run jobs concurrently with a bounded worker pool:
  - Use the new image worker setting as concurrency limit.
  - Preserve per-job status updates (RUNNING/READY/FAILED/CANCELLED).
- [x] Add basic backpressure:
  - If too many jobs are already RUNNING, do not claim more.

## Phase 4 — Export & Merge Concurrency (pending)
- [x] Keep Export Workers as-is (already exists) and ensure Settings → Performance can control it.
- [x] Add Merge queue with concurrency cap:
  - Progress page “Restart Merge Only” enqueues merge tasks when all merge workers are busy.
  - Merge worker limit applies across export-merge (batch export) + progress merge-only tasks.
  - Export auto-merge remains single-flight; it occupies one merge worker slot while running.

## Phase 5 — YouTube Upload Concurrency (pending)
- [x] Add DB-atomic job claiming for YouTube uploads to prevent duplicate pickup:
  - Implement `claim_pending_youtube_upload_jobs(...)` in `database/youtube_db.py`.
- [x] Replace the current single-worker YouTube tick with a bounded worker pool:
  - Run up to `perfYouTubeWorkers` concurrent uploads.
  - Keep per-profile OAuth/token refresh isolated per worker.
  - Keep safe retry/backoff and clear footer status messages.

## Phase 6 — Music Generation Concurrency (pending)
- [x] Add Music batch worker pool:
  - Run multiple batch units concurrently (date + OK/ALT pair index), up to `musicWorkers`.
  - Keep per-batch inner song generation sequential to preserve “forced album per batch” behavior.
- [x] Guard shared host access:
  - Ensure cancellation flag works across workers.
  - Ensure UI events and DB writes remain safe.
- [x] Add safety defaults (Balanced):
  - Music=1, Images=4, Export=2, Merge=1

## Phase 7 — Verification (pending)
- [needs review] Smoke-test: start app, open Settings → Performance, change limits, persist and reload.
- [needs review] Image: enqueue many jobs; verify no duplicates and parallel progress.
- [needs review] Export: run batch export with workers=2; verify stability.
- [needs review] Merge: enqueue multiple merges; verify capped concurrency and queue behavior.
- [needs review] YouTube: enqueue multiple uploads and verify capped concurrency and no duplicate claims.
- [needs review] Music: generate multiple batches; verify throughput increases and no crashes.

## Phase 8 — Documentation (pending)
- [x] Update `python_app/DEVELOPMENT_LOG.md` with worker system changes and migration notes.
