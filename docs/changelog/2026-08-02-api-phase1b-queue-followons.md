# Phase 1b — queue follow-ons (images, YouTube, per-song, metrics)

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/api-phase1b-queue-followons`

## Scope

Complete the four Phase 1 follow-ons (not “Phase 2” VPS upgrade):

1. **Image drains off the API** — replace `asyncio.create_task(run_image_jobs_until_empty…)` with durable `run_image_jobs` rows (deduped via `enqueue_if_absent`). Sites: `/image-jobs/run`, `/image-jobs/retry`, Suno SUCCESS callback, batch image backfill/reconcile.
2. **YouTube uploads off HTTP BackgroundTasks** — `POST /youtube/uploads/run` enqueues `run_youtube_uploads` for `camxora-worker`.
3. **Per-song draft / suno_submit** — `execute_batch` fans out one `draft` job per pending song; successful drafts with `auto_gsuno` enqueue `suno_submit`. Manual retries still use `retry_song_draft` / `retry_song_suno` (inline Suno on draft retry). Polish→Suno also enqueues `retry_song_suno`.
4. **Basic metrics/alerts** — `GET /api/v1/admin/job-queue/metrics` returns queue depth by status/type, busy workers, oldest claimable age, in-process `/progress` p50/p95 (per uvicorn worker), and simple threshold alerts.

## Worker job types

`execute_batch`, `draft`, `suno_submit`, `retry_song_draft`, `retry_song_suno`, `run_image_jobs`, `run_youtube_uploads`

## Ops notes

- Restart **both** `camxora-api` and `camxora-worker` after deploy.
- `/progress` latency samples are **per uvicorn process**; with `--workers 4` each process holds its own ring buffer.
- Album consistency for multi-worker draft fan-out still prefers earlier `batch_index` via priority; sibling album/title reuse remains as in `retry_song_draft`.
