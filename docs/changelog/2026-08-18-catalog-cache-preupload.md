# Music web: catalog cache + Create pre-upload + bounded play ranges

**Date:** 2026-08-18  
**Branch:** `fix/music-web-generate-assist`

## Summary

Catalog playback should start from Backblaze, never Suno. Create clips should upload to Backblaze when generation succeeds, not on first Play. Stream requests cannot one-shot a full MP3. Workspace Create playback stays on its own uncached proxy path so the shared player does not use catalog cache rules.

## Product impact

- Home / Explore / album tracks start from B2. Listener 2 on the same origin hits nginx cache after login, not a second B2/Suno fetch.
- Create / My Workspace still plays `/web-music/generations/{id}/stream` (private, not catalog-cached).
- A download-style GET with no Range is throttled like a download and only receives the first 256 KiB from the stream endpoint. Full files stay on paid `/download`.

## Technical impact

- Web-music success (Suno callback or poll) schedules `schedule_web_music_b2_backfill` immediately.
- Catalog `proxy_track_audio` remains B2-only.
- `clamp_stream_range` rewrites missing/`bytes=0-` play requests to a 256 KiB 206.
- nginx: catalog stream uses `auth_request` + `proxy_cache` keyed by track id + Range. Create/play-token locations stay unbuffered with no cache.
- Cloudflare is not used as a public audio CDN (track UUIDs are public in catalog JSON; a CF cache hit would skip login).
- Player cache-busts Create URLs only.

## Files touched

- `platform_api/services/audio_origin_proxy.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/streaming_catalog_service.py`
- `platform_api/routers/callbacks.py`
- `platform_api/routers/streaming_public.py`
- `platform_api/routers/web_music.py`
- `music_web/src/components/player-provider.tsx`
- `scripts/deploy/nginx-camxora-sandbox.conf`
- `scripts/deploy/nginx-camxora-production.conf`
- `scripts/deploy/apply_nginx.py`

## Migration/deploy

No database migration. Sync API files, apply nginx (creates `/var/cache/nginx/camxora_catalog_audio`), rebuild music_web.

## Tests

- Range clamp bounds full-file requests.
- Catalog play-auth returns 204.
- Catalog stream still hides origin URLs.

## Follow-ups

Production nginx + API when asked. Cloudflare Worker only if we later want global PoPs without skipping login.
