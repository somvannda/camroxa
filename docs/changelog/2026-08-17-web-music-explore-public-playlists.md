# Web music explore — public playlists and creators

**Date:** 2026-08-17  
**Surfaces:** `platform_api`, `music_web`

## Summary

Explore and Artists now surface **web music public playlists** instead of the legacy streaming album catalog for creator discovery.

## Backend

- `GET /api/v1/web-music/public/playlists` — recent public playlists with creator info and cover art from the first track.
- `GET /api/v1/web-music/public/artists` — creators with at least one public playlist; returns `playlist_count` and `track_count`.
- `GET /api/v1/web-music/public/artists/{user_id}` — creator profile with their public playlists.

## Frontend

- Explore page: **Recent public playlists** section; Artists section uses web music creators.
- Artist cards: **playlists · tracks** counts (replaces albums · tracks).
- Artist detail page: shows public playlists instead of streaming discography.

## Notes

- A user appears in Artists only after they set at least one playlist to **public**.
- Playlist cover uses the first item's Suno cover image when available.
- **Recently added** shows tracks from both the streaming catalog and songs added to public playlists.
- Your web music tracks appear in Recently added when you **add them to a public playlist** (Create → Playlists → set Public → add songs).
- Streaming-only artists remain visible alongside web music creators with public playlists.
- Web music play counts increment on stream playback; likes work for your tracks and public playlist tracks.
- Track row heart button is no longer blocked by nested button markup.
