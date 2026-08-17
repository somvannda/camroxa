# Music web: Create settings, duration, and faster playback

**Date:** 2026-08-17  
**Branch:** `fix/music-web-generate-assist`

## Summary

Create-page track details always showed default vocal/slider values, durations waited on audio metadata, and Play downloaded the full MP3 through the API before sound started. One Suno job also listed both clips with the same title, so Version 1 and Version 2 looked identical.

## Product impact

- Right-panel settings show the stored vocal gender and slider values (percent), or "—" / "Not set" when unset.
- Workspace rows label clips as **Version 1** / **Version 2** and show duration from Suno when stored.
- Play streams through `/web-music/play/{token}` (login required). The browser never sees Suno or Backblaze URLs. The API forwards HTTP Range so playback can start after the first chunk, then backfills B2 in the background.

## Technical impact

- Generation list/get responses include `vocal_gender`, slider weights, and clip `duration_seconds`. Clip `audio_id` is not returned to the browser.
- Migration `104_suno_task_durations` adds `suno_tasks.duration_ok` / `duration_alt`. Poll and callback persist those values.
- `/web-music/generations/{id}/stream` and `/web-music/play/{token}` proxy origin audio with Range. They do not 302 to Suno/B2.
- Player uses credentialed same-origin requests for those play URLs.

## Files touched

- `platform_api/routers/web_music.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/routers/callbacks.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/migrations/versions/104_suno_task_durations.py`
- `platform_api/tests/test_web_music_router.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `music_web/src/lib/web-music-api.ts`
- `music_web/src/components/create-page-client.tsx`
- `music_web/src/components/player-provider.tsx`
- `platform_api/services/audio_origin_proxy.py`
- `platform_api/tests/test_audio_origin_proxy.py`
- `scripts/deploy/nginx-camxora-sandbox.conf`

## Migration/deploy

1. `alembic upgrade head` is currently broken on sandbox (merge references missing `084_provider_balance_events`). Duration columns were confirmed present; revision `104_suno_task_durations` is already in `alembic_version`.
2. Sync `platform_api` and rebuild `music_web`.
3. Sandbox first. Production only on explicit request.

## Tests

- Router: generation payload includes settings; stream proxies audio and does not 302 to the origin URL.
- Callback URL parser stores clip durations.

## Follow-ups

- Existing tracks get duration on next get/refresh (Suno poll backfill), not on list alone.
- Production deploy of this playback path is separate from the Create assist nginx template change.
