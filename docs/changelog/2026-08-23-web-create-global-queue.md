# Global paid-first web Create queue

**Date:** 2026-08-23  
**Surfaces:** platform_api, music_web  
**Branch:** `feature/web-create-cooldown-queue`

## Summary

Web Create no longer calls Suno inside the API request. It validates, charges, inserts a pending `suno_tasks` row, and enqueues `web_music_generate` on the existing `job_queue`. Suno workers drain **paid first, then free**, one web song at a time. Desktop generate/Suno is unchanged.

## Product impact

- Create button stays disabled for **5 seconds**, then the next click enqueues another song.
- Paid users can have **20** songs waiting to hit Suno. Free users can have **2**.
- Paid jobs always start before free jobs that are still queued. Desktop studio jobs still outrank web.
- The workspace list shows the song immediately as Queued/Waiting. Audio still arrives later.
- Credits are taken on enqueue and refunded if the worker cannot start the Suno job.

## Technical impact

- New job type `web_music_generate` on the Suno worker shard. Priorities: desktop `suno_submit` 18, web paid 16, web free 8.
- Redis lock `web_music:suno_submit` so multiple Suno workers send only one web song at a time.
- `/web-music/generate` rate-limit type `web_music_generate` is 40/60s so the queue cap is the real limit.
- Quota responses include `queue_limit` and `queue_used`.

## Files touched

- `platform_api/services/job_types.py`
- `platform_api/repositories/job_queue_repo.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/generation_service.py`
- `platform_api/worker.py`
- `platform_api/middleware/rate_limit.py`
- `platform_api/routers/web_music.py`
- `platform_api/tests/test_web_music_generate_queue.py`
- `music_web/src/lib/create-submit-queue.ts`
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/lib/web-music-api.ts`
- `music_web/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration/deploy

No database migration. Sandbox:

```bash
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/rebuild_music_web_sandbox.py
```

Restart Suno workers with the API sync (existing script already restarts `camxora-worker-suno@`). Production only when asked.

## Tests

- `pytest platform_api/tests/test_web_music_generate_queue.py platform_api/tests/test_job_types_worker_stages.py platform_api/tests/test_rate_limit.py -q`
- `npx tsx --test music_web/src/lib/create-submit-queue.test.ts`

## Follow-ups

- Production music web + API + Suno worker deploy after review.
