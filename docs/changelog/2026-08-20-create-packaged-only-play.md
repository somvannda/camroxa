# Create play only after packaging

**Date:** 2026-08-20  
**Branch:** `bugfix/music-web-ios-protected-playback`

## Summary

Camxora Music Create clips are playable only after both the unique B2 object exists **and** that version is packaged. Leftover plaintext `/stream` play is removed. Each version becomes Ready on its own once packaged.

## Product impact

Create and playlist tracks stay on **Finishing** until packaging completes, then **Ready** with the encrypted player. There is no leftover MP3 play path.

## Files touched

- `platform_api/services/web_music_service.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/tests/test_web_music_storage_keys.py`
- `platform_api/tests/test_protected_playback_theft_vectors.py`
