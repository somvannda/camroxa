# Web Music — Automatic Backblaze Upload for MP3s and WAVs

**Date**: 2026-08-16  
**Surfaces**: `platform_api`, `music_web`  
**Migration**: `087_web_music_b2_storage`

## Summary

Automatically uploads web music MP3s and WAVs to Backblaze B2 storage when Suno generation completes, providing permanent storage. Play and download endpoints now seamlessly serve from Backblaze when available, falling back to Suno CDN for in-progress uploads. WAV downloads are now free (no credit cost).

## Changes

### Backend (`platform_api`)

**Database Migration** (`087_web_music_b2_storage.py`):
- Added `b2_storage_key_ok`, `b2_storage_key_alt` to `suno_tasks` table (MP3 storage)
- Added `b2_uploaded_at_ok`, `b2_uploaded_at_alt` timestamp columns (MP3 upload tracking)
- Added `b2_wav_storage_key_ok`, `b2_wav_storage_key_alt` (WAV storage)
- Added `b2_wav_uploaded_at_ok`, `b2_wav_uploaded_at_alt` (WAV upload tracking)

**Streaming Upload Service** (`streaming_upload_service.py`):
- **Removed** web_music skip — now processes both desktop and web music sources
- Added `_upload_web_music_variant()` method with simplified storage structure
  - MP3 storage path: `web-music/{user_id}/{song_slug}-{variant}.mp3`
  - WAV storage path: `web-music/{user_id}/{song_slug}-{variant}.wav`
  - No album or catalog table entries (web music is standalone)
  - Updates `suno_tasks` with B2 storage keys after successful upload
- Added `_upload_web_music_wav()` method for automatic WAV upload
  - Submits WAV conversion to Suno API
  - Polls for WAV URL (max 60 seconds)
  - Downloads and uploads to Backblaze
  - Triggered asynchronously after MP3 upload completes
- Automatically triggers when Suno task completes with `source=web_music`

**Web Music Service** (`web_music_service.py`):
- Updated `download_mp3()` to check for B2 storage keys first
- Updated `download_wav()` to check for B2 WAV storage keys first
- Added `_download_from_backblaze()` helper method
- Falls back to Suno CDN if B2 upload not complete or fails
- Updated queries to include B2 storage key columns

### Frontend (`music_web`)

**UI Updates** (`create-page-client.tsx`):
- Updated WAV button tooltips: "Download WAV (High quality)"
- Removed credit cost notices (WAV downloads are now free)

## Behavior

### Auto-Upload Flow

**MP3 Upload**:
1. User creates music via web music interface
2. Suno generation completes → callback lands → `streaming_upload_service` triggered
3. Service downloads MP3 from Suno CDN
4. Uploads to Backblaze at `web-music/{user_id}/{slug}-{variant}.mp3`
5. Updates `suno_tasks.b2_storage_key_ok/alt` and `b2_uploaded_at_ok/alt`
6. Triggers WAV upload asynchronously

**WAV Upload** (happens automatically after MP3):
1. Submits WAV conversion request to Suno API
2. Polls for conversion completion (up to 60 seconds)
3. Downloads WAV from Suno CDN
4. Uploads to Backblaze at `web-music/{user_id}/{slug}-{variant}.wav`
5. Updates `suno_tasks.b2_wav_storage_key_ok/alt` and `b2_wav_uploaded_at_ok/alt`

### Playback / Download Flow

**MP3 Downloads**:
1. User clicks play or download
2. Backend checks if `b2_storage_key_{variant}` exists
3. If yes → downloads from Backblaze and serves
4. If no or B2 fails → falls back to Suno CDN URLs (refreshed if needed)

**WAV Downloads**:
1. User clicks WAV download
2. Backend checks if `b2_wav_storage_key_{variant}` exists
3. If yes → downloads from Backblaze and serves (permanent storage)
4. If no or B2 fails → initiates Suno WAV conversion and downloads from Suno CDN
5. No credit cost for WAV downloads (changed from previous 3-credit cost)

## Notes

- B2 uploads are fire-and-forget — failures are logged but don't block generation flow
- WAV upload happens asynchronously after MP3, independent of user action
- Existing web music (created before this migration) will upload on next callback or on-demand
- Desktop app music continues to use album-based structure in `stream_tracks` table
- Storage keys in `suno_tasks` are web-music-specific (not linked to `stream_tracks`)
- WAV files are now permanently stored (no more 14-day Suno expiration)

## Testing

1. Create a web music song
2. Wait for generation to complete
3. Check database: `SELECT b2_storage_key_ok, b2_wav_storage_key_ok, b2_uploaded_at_ok, b2_wav_uploaded_at_ok FROM suno_tasks WHERE id = '...'`
4. Play/download MP3 — should work from Backblaze after upload completes
5. Download WAV — should work from Backblaze (no credit cost)
6. Verify fallback works if B2 is temporarily unavailable
7. Check that WAV button shows "High quality" tooltip (no credit warning)
