# Music web: Version 1/2 were the same Backblaze file

**Date:** 2026-08-18  
**Branch:** `fix/music-web-generate-assist`

## Summary

Create listed Version 1 as 2:46 and Version 2 as 2:55, but play used 2:54 for both. The stream paths were already unique. Production Backblaze objects `ok.mp3` and `alt.mp3` for that generation were the same bytes (same size and ETag) because uploads could fall back to the other clip’s Suno URL. Playback also went through the media CDN, which kept serving that one file.

## Product impact

Version 1 and Version 2 play their own audio. The player timer matches the row duration.

## Technical impact

- Web-music MP3 upload does not fall back to the other variant’s URL.
- Force Backblaze re-upload can overwrite task-scoped keys.
- Create stream origin uses a signed B2 URL (`use_cdn=False`) so a stale CDN object cannot mask a new upload.

## Files touched

- `platform_api/services/storage_service.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/web_music_service.py`

## Migration/deploy

File-scoped API hotfix plus a one-shot re-upload of web-music tasks whose ok/alt objects share an ETag. No schema migration. No music_web rebuild required.

## Tests

- Signed B2 URL helper still returns the CDN path when `use_cdn` is left on.

## Follow-ups

Hard-refresh Create and play Version 1 first; it should show 2:46.
