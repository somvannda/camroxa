# Pending-downloads poll latency — desktop MP3 sync unstuck

**Date:** 2026-10-02
**Status:** implemented (deploy pending)
**Area:** `platform_api/services/batch_service.py`

## Problem

The desktop client (v1.4.4) polls `GET /music/downloads/pending` every ~73s with
a **30s** httpx timeout to keep retrying Suno MP3 downloads. From ~13:30 local the
route stopped answering within 30s and timed out on every poll (98 times in one
day's client log), so the client never received the pending list again and every
run froze at 2–4 of 15 tracks.

Evidence gathered while diagnosing:

- All 26 Suno `tempfile.aiquickdraw.com` URLs that logged `404` during the first
  download pass now return `200 audio/mpeg` — the 404s were transient, and a
  normal retry would have fixed them.
- The desktop's `/progress` poll succeeded at the same moment `/music/downloads/pending`
  timed out, so this was not connectivity or auth.
- Unauthenticated, the pending route answers `401` in <1s, so the latency is inside
  the authenticated handler, not routing.

## Root cause

`BatchService.list_pending_suno_downloads` did three heavy things inline on every poll:

1. `reconcile_pending_suno_tasks(...)` — a live Suno status poll per in-flight task.
2. `ensure_batch_image_jobs(...)` — a `get_batch_for_user` + `get_image_jobs_by_batch`
   round-trip per batch with pending downloads.
3. `_resolve_pending_b2_urls(...)` — a sequential B2 `HEAD` (cache-bust ETag) per
   archived track, each building a fresh boto3 client.

Item 2 reintroduced the exact anti-pattern the 2026-08-02 capacity fix removed from
`/progress` (`progress.py` only ensures batches that have *no* `image_jobs` rows).

## Fix

`platform_api/services/batch_service.py`:

- **Reconcile** now runs debounced (60s, per user) in the background via
  `_schedule_pending_reconcile`; the next poll observes the updates.
- **Image-job healing** now runs debounced (60s, per user) in the background via
  `_schedule_pending_image_jobs`.
- **B2 URL resolution** now fans out concurrently (8) and is capped at 8s
  (`_PENDING_B2_RESOLVE_TIMEOUT_S`); on timeout it returns the partial result
  (Suno URLs still returned) instead of blocking the response.
- Added `_track_background_task` which keeps a strong reference to detached tasks so
  they are not garbage-collected mid-flight (the dead-URL probe now uses it too).

Debounced/inflight guards prevent frequent desktop polls from stampeding Suno or the
DB, and per-process state mirrors the existing dead-download-probe pattern.

## Tests

`platform_api/tests/test_pending_downloads_latency.py`:

- `test_pending_downloads_offload_reconcile_and_image_jobs` — asserts the endpoint
  schedules (never awaits) reconcile and image-job healing.
- `test_pending_b2_resolution_times_out_without_blocking` — asserts a slow B2 returns
  inside the budget with an empty/partial map.
- `test_pending_b2_resolution_returns_urls` — asserts the concurrent happy path.

```
python -m pytest tests/test_pending_downloads_latency.py -q
# 3 passed
python -m pytest tests -q -k "batch or download or progress or reconcile or suno or image_job or history"
# 451 passed
```

## Deploy

File-scoped production hotfix (allowlisted path only):

```
python scripts/deploy/hotfix_api_pending_downloads_latency_production.py
```
