# Music web: Version 1/2 play URLs must differ by path

**Date:** 2026-08-18  
**Branch:** `fix/music-web-generate-assist`

## Summary

Create workspace listed Version 1 as 2:46 and Version 2 as 2:55, but the player duration was 2:54 for both. The files in storage were distinct; the browser was loading Version 2’s audio for both rows because play URLs only differed by `?variant=ok|alt`. Chrome (and some caches) can reuse one media entry for the same path.

## Product impact

Playing Version 1 and Version 2 of the same generation loads each clip’s own audio. The player timer matches the row duration.

## Technical impact

- Owner Create play URLs are `/web-music/generations/{id}/stream/ok` and `/stream/alt` (variant in the path). The old `?variant=` route still works.
- Web-music Backblaze uploads no longer fall back to the other clip’s Suno URL if one download fails.
- Trusted-URL checks accept both path and query forms.

## Files touched

- `platform_api/routers/web_music.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/audio_origin_proxy.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/services/streaming_upload_service.py`
- `music_web/src/lib/streaming-api.ts`
- `scripts/deploy/nginx-camxora-sandbox.conf`
- `scripts/deploy/nginx-camxora-production.conf`

## Migration/deploy

File-scoped API hotfix + music_web rebuild. No migration.

## Tests

- Owner mint URLs end with `/stream/ok` and `/stream/alt`.
- Stream route `/stream/alt` passes `variant=alt`.
- Web-music URL candidates can exclude the other clip.

## Follow-ups

Hard-refresh Create after deploy so the client picks up the new play URLs.
