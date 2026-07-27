# Music portal Now Playing rail + numbered album tracklist

**Date:** 2026-07-27  
**Status:** implemented (sandbox deploy)

## Summary

P1 Spotify-gap polish: while a track plays, the right rail switches from global discovery to a contextual Now Playing panel (cover, About the artist, lyrics, Next up). Album pages use a numbered `# / Title / Plays / Time` tracklist with playing-state highlight.

## Product impact

**Before:** Right rail always showed Trending/Popular; album rows were dense cards with genre/variant noise.  
**After:** Playing → contextual rail; idle → discovery. Album lists read like a modern streaming track table.

## Technical impact

- Client `DiscoveryRail` (`now-playing-rail.tsx`) reads `usePlayer()`; idle falls back to discovery sections.
- `TrackRow` gains `variant="album"` + `index`; click toggles pause when current.
- `play-url` returns `album_id`, `user_id`, `lyrics` so Home/Search plays still feed the rail.
- Album page enriches tracks with album artist/ids for queue links.

## Files touched

- `music_web/src/components/now-playing-rail.tsx`
- `music_web/src/components/catalog-cards.tsx`
- `music_web/src/components/track-row.tsx`
- `music_web/src/components/album-track-list.tsx`
- `music_web/src/components/player-provider.tsx`
- `music_web/src/app/albums/[id]/page.tsx`
- `music_web/src/lib/streaming-api.ts`
- `platform_api/routers/streaming_public.py`
- `platform_api/services/streaming_catalog_service.py`
- `music_web/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Follow-up (2026-07-27) — wider rail for full titles

Right sidebar increased from `w-80` (320px) to `w-[26rem]` (416px). Now Playing title no longer truncates (wraps with `leading-snug`).

**Files:** `music_web/src/components/now-playing-rail.tsx`  
**Deploy:** `rebuild_music_web_sandbox.py`

## Migration / deploy

- No DB migration.
- Sandbox: `sync_platform_api_sandbox.py` + `rebuild_music_web_sandbox.py`

## Tests

- `npx tsc --noEmit` in `music_web` — clean.
- Sandbox: API sync + music rebuild (`MUSIC_WEB_REBUILD_DONE`, service active).

## Follow-ups

- Cover-color album hero (P2); library/likes (Phase 5); synced scrolling lyrics.
