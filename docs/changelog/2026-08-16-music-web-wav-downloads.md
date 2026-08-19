# Music Web — WAV Downloads

**Date**: 2026-08-16  
**Surfaces**: platform_api, music_web  
**Status**: ✅ Implemented, deployed to sandbox

## Summary

Added WAV download support for web music generations, enabling users to download high-quality lossless audio files in addition to MP3.

## Changes

### Backend (`platform_api`)

1. **Database Migration** (`085_web_music_wav_support.py`):
   - Added WAV-related columns to `suno_tasks` table:
     - `wav_task_id_ok`, `wav_task_id_alt`: Track Suno WAV conversion task IDs
     - `wav_url_ok`, `wav_url_alt`: Store WAV download URLs
     - `wav_status_ok`, `wav_status_alt`: Track conversion status (pending/success/failed)

2. **Suno Client** (`clients/suno_client.py`):
   - `submit_wav_task()`: Submit WAV conversion request to Suno API (POST /api/v1/wav/generate)
   - `poll_wav_status()`: Poll WAV conversion status (GET /api/v1/wav/record-info)
   - `extract_suno_wav_task_id()`: Parse WAV submission response
   - `parse_suno_wav_poll()`: Parse WAV polling response

3. **Web Music Service** (`services/web_music_service.py`):
   - `download_wav()`: Handle WAV downloads with on-demand conversion
     - Checks if WAV conversion already exists
     - Submits new conversion if needed
     - Polls status with retries (up to 3 attempts)
     - Downloads and returns WAV file

4. **API Router** (`routers/web_music.py`):
   - Added `/generations/{task_id}/download-wav` endpoint
   - Supports `variant` query parameter (ok/alt)
   - Returns WAV file with proper content-type and disposition headers

### Frontend (`music_web`)

1. **API Client** (`lib/web-music-api.ts`):
   - `downloadWebMusicClipWav()`: Fetch and trigger WAV download

2. **Create Page** (`components/create-page-client.tsx`):
   - Enabled WAV download buttons in main song list
   - Added WAV button in right sidebar next to MP3
   - Both buttons disabled until track is ready
   - Updated download button labels to "MP3" and "WAV" for clarity

## Technical Details

### WAV Conversion Flow

1. User clicks WAV download button
2. Backend checks if WAV conversion exists for this task+variant
3. If not, submits conversion request to Suno API with `taskId` and `audioId`
4. Polls Suno for conversion status (up to 3 attempts with 2s intervals)
5. Once ready, downloads WAV file and returns to user
6. Stores WAV task ID and URL in database for future requests

### Error Handling

- Validates track is in SUCCESS status before conversion
- Returns clear error if track not ready or conversion fails
- Gracefully handles missing audio IDs or external task IDs
- Stores failure status in database to avoid repeated attempts

## Deployment

### Migration

```bash
python scripts/deploy/run_alembic_upgrade_sandbox.py
```

### API Sync

```bash
python scripts/deploy/sync_platform_api_sandbox.py
```

### Frontend Rebuild

```bash
python scripts/deploy/rebuild_music_web_sandbox.py
```

## Testing

1. Generate a song on music.sandbox.camxora.com
2. Wait for both versions to complete
3. Click WAV button on either version
4. Verify WAV file downloads successfully
5. Check file is valid WAV format (not MP3)
6. Repeat download should use cached conversion

## Notes

- WAV conversion uses Suno API credits (separate from generation)
- Converted WAV URLs are stored for reuse (no re-conversion needed)
- WAV files are typically 10-20x larger than MP3
- First WAV download may take 5-10 seconds for conversion
- Subsequent downloads are instant (uses cached URL)

## Future Enhancements

- Add loading indicator during WAV conversion
- Add credit cost information for WAV downloads
- Consider WAV quota/limits for free users
- Add WAV option to bulk download feature
