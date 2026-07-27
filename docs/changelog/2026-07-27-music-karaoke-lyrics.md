# Karaoke-style Now Playing lyrics + remove album inline lyrics

**Date:** 2026-07-27  
**Status:** implemented (sandbox deploy)

## Summary

Removed Show/Hide lyrics under album tracks. Lyrics now live in the right Now Playing panel. Karaoke highlight + auto-scroll run **only** when the stored lyrics contain real LRC timestamps (`[mm:ss.xx]`). Plain catalog lyrics display as static text (manual scroll only).

## Product impact

**Before:** Expandable lyrics under each album row; later, estimated “fake karaoke” from song length.  
**After:** Clean album list; right panel shows static lyrics by default; synced motion only when LRC is present. Tap a timed line to seek.

## Technical impact

- `lib/lyrics.ts` — LRC parse; plain lines without inventing timing
- `SyncedLyrics` — synced mode uses `currentTime` / `seek`; plain mode is static `<p>` lines
- Compact Now Playing header; lyrics dominate the rail

## Files touched

- `music_web/src/lib/lyrics.ts`
- `music_web/src/components/synced-lyrics.tsx`
- `music_web/src/components/now-playing-rail.tsx`
- `music_web/src/components/album-track-list.tsx`
- `music_web/src/app/globals.css`
- `music_web/CHANGELOG.md`
- `docs/MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`

## Migration / deploy

- No API/DB changes.
- `python scripts/deploy/rebuild_music_web_sandbox.py`

## Tests

- `npx tsc --noEmit`; sandbox rebuild; plain lyrics stay still; LRC (if pasted) highlights + scrolls.

## Follow-ups

- Ingest real LRC (alignment pipeline / provider) into `stream_tracks.lyrics` — Suno lyrics API we use today returns **plain text only**, not timestamps.
- Custom playlists; shuffle/repeat toggles.
