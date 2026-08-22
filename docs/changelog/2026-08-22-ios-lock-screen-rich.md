# iOS lock screen rich Now Playing (2026-08-22)

## Enhancement
Full native lock screen layout: large artwork, title, artist (Album), elapsed/remaining scrubber, prev/next, 15s skip.

## Changes (`media-session.ts`)
- Artwork sizes up to **1024×1024** with correct MIME type for large lock screen art.
- Artist line formatted as **`Artist (Album)`** like Apple Music.
- **`seekbackward` / `seekforward`** handlers (15s) on lock screen.
- **`publishLockScreenNowPlaying()`** — metadata + position in one call.

## Player
- iOS HLS: **400ms** position tick + keepalive while locked.
- Native **`timeupdate`** syncs scrubber every ~350ms when screen is locked.
- HLS start publishes full lock screen state immediately.

## Deploy
```bash
python scripts/deploy/hotfix_sandbox_ios_hls_now_playing.py
```
