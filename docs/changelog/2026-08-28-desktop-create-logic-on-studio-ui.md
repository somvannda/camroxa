# Desktop Create logic on studio UI

**Date:** 2026-08-28  
**Surfaces:** desktop app (`camxora_python`)

## What

Port web-music Create generate, history, files inventory, downloads, and session 401 refresh onto the studio Create chrome from PR #122. The new UI stays. The old `features/music` Create widgets are not copied.

## Why

`feature/desktop-music-web-ui` had the working Create product on old chrome. Merging that branch into `main` would fight or revert the studio pages. This branch starts from `main` and wires the same behavior into `features/create`.

## Behavior kept

- Generate uses `POST /web-music/generate` (Advanced drafts via `/web-music/generate-draft`).
- History comes from `GET /web-music/generations` (not local JSON).
- Files table: two rows per song (Version 1, Version 2). Click never charges or downloads.
- Right-click downloads MP3/WAV/LRC/SRT for that version only.
- 401 on a still-fresh access token must rotate refresh. Helpers skip polls when signed out.

## Not included

- Old Create/login/Profile/sidebar chrome
- Production deploy
- Server auth hotfix (already on sandbox)
