# Create workspace Ready only when audio actually streams

**Date:** 2026-08-18  
**Surfaces:** music_web, platform_api

## Summary

Create workspace no longer shows Play / Ready when Suno has only returned a URL. Ready waits until a short Range request succeeds (CDN has the file) or our Backblaze copy exists. Until then the cover stays on a spinner and the label says Finishing.

## Product impact

- Play on the cover and in track details stays disabled until the clip can actually start.
- After Suno says SUCCESS, status is Finishing (not Ready) for the usual CDN delay of a few minutes.
- Existing Ready tracks stay Ready (stream flags are backfilled).

## Technical impact

- `clips[].ready` requires `stream_ready_ok` / `stream_ready_alt`, or a task-scoped B2 key.
- `get_generation` probes `bytes=0-2047` on the Suno origin and persists the flag on 200/206.
- Origin 403/HTML is not treated as playable. The Create poll keeps running until both clips verify.
- Migration `106_web_music_stream_ready`.

## Files touched

- `platform_api/services/suno_audio_resolver.py`
- `platform_api/services/web_music_service.py`
- `platform_api/migrations/versions/106_web_music_stream_ready.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `music_web/src/components/create-page-client.tsx`
- `music_web/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration/deploy

File-scoped sandbox hotfix: `ALTER` stream-ready columns, backfill existing URL rows, upload the files above, restart API, rebuild music web. Production stays untouched until asked.

## Tests

- Generate a song: cover spinner and Finishing until playback actually starts; then Ready and Play.
- Existing Ready tracks still show Play after deploy.
- `pytest platform_api/tests/test_suno_audio_resolver.py platform_api/tests/test_web_music_router.py`

## Follow-ups

- None.
