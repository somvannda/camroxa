# Streaming capture: dedupe upload jobs + stop paging on already-archived audio

## Summary
The hourly **STREAMING CAPTURE** Telegram report kept surfacing the same
`tempfile.aiquickdraw.com ... 404 Not Found` errors. Investigation of production
showed the failures were **redundant duplicate upload jobs**, not missing audio:
**1,405 of 1,406 failed `mp3_ok`/`mp3_alt` jobs already had a durable B2 copy**
for the same task+variant. A few tasks had accumulated thousands of jobs
(e.g. one task carried 3,755 `mp3_ok` and 3,740 `mp3_alt` jobs).

## Product impact
None. Capture itself was working; ops was being paged about jobs whose audio was
already safely stored.

## Root cause
Two compounding problems:

1. **Non-idempotent job creation.** `_upload_mp3_variant` guarded only against a
   task+variant that was *already archived* (`stream_tracks.storage_key`). That
   check is racy and ignores in-flight jobs, so re-delivered Suno callbacks and
   desktop reconcile polling each inserted a new `stream_upload_jobs` row for the
   same track. When the Suno temp URL later expired, every duplicate download
   returned 404 and the job stayed failed.
2. **Health report counted archived failures.** `count_failed_mp3_jobs` and
   `list_recent_failed_mp3_errors` counted every failed job, including duplicates
   whose track was already on B2, so the report never went quiet.

## Technical impact
- `StreamingRepository.has_active_upload_job(suno_task_id, kind, ...)` — a
  `pending` job, or a non-permanent `failed` job inside a 30-minute cooldown,
  means a capture for that task+variant is already being handled.
- `_upload_mp3_variant` now returns early when an active job exists, so repeated
  callbacks/reconciles no longer stack duplicate jobs.
- Added `_ARCHIVED_TRACK_EXCLUDED` and applied it to the auto-retry / backfill
  job selectors and to the health-report counts (`missing_b2_only=True`), so
  workers stop churning on and ops stops paging about already-archived audio.
- No schema change.

## Tests
`platform_api/tests/test_streaming_upload_dedup.py` (new), plus expanded
`test_streaming_upload_service.py` and `test_streaming_health_report.py`.
Focused streaming suite: 27 passed.

## Follow-ups
- Optional DB backstop: partial unique index on
  `stream_upload_jobs (suno_task_id, kind) WHERE status = 'pending'`.
- Production backlog cleanup: mark already-archived failed jobs
  `permanent_failed` and decide whether to prune the redundant rows.

## Files touched
- `platform_api/repositories/streaming_repo.py`
- `platform_api/services/streaming_upload_service.py`
- `platform_api/services/streaming_health_report.py`
- `platform_api/tests/test_streaming_upload_service.py`
- `platform_api/tests/test_streaming_health_report.py`
- `platform_api/tests/test_streaming_upload_dedup.py`
