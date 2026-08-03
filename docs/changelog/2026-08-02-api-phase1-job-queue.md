# Phase 1 — durable job_queue + platform_worker

**Date:** 2026-08-02  
**Status:** implemented (execute_batch + draft/Suno retries)  
**Branch:** `fix/api-phase1-job-queue`

## Problem

Batch generation ran inside uvicorn via FastAPI `BackgroundTasks`, so long draft/Suno work competed with `/progress` / `/profiles` polls on the same worker processes.

## Fix (incremental)

1. Migration `080_job_queue` — durable Postgres queue with `FOR UPDATE SKIP LOCKED` claim index
2. `JobQueueRepository` — enqueue / claim / done / retry-or-fail / stale recovery
3. `POST /batches`, retry-draft, retry-suno → **enqueue** (no BackgroundTasks)
4. `python -m platform_api.worker` — systemd `camxora-worker` drains:
   - `execute_batch`
   - `retry_song_draft`
   - `retry_song_suno`

## Follow-ons (Phase 1b)

See `docs/changelog/2026-08-02-api-phase1b-queue-followons.md`:

- Image job drains → `run_image_jobs`
- YouTube uploads → `run_youtube_uploads`
- Per-song `draft` / `suno_submit` fan-out
- Admin metrics (`queue depth`, worker busy, `/progress` p95)

## Ops

Worker must be running or batches stay `queued` in `job_queue`. API restarts no longer cancel in-flight batch execution once claimed by the worker.
