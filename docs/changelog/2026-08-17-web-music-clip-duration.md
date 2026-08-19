# Show clip duration before Ready on Create

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

Create workspace rows now show each clip’s length before the Ready/Waiting label (for example `3:45 · Ready`). New generations store Suno durations on `suno_tasks`; older Ready clips fall back to audio metadata in the browser.

## Product impact

- Workspace list and the selected-track subtitle show `m:ss` before Ready.
- Existing Ready tracks still show a duration even if the database row has none yet.

## Technical impact

- Migration `104_suno_task_durations` adds `suno_tasks.duration_ok` / `duration_alt`.
- Web-music list/get payloads include `clips[].duration_seconds`.
- Successful Suno poll writes those durations.
- Create UI probes `audio_url` metadata when the API value is missing.

## Files touched

- `platform_api/migrations/versions/104_suno_task_durations.py`
- `platform_api/services/web_music_service.py`
- `music_web/src/lib/web-music-api.ts`
- `music_web/src/components/create-page-client.tsx`

## Migration/deploy

File-scoped sandbox hotfix: upload the files above, `alembic upgrade head`, restart API, rebuild music web. Production stays untouched until asked.

## Tests

- Open Create and confirm Ready rows show a duration before Ready.
- Open a generating row: no duration until Ready (or metadata loads).
- Open track detail: subtitle matches the list format.

## Follow-ups

- Optional backfill of stored durations for older success rows (Suno poll or `scripts/deploy/backfill_web_music_durations.py` if present).
