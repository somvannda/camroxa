# Pipeline Ops: stale streaming 403s looked like live failures

**Date:** 2026-08-16  
**Status:** implemented  
**Branch:** `bugfix/pipeline-stale-streaming-error`

## Summary

Admin **Pipeline Ops** (`/pipeline`) painted completed albums as live **Error** with a 1–5s age when leftover catalog-archive jobs had `403 Forbidden` from expired `cdn1.suno.ai` MP3 URLs. Music/images were already done; the user had not started a new run. Desktop Progress sync also re-stamped `batches.updated_at` on every heartbeat even when status was unchanged.

## Product impact

- Failed streaming archive jobs show on the **streaming chip** (`Failed X/Y`), not as a red pipeline Error row.
- Completed music+image batches drop off the default active board even if some Backblaze copies 403'd.
- Age no longer jumps to “a few seconds ago” from Progress sync heartbeats.

## Technical impact

- `_promote_admin_stage` no longer returns Error solely because `stream_upload_jobs` failed. Pending uploads still show **Streaming**. Music+images done with no pending uploads promote to **Done** (chip still shows failures).
- Row-level `error_snippet` omits streaming 403s on Done/Completed rows.
- `update_batch_status` only writes when `status IS DISTINCT FROM` the new value, so `refresh_batch_status` from `/progress/sync-local` does not bump `updated_at`.

## Files touched

- `platform_api/services/admin_pipeline_service.py`
- `platform_api/repositories/batch_repo.py`
- `platform_api/tests/test_admin_pipeline_stage.py`
- `platform_api/tests/test_batch_status_noop.py`
- `platform_api/CHANGELOG.md`
- `admin_portal/CHANGELOG.md`

## Migration/deploy

No migration. Restart `camxora-api` after syncing `platform_api` (sandbox first). Workers do not need a restart for this change.

## Tests

- `pytest platform_api/tests/test_admin_pipeline_stage.py platform_api/tests/test_batch_status_noop.py`

## Follow-ups

- Production API deploy only when asked.
- Optional later: retry streaming archives from Backblaze-local MP3s instead of expired Suno CDN URLs.
