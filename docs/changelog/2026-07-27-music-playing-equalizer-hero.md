# Playing equalizer highlight + cover-color album hero

**Date:** 2026-07-27  
**Status:** implemented (sandbox deploy)

## Summary

Track lists now clearly mark the active song with a fuchsia/violet row highlight and animated equalizer bars (static bars when paused). Album heroes pick up color from the cover (blurred backdrop + optional dominant-color overlay) instead of a fixed purple wash.

## Product impact

**Before:** Current track was easy to miss; equalizer used weak pulse; album hero was always the same violet gradient.  
**After:** Playing row has a left accent + tinted background and bouncing bars; album pages atmosphere matches the artwork.

## Technical impact

- `PlayingEqualizer` + `.eq-bar` / `.track-row-playing` CSS in `globals.css`.
- `TrackRow` album + default variants show equalizer when current.
- New client `AlbumHero` (blurred cover + canvas palette with purple fallback).

## Files touched

- `music_web/src/components/playing-equalizer.tsx`
- `music_web/src/components/track-row.tsx`
- `music_web/src/components/album-hero.tsx`
- `music_web/src/app/albums/[id]/page.tsx`
- `music_web/src/app/globals.css`
- `music_web/CHANGELOG.md`
- `docs/MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`

## Migration / deploy

- No API/DB changes.
- Sandbox: `python scripts/deploy/rebuild_music_web_sandbox.py`

## Tests

- `npx tsc --noEmit` in `music_web`.
- Sandbox rebuild + visual check: play a track → bars animate; pause → bars still; album hero tinted.

## Follow-ups

- Library / likes / playlists (Phase 5).
- Synced scrolling lyrics.
