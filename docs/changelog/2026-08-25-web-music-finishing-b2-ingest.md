# Web Create Finishing never reached B2

**Date:** 2026-08-25  
**Branch:** `bugfix/web-music-finishing-b2-retry`  
**Surfaces:** platform_api (music.camxora.com Create)

## Summary

Suno can mark a web song SUCCESS (duration + origin URLs) while Create stays on **Finishing**. Ready waits for our Backblaze object. The Suno callback skipped web-music ingest on purpose, and the Create poll only scheduled B2 when *it* saw pending→success. If the callback won, ingest never started.

## Product impact

- New Create songs start B2 ingest when the Suno callback lands SUCCESS.
- While a clip is still Finishing, Create's 2.5s poll retries ingest (20s cooldown).
- Duke's `Yeah…` tracks (`iamduke1987@gmail.com`) matched this: SUCCESS, Suno URLs present, no B2 keys.

## Technical impact

- Callback SUCCESS for `source=web_music` calls `schedule_web_music_b2_backfill`.
- Desktop catalog still uses `schedule_suno_streaming_upload` when `song_id` is set.
- `get_generation` schedules ingest for SUCCESS clips that are not playable but still have origin URLs.
- Backfill schedule ignores duplicate in-flight work and cools down 20s after an attempt.
- `StreamingCatalogService.__init__` accepts `redis=` so `/streaming/library/likes` no longer 500s after API restart.

## Files touched

- `platform_api/routers/callbacks.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/tests/test_web_music_b2_ingest_retry.py`
- `platform_api/tests/test_streaming_upload_service.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

Production: restore the pre-overwrite `web_music_service.py` / `callbacks.py` /
`streaming_upload_service.py` from the fill-gaps tree that still matches
production `web_music.py` + `job_types.py`, then apply **only** the ingest
lines (callback B2 on web_music SUCCESS, `get_generation` retry, 20s
cooldown). Do not upload `main`'s v3/queue service onto production.

API restart required. Restart logs users out. No migration.

Keep `StreamingCatalogService` `redis=` (already on production).

## Tests

- Callback web_music SUCCESS schedules B2, not catalog upload.
- Desktop SUCCESS with `song_id` still uses catalog upload.
- `get_generation` retries unready SUCCESS clips and skips packaged Ready clips.
- B2 schedule skips in-flight and cooldown duplicates.

## Follow-ups

- `camxora-worker` was inactive on production during diagnose. Unrelated to this ingest skip, but queued `web_music_generate` jobs would stall if generate is worker-only.
