# Player skip-loop from silent WAV unlock

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-safari-playback`  
**Surfaces:** music_web

## Summary

Sandbox `playback_events` after Chrome + Safari play showed 13 `play_start` / `play_path=webaudio` and **zero** `play_chunks`, `play_decode`, `play_ok`, or `play_error`. Tracks flipped Version 1 ↔ Version 2 every 1–2 seconds.

The last abort hotfix played a looping silent WAV on the **shared** player `<audio>`. That element’s `ended` handler treats a short clip as “song finished” and starts the next queue item, which cancels the in-flight decrypt. Both WebKit Chrome and Safari hit the same path (`mse=0` on iOS).

## Product impact

- Play stays on the tapped track while chunks load.
- Play/pause is not driven by an empty or `data:` unlock src.
- Protection unchanged: no `blob:`/`data:` `audio/mpeg` play src.

## Files touched

- `music_web/src/lib/mpeg-playback.ts`
- `music_web/src/components/player-provider.tsx`

## Migration / deploy

Sandbox `music_web` file-scoped hotfix only. Production only on explicit request.
