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

## Second blocker — dead `audiostream.api.box` stream host

Once polls were answered again, the client started downloading — but a subset of
tracks resolved to `https://audiostream.api.box/stream/<id>.mp3`, which now
answers `200 audio/mpeg` with a **0-byte body**, so those never completed.

A previous production hotfix (`apply_suno_stream_host_and_recover_production.py`)
had deliberately preferred that host over `tempfile.aiquickdraw.com`. That is no
longer true. The same clip id serves a healthy MP3 from the tempfile sibling
(verified 3.6–5.6 MB for the failing ids).

Fix:

- `platform_api/clients/suno_client.py` — `prefer_suno_mpeg_cdn_url` rewrites any
  `audiostream.api.box` URL to `https://tempfile.aiquickdraw.com/r/<id>.mp3`
  (clip id parsed from the path or taken from `audio_id`). This is the shared
  normalizer used by the pending list, the redownload plan, and server-side B2
  archiving, so existing rows are fixed without a data migration and new
  callbacks stop storing the dead host.
- `platform_api/services/suno_audio_resolver.py` — `audiostream.api.box` added to
  `_DISALLOWED_URL_MARKERS` (same precedent as `musicfile.removeai.ai`, which also
  returns `200 audio/mp3` with 0 bytes).

No desktop rebuild is required — the client just receives working URLs.

## Tests

`platform_api/tests/test_pending_downloads_latency.py`:

- `test_pending_downloads_offload_reconcile_and_image_jobs` — asserts the endpoint
  schedules (never awaits) reconcile and image-job healing.
- `test_pending_b2_resolution_times_out_without_blocking` — asserts a slow B2 returns
  inside the budget with an empty/partial map.
- `test_pending_b2_resolution_returns_urls` — asserts the concurrent happy path.

Stream-host rewrite:

- `test_suno_clip_download_url.py::test_prefers_real_mp3_over_dead_stream_host`
- `test_suno_clip_download_url.py::test_stream_host_only_synthesizes_tempfile`
- `test_suno_audio_resolver.py::test_prefer_suno_mpeg_cdn_url_rewrites_dead_stream_host`

```
python -m pytest tests/test_pending_downloads_latency.py tests/test_suno_clip_download_url.py tests/test_suno_audio_resolver.py -q
python -m pytest tests -q -k "batch or download or progress or reconcile or suno or image_job or history"
```

## Deploy

File-scoped production hotfix (allowlisted path only):

```
python scripts/deploy/hotfix_api_pending_downloads_latency_production.py
```
