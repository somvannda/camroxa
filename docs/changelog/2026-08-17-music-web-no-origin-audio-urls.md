# Music web: hide origin audio URLs in catalog JSON

**Date:** 2026-08-17  
**Branch:** `fix/music-web-generate-assist`

## Summary

Catalog list/home/album/search/likes JSON still included `storage_key` and `suno_audio_id`. With a CDN base those are durable music URLs (`cdn1.suno.ai/{id}.mp3` or B2). Playback was already proxied; the metadata leak was not.

## Product impact

Home, Explore, albums, search, library likes, Create, and playlists only expose Camxora play/stream paths. The browser cannot copy a Suno or Backblaze audio URL from API JSON. Listening still goes through the Range proxy. Login is still required; play stays free.

## Technical impact

- Public track/album decoration keeps a whitelist and drops `storage_key`, `suno_audio_id`, `suno_image_url`, and other storage keys.
- Artist album lists use the same album decorator (they previously returned raw `cover_storage_key`).
- Album cover fallback is copied onto tracks **before** the album row is stripped.
- Player `isTrustedPlayUrl` only accepts:
  - `/api/v1/web-music/play/{token}`
  - `/api/v1/web-music/generations/{id}/stream?variant=ok|alt`
  - `/api/v1/public/streaming/tracks/{id}/stream`
- Create/playlist mint helpers refuse to return a non-proxy URL.

## Files touched

- `platform_api/services/streaming_catalog_service.py`
- `platform_api/services/audio_origin_proxy.py`
- `platform_api/services/web_music_service.py`
- `platform_api/migrations/runner.py`
- `platform_api/migrations/versions/103_merge_credit_refund_heads.py`
- `platform_api/tests/test_streaming_catalog_playback.py`
- `platform_api/tests/test_audio_origin_proxy.py`
- `platform_api/tests/test_migrations_runner.py`
- `music_web/src/lib/streaming-api.ts`

## Migration/deploy

Sync sandbox `platform_api` and rebuild `music_web`. No new database migration. Production only on explicit request.

Startup Alembic hang: this branch uses the hang-safe migration runner (skip leftover sibling heads, 180s timeout) and linear `103_merge_credit_refund_heads`. Broken merge stubs that referenced missing `084_provider_balance_events` were removed so a full API sync cannot hang sandbox again.

Cover images can still use signed URLs. Audio files do not.

## Tests

- Catalog decorate/album/artist responses omit `storage_key` and `suno_audio_id`.
- `is_camxora_audio_proxy_url` accepts the three proxy paths and rejects Suno/B2 URLs.

## Follow-ups

A logged-in listener can still save bytes from our proxy URL. There is no DRM. Goal is no shareable origin link. Cover art signed URLs remain visible in image requests.
