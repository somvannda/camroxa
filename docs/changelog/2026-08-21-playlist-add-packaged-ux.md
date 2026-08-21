# Playlist add — packaged clips + Create-page confirmation

**Date:** 2026-08-21  
**Surfaces:** platform_api, music_web

## Summary

Adding a generated song to a playlist failed on sandbox and production after protected playback: the Create page treated packaged clips as ready, but `POST /web-music/playlists/{id}/items` still required a Suno origin URL (`audio_url_ok` / `audio_url_alt`). Those URLs are cleared after packaging, so playable songs returned 422 “This song version is not ready yet.”

The add control now confirms the save with a tick animation, keeps the menu open so a clip can go into more than one playlist, and shows playlist name chips on the Create track row.

## Changes

- `add_playlist_item` uses the same playable check as playback (`package_status` / packaged key / B2 key), not origin URLs.
- `GET /api/v1/web-music/playlists/memberships` returns compact `{playlist_id, playlist_name, task_id, variant}` rows for the signed-in owner.
- Create playlist button: pop-in tick, per-playlist checkmarks, menu stays open, chips under the track title.

## Verification

- `pytest platform_api/tests/test_web_music_playlist_add.py platform_api/tests/test_web_music_router.py -q`
- On Create, add a packaged song to playlist A (tick + chip), then playlist B without closing the menu.
