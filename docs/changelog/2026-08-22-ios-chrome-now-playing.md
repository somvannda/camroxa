# iOS Chrome lock screen sync (2026-08-22)

## Problem
Safari iOS HLS path works on first play. iOS Chrome (CriOS) still uses Web Audio + silent hold; lock screen showed wrong scrubber position (elapsed time vs knob at 0) and weak Now Playing sync.

## Fix (CriOS only — Safari/HLS untouched)
- `isIosChrome()` gates all changes; HLS / native `<video>` paths unchanged.
- Silent hold loops on CriOS so the hold element never ends mid-track.
- `syncIosChromeHoldPosition()` mirrors Web Audio `currentTime` onto the hold element (CriOS scrubber reads element time).
- Faster Media Session tick (250ms) + lock-screen keepalive + visibility burst sync when Web Audio is active.
- Web Audio `onStarted` uses full `syncNowPlayingFromRefs('webaudio_started')` with metadata refresh.

## Deploy
```bash
python scripts/deploy/hotfix_sandbox_ios_hls_now_playing.py
```
