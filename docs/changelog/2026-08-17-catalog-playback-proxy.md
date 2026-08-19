# Music web: proxy catalog playback

**Date:** 2026-08-17  
**Branch:** `fix/music-web-generate-assist`

## Summary

Catalog/Explore play returned a signed Backblaze URL in `GET /public/streaming/tracks/{id}/play-url`. Anyone logged in could copy that URL and save the file without using a Camxora play session.

## Product impact

Album, Home, Explore, Search, and Library play now stream through `/api/v1/public/streaming/tracks/{id}/stream`. The browser only sees a Camxora URL. Login is still required; listening stays free.

## Technical impact

- `play-url` returns the proxy path, not a signed B2/CDN URL. Play count increments on the first Range request to `/stream`, not on metadata fetch.
- Player ignores leftover `http(s)` play URLs and uses the catalog stream path for UUID tracks.
- Create/playlist play tokens (`/web-music/play/{token}`) are unchanged.
- Sandbox nginx Range proxy locations include the catalog stream path.

## Files touched

- `platform_api/services/streaming_catalog_service.py`
- `platform_api/routers/streaming_public.py`
- `platform_api/tests/test_streaming_catalog_playback.py`
- `music_web/src/lib/streaming-api.ts`
- `music_web/src/components/player-provider.tsx`
- `scripts/deploy/nginx-camxora-sandbox.conf`

## Migration/deploy

Sync `platform_api`, apply sandbox nginx, rebuild `music_web`. Production only on explicit request.

Cover images still use signed URLs. Audio files do not.

## Tests

- `get_play_url` returns `/api/v1/public/streaming/tracks/{id}/stream` and does not mint a client origin URL.
- Stream endpoint proxies bytes with no `Location` header.
- Play count increments on `bytes=0-` only.

## Follow-ups

Cover art signed URLs are still visible if someone inspects image requests.
