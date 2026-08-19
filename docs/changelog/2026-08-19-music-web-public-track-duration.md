# Music web public track duration type

**Date:** 2026-08-19  
**Surfaces:** music_web

## Summary

`WebMusicPublicRecentTrack` was missing `duration_seconds`, so a production `next build` failed when Explore mapped clip duration. The field is now on the public-track type and copied into the catalog track mapper.

## Product impact

**Before:** Public/Explore recent tracks could not typecheck duration, which blocked a production music-web rebuild.

**After:** Public recent tracks carry optional duration; Explore can show time without a TypeScript error.

## Technical impact

- Optional `duration_seconds` on `WebMusicPublicRecentTrack`.
- `publicTrackToStreamTrack` forwards that field onto `StreamTrack`.

## Files touched

- `music_web/src/lib/playlist-api.ts`
- `music_web/src/lib/explore-api.ts`
- `music_web/CHANGELOG.md`

## Migration/deploy

No API or DB change. Type-only client fix.

## Tests

- `next build` for music_web succeeds when Explore reads `track.duration_seconds`.
- Session refresh from PR #68 is unchanged.

## Follow-ups

- None.
