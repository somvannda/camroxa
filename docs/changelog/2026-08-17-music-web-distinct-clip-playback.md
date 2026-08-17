# Music web: Create clips must play distinct audio

**Date:** 2026-08-17  
**Branch:** `fix/music-web-generate-assist`

## Summary

After Range-proxy playback shipped, Create workspace rows could keep playing the first clip’s audio when you pressed Play on another Version or another song. Metadata (title, duration, cover) was correct; the media element reused the previous buffer.

## Product impact

Each Create clip plays its own file. Switching Version 1 / Version 2 or a different song creates a fresh media element before loading the new stream.

## Technical impact

- Owner Create play URLs are `/web-music/generations/{id}/stream?variant=ok|alt` (unique per clip). Opaque play tokens remain for public playlist playback.
- Player replaces the `HTMLAudioElement` on each clip (do not reuse the previous media buffer), pauses/clears the old `src`, and cache-busts the next URL.
- Create rows no longer probe duration by creating hidden `Audio()` elements against play URLs.
- Proxy responses send `Cache-Control: private, no-store, no-cache`.

## Files touched

- `music_web/src/components/player-provider.tsx`
- `music_web/src/components/create-page-client.tsx`
- `platform_api/services/web_music_service.py`
- `platform_api/services/audio_origin_proxy.py`
- `platform_api/tests/test_web_music_play_tokens.py`

## Migration/deploy

Sync sandbox API and rebuild `music_web`. File-scoped production hotfix of the same files. No migration.

## Tests

- Owner mint URLs differ by task id and variant.

## Follow-ups

None.
