# Music portal Liked Songs (library Phase 5 slice)

**Date:** 2026-07-27  
**Status:** implemented (sandbox deploy)

## Summary

Signed-in listeners can like/unlike published tracks. Likes persist in `stream_track_likes`, appear in Your Library → Liked Songs, and sync via hearts on the player and track rows. Custom playlists remain a follow-up.

## Product impact

**Before:** Library page was a stub.  
**After:** Heart saves to Liked Songs; library lists them; guest heart → sign-in.

## Technical impact

- Migration `073_stream_track_likes`
- Auth routes: `GET/PUT/DELETE /api/v1/streaming/library/likes…`
- `LikesProvider` + `LikeButton` on music_web

## Files touched

- `platform_api/migrations/versions/073_stream_track_likes.py`
- `platform_api/repositories/streaming_repo.py`
- `platform_api/services/streaming_catalog_service.py`
- `platform_api/routers/streaming_library.py`
- `platform_api/main.py`, `wire_dependencies.py`
- `music_web/src/lib/library-api.ts`
- `music_web/src/components/likes-provider.tsx`
- `music_web/src/app/library/page.tsx`, `layout.tsx`
- `music_web/src/components/player-bar.tsx`, `track-row.tsx`, `sidebar.tsx`, `album-track-list.tsx`
- `platform_api/CHANGELOG.md`, `music_web/CHANGELOG.md`

## Migration / deploy

1. `python scripts/deploy/sync_platform_api_sandbox.py`
2. `python scripts/deploy/run_alembic_upgrade_sandbox.py` (or ensure upgrade head)
3. `python scripts/deploy/rebuild_music_web_sandbox.py`

## Tests

- Typecheck music_web; sandbox migrate + API/music deploy; sign-in → like → library list.

## Follow-ups

- Custom playlists CRUD; recently played; follow artists.
