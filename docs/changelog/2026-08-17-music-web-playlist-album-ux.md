# Music web: playlist detail matches album UX

**Date:** 2026-08-17

## Summary

- Playlist detail now uses the same collection hero as albums: cover-tinted card, large title, purple Play, outlined Shuffle.
- Track rows reuse the album table (`#`, title, like, time) with hover play and an owner-only remove menu.
- Playlist-only actions stay: public toggle, search/sort, and Add songs.

## Surfaces

- `music_web` — `playlist-detail-page-client`, `album-hero`, `album-playback-controls`, `album-track-list`, `track-row`
