# Web music: cap stream Range windows

**Date:** 2026-08-19  
**Branch:** `fix/web-music-stream-range-cap`

## Summary

Create/catalog play URLs still handed out a full MP3 when the client sent `Range: bytes=0-` (Chrome, Postman, and curl all do this). A logged-in user could save the whole track in one request. Stream endpoints now return at most 256 KiB per request as HTTP 206. Official `/download` is unchanged for entitled users.

## Product impact

- In-app play still works: the player follows 206 windows and requests the next 256 KiB.
- A copied `/stream/ok` or `/stream/alt` curl/Postman call no longer returns the full file.
- A GET with no Range is treated like a download for rate-limiting, and still only receives the first 256 KiB.
- Paid/entitled MP3 and WAV downloads are not capped.

## Technical impact

- `clamp_stream_range` rewrites missing/`bytes=0-` (and any open-ended or oversized Range) to a 256 KiB window.
- `proxy_origin_audio` always sends that bounded Range upstream **and** truncates the body if origin ignores Range or returns 200.
- The in-memory B2/Suno fallback (`_proxy_row` when there is no origin URL) slices bytes the same way instead of dumping the whole MP3.
- Catalog `/public/streaming/tracks/{id}/stream` uses the same proxy, so Explore/Home get the cap too.

## Files touched

- `platform_api/services/audio_origin_proxy.py`
- `platform_api/services/web_music_service.py`
- `platform_api/routers/web_music.py`
- `platform_api/routers/streaming_public.py`
- `platform_api/tests/test_audio_origin_proxy.py`

## Migration/deploy

No database migration. File-scoped API hotfix, restart `camxora-api`. No `music_web` rebuild. Production only on explicit request.

## Tests

- `bytes=0-` and missing Range clamp to `bytes=0-262143`.
- Origin 200 with a 400 KiB body is truncated to 256 KiB 206.
- In-memory fallback slices to 256 KiB.
- Small bounded ranges such as `bytes=0-11` still pass through.

## Follow-ups

Production API when asked. Determined clients can still stitch Range windows; this stops the one-shot save Sokha reproduced.
