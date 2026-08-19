# Streaming artist list avatars

**Date:** 2026-08-17  
**Surfaces:** `platform_api`, `music_web`

## Summary

Published streaming artists (e.g. Somvannda Kong with 80 albums but no public playlists) now include `avatar_url` in the public artists API. Artist cards on Home, Explore, and `/artists` show uploaded profile photos instead of letter initials.

## Root cause

Artist list pages merge streaming catalog artists with web-music public-playlist creators. Only the web-music list returned `avatar_url`; streaming `list_artists` omitted it, and the frontend merge dropped it for streaming-only creators.

## Changes

- `platform_api/repositories/streaming_repo.py` — select `users.avatar_url` in artist list query.
- `platform_api/services/streaming_catalog_service.py` — expose normalized avatar API path on list response.
- `music_web/src/lib/explore-api.ts` — preserve `avatar_url` when merging streaming artists.
- `music_web/src/lib/streaming-api.ts` — add `avatar_url` to `StreamArtist` type.
