# Streaming health report: stop paging on permanent_failed captures

## Summary
The hourly **STREAMING CAPTURE** Telegram report kept re-sending an identical
`tempfile.aiquickdraw.com ... 404 Not Found` error every hour for a single
capture that was already terminal. Production triage (2026-10-06) found exactly
one failed, non-archived `mp3_ok` job (`5abef4fd-…`) with
`permanent_failed = true` and `attempt_count = 8`, created 2026-09-01. Its task's
`mp3_alt` variant was safely archived to B2 and the task carried
`download_unavailable_ok = true`.

## Product impact
None. No audio was lost — the alternate variant was archived. Ops was being
paged hourly about a job the retry loop had already given up on.

## Root cause
The health report's `missing_b2_only=True` reads excluded redundant duplicate
jobs whose task+variant is already archived (`_ARCHIVED_TRACK_EXCLUDED`), but did
not exclude jobs already marked terminal (`permanent_failed`). The retry /
auto-retry selectors already ignore `permanent_failed` jobs, so the report
disagreed with the retry loop and re-fired on an unactionable row forever
(`has_failures()` is true whenever `failed_total > 0`, with no age window).

## Technical impact
- `platform_api/repositories/streaming_repo.py`: new
  `_PERMANENT_FAILED_EXCLUDED` (`AND COALESCE(j.permanent_failed, false) = false`)
  applied, together with `_ARCHIVED_TRACK_EXCLUDED`, to the `missing_b2_only`
  path of `count_failed_mp3_jobs`, `count_failed_mp3_jobs_since`, and
  `list_recent_failed_mp3_errors`.
- Scoped to `missing_b2_only` so the global `count_failed_mp3_jobs()` caller
  (`streaming_upload_service.py`) and the admin/ops counts are unchanged.

## Tests
`platform_api/tests/test_streaming_upload_dedup.py` — new cases assert the
exclusion is present with `missing_b2_only=True` and absent without it. Focused
suite: 16 passed. Streaming suite (`dedup` + `health_report` +
`upload_service`): 23 passed.

## Deploy notes
No production DB change is required: the offending row is already
`permanent_failed`, so once the report respects it the hourly page stops.

## Files touched
- `platform_api/repositories/streaming_repo.py`
- `platform_api/tests/test_streaming_upload_dedup.py`
