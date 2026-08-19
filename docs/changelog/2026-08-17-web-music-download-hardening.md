# Web music download hardening

**Date:** 2026-08-17  
**Surfaces:** `platform_api`

## Summary

Hardens web music media delivery: reject non-MP3 Suno downloads (m4a/HLS), rate-limit download/play endpoints, short-lived play tokens (hide task UUIDs), and automatic B2 backfill when serving from Suno fallback.

## Changes

### MP3-only from Suno
- Filter disallowed URLs (`.m4a`, `.m3u8`, `audio/mp4`) in `build_download_url_candidates`
- Validate downloaded bytes (ID3 / MPEG sync; reject `ftyp` MP4 containers)
- Reject non-MP3 `Content-Type` on Suno HTTP responses
- `_extract_clip_download_url` skips m4a URLs

### Backblaze storage (unchanged path, stronger behavior)
- Files remain under `web-music/{user_id}/{song_slug}-{ok|alt}.mp3` and `.wav`
- On B2 miss or invalid MP3 object, schedule async backfill upload
- B2-served bytes validated before return

### Play tokens
- Redis tokens TTL 15 minutes at `/api/v1/web-music/play/{token}`
- Public discovery tracks mint `access=public` tokens
- Create workspace clips mint `access=owner` tokens
- Legacy `/generations/{id}/stream` kept for compatibility

### Rate limits
- `web_music_download`: 30 req / 60s per user (MP3, WAV, LRC, SRT)
- `web_music_play`: 120 req / 60s per user or IP (anonymous public play)
