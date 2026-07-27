# Streaming play counts (track + album totals)

**Date:** 2026-07-27  
**Status:** implemented; sandbox live

## Summary

Added listen analytics: each track stores `play_count`, incremented when a signed play URL is issued. Album `play_count` is the sum of its tracks. Counts appear in admin streaming catalog and on the music portal album/track UI.

## Product impact

**Before:** No visibility into how often tracks/albums were played.

**After:** Admin catalog shows Plays per track and album. Music portal album pages and track rows show play totals. Each successful `play-url` request counts as one play.

## Technical impact

- Migration `072_stream_track_play_count`: `stream_tracks.play_count BIGINT NOT NULL DEFAULT 0`
- `StreamingRepository.increment_play_count`; album list/detail queries expose `SUM(play_count)`
- Admin `CatalogTrackResponse` / `CatalogAlbumResponse` include `play_count`
- Public catalog + `PlayUrlResponse.play_count`

## Files touched

- API: migration `072`, `streaming_repo.py`, `streaming_catalog_service.py`, `streaming_public.py`, `streaming_admin.py`
- Admin: `use-streaming.ts`, `pages/streaming/catalog.tsx`
- Music: `streaming-api.ts`, `track-row.tsx`, `album-track-list.tsx`, `albums/[id]/page.tsx`
- Deploy: `run_alembic_upgrade_sandbox.py`, `sync_admin_portal_sandbox.py` → sandbox host resolvers

## Migration / deploy

```bash
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/run_alembic_upgrade_sandbox.py
python scripts/deploy/sync_admin_portal_sandbox.py
python scripts/deploy/rebuild_music_web_sandbox.py
```

**Sandbox (2026-07-27):** migration `072` applied; API/admin/music redeployed. Smoke: `play-url` returns/increments `play_count`; album detail includes summed `play_count`.

## Tests

- Sandbox smoke: play-url increments track count; album sum updates.

## Follow-ups

- Optional: debounce / unique-session plays to reduce refresh inflation if play-url is re-fetched mid-track.
- Admin catalog pagination (still loads up to 500).
