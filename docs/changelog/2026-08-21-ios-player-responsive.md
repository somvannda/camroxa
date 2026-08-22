# iOS player responsive playback

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-player-responsive`  
**Surface:** `music_web`

## Problem

On iOS Safari and iOS Chrome (WebKit), packaged playback waited for every encrypted chunk, concatenated the full MP3, then decoded before any sound. First audio could take 30–90 seconds. During that wait the user gesture expired, so a second tap was sometimes required. Track duration grew as buffers arrived. Lock screen and Dynamic Island showed no artwork because Web Audio cleared the in-DOM `<audio>` and there was no Media Session API.

## Fix

- **Progressive Web Audio:** decode chunk 0 with a persistent mpg123 decoder, start PCM immediately, fetch remaining chunks with concurrency 3, schedule gapless `AudioBufferSourceNode`s.
- **Pin duration:** catalog `duration_seconds` is set at play start and never overwritten by `graph.duration` or MSE `audio.duration`.
- **Gesture + Now Playing element:** looping silent WAV (`data:audio/wav`, not mpeg) on the in-DOM player during Web Audio playback; detached hold released after first PCM.
- **Media Session:** metadata, artwork preload, position state, and play/pause/next/previous/seek handlers; refresh on visibility.
- **Faster session start:** `createLicenseSession` starts immediately after unlock; `getPlayUrl` metadata (cover/duration) applies in parallel and does not block first audio.
- **RAM replay:** same track in the same tab replays from in-memory PCM (`webaudio_ram` trace).
- UI `play_ok` / playing state fires after chunk 0, not after the whole file. Media Session position updates are throttled to 1s so iOS does not drop artwork.

### Follow-up (lock screen / Dynamic Island)

- Removed aggressive 250ms / 2s re-sync that was fighting Web Audio on iOS.
- Silent hold is now a same-origin static WAV (`/camxora-silent-hold.wav`), not `data:` or `blob:`.
- Media Session updates once per second while playing; hold element is re-started only on visibility change.

Chrome desktop/Android keep MSE. No blob/data MP3 play src. MP3 bytes wiped after each decode.

## Files

- `music_web/src/lib/mp3-software-decode.ts` — `StreamingMp3Decoder`
- `music_web/src/lib/mpeg-playback.ts` — progressive `ProtectedAudioGraph`, `assignPlayerSilentHold`
- `music_web/src/lib/media-session.ts` — new
- `music_web/src/components/player-provider.tsx` — progressive play, duration pin, media session

## Sandbox hotfix

```bash
python scripts/deploy/hotfix_sandbox_ios_player_responsive.py
```
