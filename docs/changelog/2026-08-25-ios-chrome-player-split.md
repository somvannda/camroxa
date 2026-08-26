# iOS Chrome player split + MediaError 4 fallback

**Date:** 2026-08-25  
**Branch:** `bugfix/ios-chrome-player-split`  
**Surfaces:** music_web (`music.sandbox.camxora.com` first)

## Summary

iOS Chrome (CriOS) was on the same HLS `<video>` lane as iOS Safari. When HLS was missing or WebKit fired `MediaError.code === 4` (`MEDIA_ERR_SRC_NOT_SUPPORTED`), the player showed the raw “media error 4” string and never fell back to Web Audio.

Each OS/browser now has its own player module. The CriOS fix lives only in `ios-chrome.ts`. Windows Chrome still uses MSE in `win-chrome.ts`.

## Product impact

- iOS Chrome: try trusted HLS, then decrypt with Web Audio + silent hold. Never set `<audio>/<video>.src` to a packaged HTML Create stream.
- iOS Chrome MediaError 4 maps to “Tap play again to start audio.”
- Desktop Chrome play path is unchanged (`path=mse player=win-chrome`).
- **win-** players are Windows only. macOS Chrome is `macos-chrome.ts` (HLS `<video>` first, then CXA1 Web Audio so songs without HLS still play; no MSE). macOS Safari is `macos-safari.ts` (HLS → license HTML → Web Audio).

## Technical impact

- `player-provider.tsx` dispatches `detectPlayer()` → `getPlayBackend(id).play()`.
- Shared MSE engine lives in `players/engines/mse.ts` and is imported only by desktop/Android Chrome-family files.
- `play_path` traces include `player=<id>` so CriOS and Windows Chrome are distinguishable.

## Files touched

- `music_web/src/lib/players/*` (detect, backends, engines)
- `music_web/src/components/player-provider.tsx` (dispatcher)
- `music_web/src/lib/players/detect.test.ts`
- `music_web/src/lib/players/ios-chrome.test.ts`
- `music_web/CHANGELOG.md`

## Migration / deploy

music_web sandbox rebuild only (`rebuild_music_web_sandbox.py`). Production music_web after sandbox play traces look right. No API / migration.

## Tests

- CriOS UA → `ios-chrome`; desktop Chrome → `win-chrome`; Safari iPhone → `ios-safari`
- iOS Chrome: HLS; HLS fail → Web Audio; no HLS → Web Audio; source does not import MSE

## Follow-ups

- Production music_web rebuild only after sandbox `play_path` shows `player=ios-chrome` vs `player=win-chrome`.
- HLS playlist/segment gaps remain an API packaging issue; this change only reroutes CriOS off a dead native src.
