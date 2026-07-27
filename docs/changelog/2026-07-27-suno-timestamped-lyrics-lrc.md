# Suno timestamped lyrics → LRC on stream tracks

**Date:** 2026-07-27  
**Status:** implemented (sandbox + production deployed)

## Summary

After Suno music generation uploads to the streaming catalog, the platform now fetches word-aligned timestamps via `POST /api/v1/generate/get-timestamped-lyrics`, converts them to line-level LRC, and stores that on `stream_tracks.lyrics`. The music portal already karaoke-scrolls only when real LRC is present.

## Product impact

**Before:** Stream tracks stored plain draft lyrics; Now Playing showed static text.  
**After:** New uploads (and metadata sync) prefer Suno-aligned LRC when available → synced lyrics in the player. Instrumentals / API failures still fall back to plain lyrics.

## Technical impact

- Persist Suno clip IDs: `suno_tasks.audio_id_ok` / `audio_id_alt`, `stream_tracks.suno_audio_id`
- Parse clip `id` from record-info + callbacks
- `SunoClient.get_timestamped_lyrics(taskId, audioId)`
- `aligned_words_to_lrc` groups words on newlines into `[mm:ss.xx]` lines
- Streaming upload + admin metadata sync fetch LRC; never overwrite existing LRC with plain text

## Files touched

- `platform_api/migrations/versions/074_suno_audio_ids.py`
- `platform_api/clients/suno_client.py`
- `platform_api/services/suno_lrc.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/streaming_metadata_sync_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/repositories/streaming_repo.py`
- `platform_api/routers/callbacks.py`
- `platform_api/tests/test_suno_lrc.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `platform_api/CHANGELOG.md`
- `docs/MUSIC_STREAMING_PORTAL_ENHANCEMENT.md`

## Migration / deploy

1. `python scripts/deploy/run_alembic_upgrade_sandbox.py` (revision `074_suno_audio_ids`)
2. `python scripts/deploy/sync_platform_api_sandbox.py`
3. Optional backfill: admin metadata sync on existing tracks (needs clip ids from record-info refresh)

No music_web rebuild required for new lyrics content (player already supports LRC).

## Tests

- `pytest platform_api/tests/test_suno_lrc.py platform_api/tests/test_suno_audio_resolver.py platform_api/tests/test_streaming_metadata_sync_service.py`

## Follow-ups

- Optional one-shot backfill script for catalog tracks that already have `external_task_id` but plain lyrics
- Confirm credit cost / rate limits on `get-timestamped-lyrics` in production
- Production deploy when sandbox verified
