# iOS native HTML playback revamp

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-player-responsive`  
**Surfaces:** `platform_api`, `music_web`

## Problem

Progressive Web Audio + silent WAV hold could not reliably drive iOS lock screen / Dynamic Island. First lock showed Play instead of Pause; after manual lock-screen pause/play, duration scrubber drifted. Sandbox traces confirmed audio playback (`play_ok path=webaudio`) — the failure was Now Playing integration, not decode.

## Revamp

**iOS / iPadOS / iOS Chrome:** packaged tracks now play through native `<audio>` using a new session-bound server stream:

- `GET /api/v1/web-music/licenses/play/{token}` — server decrypts CXA1 once (90s in-process cache), serves clamped 256 KiB range windows as `audio/mpeg` (same threat model as legacy proxy).
- Session JSON includes `play_url`.
- Chrome desktop/Android keep MSE client decrypt. Firefox desktop keeps progressive Web Audio.

Lock screen, Dynamic Island, and duration follow the real HTML media element — no silent hold hack on iOS Safari.

**iOS Chrome (CriOS):** stays on progressive Web Audio (`path=webaudio`) — Chrome iOS rejects `audio.play()` after the license session async work (`NotAllowedError`). Safari uses native HTML; Chrome uses the path that already worked for in-app playback.

## Files

- `platform_api/services/decrypted_play_cache.py` — new
- `platform_api/services/content_license_service.py` — `load_decrypted_playback_mp3`, `play_url`
- `platform_api/routers/web_music_licenses.py` — `/play/{token}`
- `platform_api/services/audio_origin_proxy.py` — trust regex
- `music_web/src/lib/mpeg-playback.ts` — `shouldUseNativeHtmlPlayback()`
- `music_web/src/components/player-provider.tsx` — `path=html_native`
- `music_web/src/lib/streaming-api.ts`, `content-license.ts` — trusted URL + type

## Sandbox hotfix

```bash
python scripts/deploy/hotfix_sandbox_ios_native_playback.py
```
