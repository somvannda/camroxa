# Music web: retry this clip’s Suno URL; never mix Version 1/2 on MP3/WAV

**Date:** 2026-08-18  
**Branch:** `fix/music-web-generate-assist`

## Summary

Create Backblaze uploads used to skip a clip when its Suno CDN URL was not ready yet (or fall back to the other clip). Suno CDN often lags a few seconds after generate success. Uploads now wait and retry **that clip only**, then reschedule if it is still not ready. MP3 and WAV downloads do the same: refresh, retry, and never use the sibling version. WAV download no longer runs the MP3 validator (RIFF/WAVE is required).

## Product impact

Version 1 and Version 2 keep their own MP3/WAV files even when one Suno link is slow. Download buttons wait briefly for that clip’s CDN instead of grabbing the other version.

## Technical impact

- `variant_url_candidates` defaults to this clip only.
- Web-music B2 MP3 upload retries record-info + download up to 12 times (~36s), then schedules another backfill round (max 6).
- WAV B2 upload and user WAV download validate WAVE bytes and retry this variant’s URL.
- User MP3 download retries this variant’s Suno URL (not the other clip).

## Files touched

- `platform_api/services/suno_audio_resolver.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/web_music_service.py`

## Migration/deploy

File-scoped API hotfix. No migration. No music_web rebuild.

## Tests

- Default URL candidates exclude the other clip.
- WAVE magic bytes are accepted; MP3 is not treated as WAV.

## Follow-ups

None.
