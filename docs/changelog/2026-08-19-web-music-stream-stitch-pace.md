# Web music: stop Range-stitch dumps

**Date:** 2026-08-19  
**Branch:** `fix/web-music-stream-stitch-pace`

## Summary

A logged-in client could still save a full MP3 by walking the 256 KiB play windows (19 requests for a ~4.8 MB track). Play/stream now requires a browser audio request, and new Range windows are paced per user+track so a fast stitch dump 429s. Official `/download` is unchanged.

## Product impact

- In-app `<audio>` play on music.camxora.com is unchanged (Sec-Fetch-Dest: audio).
- Opening a play URL in a new tab, curl, Postman, or a Range-stitch shell script is 403.
- A patched script that spoofs browser headers and sleeps between windows can still collect bytes over time; this is not DRM.
- Paid MP3/WAV download is unaffected.

## Technical impact

- `assert_browser_audio_request`: `Sec-Fetch-Dest: audio`, or a music-web Referer when Sec-Fetch is absent (older Safari).
- Unique 256 KiB windows are capped at 10 per 15 seconds per user+task/track. Retries of the same window are free.
- Catalog `/public/streaming/tracks/{id}/stream` uses the same guard. Admin blob audio is a different route and is not gated.

## Files touched

- `platform_api/services/stream_playback_guard.py`
- `platform_api/services/audio_origin_proxy.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/streaming_catalog_service.py`
- `platform_api/routers/web_music.py`
- `platform_api/routers/streaming_public.py`
- `platform_api/wire_dependencies.py`
- `platform_api/exceptions.py`
- `platform_api/main.py`
- `platform_api/tests/test_stream_playback_guard.py`
- `platform_api/tests/test_exceptions.py`
- `scripts/deploy/hotfix_web_music_stream_stitch_pace_sandbox.py`
- `scripts/deploy/hotfix_web_music_stream_stitch_pace_production.py`

## Migration/deploy

No database migration. File-scoped API hotfix, restart `camxora-api`. No `music_web` rebuild. Sandbox and production file-scoped hotfixes were applied.

## Tests

- curl-like headers are denied; `Sec-Fetch-Dest: audio` and music Referer are allowed.
- Same window retries do not consume the unique-window budget.
- An 11th new window inside 15 seconds raises 429 with Retry-After.
- RateLimitedError responses include Retry-After.

## Follow-ups

Real DRM (encrypted HLS/MSE) would be required to stop a patched browser/Playwright client.
