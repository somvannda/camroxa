# Playlist detail: professional mobile/desktop UX

**Date:** 2026-08-21  
**Branch:** `feature/playlist-detail-ux-ship`  
**Surfaces:** music_web

## Summary

Playlist detail used a native HTML `<select>` (white system menu) and a homemade more-menu that wrapped under the cover because the track grid had too few columns. Phone layout truncated the title, hid row actions, and made Remove look like artwork.

The page now uses the shared Radix Select (`MusicSelect`) and DropdownMenu, album Play/Shuffle controls, and a stable track grid for phone and desktop.

## Product impact

- Sort menu matches Create and the rest of music_web (dark themed, not the OS select).
- Remove lives in a proper “…” menu: Play/Pause plus **Remove from playlist**.
- Phone: cover + title + style + date, always-visible more button, wrapping playlist name.
- Desktop: `#` / play-on-hover, title, date added, more on hover.
- Empty playlists get a clear add-songs prompt.

`music_web` had only this one native `<select>`. Create already uses `MusicSelect`.

## Technical impact

- Track grid: `title | more` on phone; `# | title | added | more` on desktop. No `sm:contents` overflow into the cover column.
- Play/shuffle reuse `AlbumPlaybackControls` (`playQueue` / `playShuffled`).
- Row play uses the same overlay pattern as album `TrackRow`.

## Files touched

- `music_web/src/components/playlist-detail-page-client.tsx`
- `music_web/CHANGELOG.md`
- `scripts/deploy/hotfix_sandbox_playlist_detail_ux.py`
- `scripts/deploy/hotfix_playlist_detail_ux_production.py`

## Migration / deploy

Sandbox file hotfix applied 2026-08-21: `scripts/deploy/hotfix_sandbox_playlist_detail_ux.py` uploaded `playlist-detail-page-client.tsx`, rebuilt music_web, restarted `camxora-music`. BUILD_ID `Jgr2k0_JKGuy1cQ-EcAu6`. No API/migration. Production stays untouched.

## Tests

- Desktop: sort menu is the dark shared Select; more menu stays in the last column; Remove does not sit on the cover.
- Phone: title wraps, more stays tappable, search stacks above sort.
- Owner can add/remove; Play still queues the playlist.

## Follow-ups

- Confirm on https://music.sandbox.camxora.com/playlists (hard refresh).
- Does not touch playlist-add files (`add-to-playlist-button`, memberships API, `web_music_service`). Those stay on `bugfix/playlist-add-packaged-ux`.
- Playlist items still have no duration; a Time column can wait on API duration.
