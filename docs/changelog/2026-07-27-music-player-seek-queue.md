# Music portal player seek, queue, album Play/Shuffle

**Date:** 2026-07-27  
**Status:** implemented (sandbox deploy)

## Summary

Closed the largest Spotify gap on `music_web`: the bottom player now supports seek, volume, previous/next within a queue, and auto-advances when a track ends. Album pages get Play-all and Shuffle under the hero; clicking a track in an album loads the full album as the queue.

## Product impact

**Before:** Player was play/pause only; album pages had no Play-all; single-track play with no album queue.  
**After:** Seek scrubber + clock, volume/mute, prev/next (prev restarts after 3s), album Play/Shuffle, track rows enqueue the album and advance automatically.

## Technical impact

- `PlayerProvider` owns queue + index, audio time/duration listeners, volume (localStorage), `playQueue` / `playShuffled`.
- `PlayerBar` three-column Spotify-like controls.
- `AlbumPlaybackControls` client CTA on album hero.
- `TrackRow` accepts optional `queue` (album list passes it).

## Files touched

- `music_web/src/components/player-provider.tsx`
- `music_web/src/components/player-bar.tsx`
- `music_web/src/components/album-playback-controls.tsx`
- `music_web/src/components/album-track-list.tsx`
- `music_web/src/components/track-row.tsx`
- `music_web/src/app/albums/[id]/page.tsx`
- `music_web/src/app/layout.tsx`
- `docs/MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`
- `music_web/CHANGELOG.md`

## Migration / deploy

- No API/DB changes.
- Sandbox: `python scripts/deploy/rebuild_music_web_sandbox.py`

## Tests

- `npx tsc --noEmit` in `music_web` — clean.
- Sandbox rebuild succeeded; `camxora-music` active; home `200`.
- Deployed chunks include album Play/Shuffle and player seek/volume symbols.

## Follow-ups

- Shuffle/repeat toggles on the player bar; queue panel; contextual Now Playing rail; synced lyrics (Phase 4 remainder).
- Numbered tracklist cleanup (P1 from Spotify comparison).
