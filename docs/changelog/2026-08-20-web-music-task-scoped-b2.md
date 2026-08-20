# Create leftover B2 keys were unplayable

**Date:** 2026-08-20  
**Branch:** `bugfix/music-web-ios-protected-playback`

## Summary

Camxora Music leftovers were stored as `web-music/{user}/untitled-ok.mp3`, so many songs shared one file. Protected playback then required the task id in the B2 path before a clip could play. Playlist tracks such as **Tense Release** and Create rows stuck on **Finishing** still had those shared keys, were **not** encrypted, and the player correctly refused them.

## Product impact

**Before:** Opening Create after Suno finished could show **Finishing** forever. Playlist play icons did nothing for those leftovers.

**After:** Ingest writes `web-music/{user}/{task_id}/{ok|alt}.mp3`. Opening Create or the playlist re-uploads shared/untitled leftovers onto unique keys. Those clips become Ready and play (plaintext leftover until packaging, then the encrypted player).

## Technical impact

- Shared slug keys are treated as missing; B2 backfill overwrites them.
- Packaging backfill skips untitled keys so one shared MP3 is not encrypted onto several tasks.
- Create polling and playlist item loads schedule that repair.

## Files touched

- `platform_api/services/web_music_storage_keys.py`
- `platform_api/services/web_music_service.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/audio_package_service.py`
- `platform_api/tests/test_web_music_storage_keys.py`
