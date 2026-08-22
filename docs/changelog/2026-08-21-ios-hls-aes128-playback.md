# AES-128 HLS lane for iOS Safari

**Date:** 2026-08-21  
**Branch:** `bugfix/ios-player-responsive`  
**Surfaces:** `platform_api`, `music_web`

## Summary

Adds an AES-128 HLS packaging and playback lane for iOS Safari. Safari plays session-bound `index.m3u8` through native HTML audio so lock screen and Dynamic Island use the real media element. Chrome desktop keeps CXA1 + MSE; iOS Chrome (CriOS) keeps progressive Web Audio.

## Backend

- Migration `115_hls_playback`: `hls_storage_prefix`, `hls_status` on catalog + Create rows.
- `hls_packager.py`: ffmpeg AAC TS segments, AES-128 key derived from content key (HKDF).
- Ingest/backfill uploads `{package_key}.hls/index.m3u8` + `seg*.ts`.
- License routes:
  - `GET /licenses/hls/{token}/index.m3u8` (rewritten playlist)
  - `GET /licenses/hls-key/{token}` (16-byte AES key, session auth)
  - `GET /licenses/hls/{token}/{segment}.ts`
- `POST /licenses/admin/backfill-hls` for existing packaged tracks.

## Frontend

- iOS Safari prefers `session.hls_url`, falls back to MP3 `play_url`, then Web Audio.
- In-DOM `<video>` (not `<audio>`) for Safari HLS — iOS binds lock screen / Dynamic Island to video.
- No silent WAV on the player element during HLS load (was breaking first-lock Now Playing).
- Media Session sync on native `playing` event + metadata before stream src.
- Traces: `path=hls_aes128`, `ctx=video`.

## Requirements

- **ffmpeg** on API/worker hosts for HLS packaging and backfill.
- Run migration + HLS backfill before Safari users see the new lane.

## Sandbox

```bash
python scripts/deploy/run_alembic_upgrade_sandbox.py
python scripts/deploy/hotfix_sandbox_ios_hls_playback.py
```
