# Stream CDN 403 — idempotent jobs + board truth + warmup retry

**Date:** 2026-08-06  
**Surfaces:** `platform_api`  
**Branch:** `bugfix/stream-cdn-403-idempotent-board`

## Summary

After the Aug 6 CDN URL heal (`cdn_url_for_suno_audio_id`), streaming uploads
often hit `cdn1.suno.ai` before the object was downloadable → transient **403**,
then succeeded ~1–2 minutes later. Duplicate job rows (callback + reconcile)
left the failed attempts in place, so Pipeline Ops marked whole batches
**Failed** even when every clip later succeeded (`fail_only=0` in prod).

## Product impact

- Pipeline Ops no longer shows **Failed** for clips that later uploaded
  successfully.
- Streaming catalog still archives MP3s; fewer false-fail rows and less
  duplicate work when the same Suno task is scheduled twice.
- Progress / missing-MP3 CDN heal is **unchanged** (synthesize URL from
  `audio_id` remains).

## Technical impact

1. **Board aggregation** — one outcome per `(suno_task_id|song_id, kind)`;
   success wins over earlier failed/pending history.
2. **Idempotent MP3 jobs** — skip if success exists; reuse failed/pending row
   instead of inserting another.
3. **CDN warmup retry** — HTTP 403/404 use longer backoff (5/15/30/45s);
   upload path refreshes record-info between CDN miss rounds.
4. **Same-variant URL candidates only** — never fall back to the opposite
   OK/ALT URL when downloading a variant.

## Files touched

- `platform_api/services/admin_pipeline_service.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/repositories/streaming_repo.py`
- `platform_api/tests/test_admin_pipeline_streaming_aggregate.py`
- `platform_api/tests/test_streaming_upload_service.py`
- `platform_api/tests/test_suno_audio_resolver.py`
- `platform_api/CHANGELOG.md`

## Migration / deploy

- No DB migration.
- Deploy `platform_api` (sandbox first). API process picks up board + upload
  changes; streaming uploads run in-process on the API (not stage workers).

## Tests

- `pytest platform_api/tests/test_admin_pipeline_streaming_aggregate.py -q`
- `pytest platform_api/tests/test_streaming_upload_service.py -q`
- `pytest platform_api/tests/test_suno_audio_resolver.py -q`

## Follow-ups

- Optional unique partial index on `(suno_task_id, kind)` for MP3 jobs to
  harden concurrent first inserts.
- Separate: image reference path fallthrough / stuck `manual_image` pending.
- Separate: age-out abandoned Waiting rows on Pipeline Ops.
