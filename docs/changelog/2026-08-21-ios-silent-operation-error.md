# iOS silent play + OperationError

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-safari-playback`  
**Surfaces:** music_web

## Summary

Sandbox traces after the skip-loop fix: some plays reached `play_ok` (Web Audio, ~64s) but sounded silent. Others died with `stage=packaged OperationError The operation failed for an operation-specific reason` during chunk decrypt, with no `count=`. Switching tracks left the previous fetch/decrypt running; Safari Web Crypto then fails, and a 30s fetch lets iOS suspend AudioContext so progress moves with no sound.

## Product impact

- Switching tracks aborts the old download.
- A detached silent WAV (not the player element) plus AudioContext resume keep iOS unlocked until the song starts.
- If the context is still suspended, play asks for another tap instead of looking like it is playing with no audio.

## Files touched

- `music_web/src/lib/mpeg-playback.ts`
- `music_web/src/lib/content-license.ts`
- `music_web/src/components/player-provider.tsx`

## Migration / deploy

Sandbox `music_web` file-scoped hotfix. Production only on explicit request.
