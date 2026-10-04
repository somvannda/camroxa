# B2 sweep: stop re-paging on terminal WAV failures + recover them

## Summary

The recurring Telegram alert

```
B2 backfill sweep
jobs retried=0 ok=0 failed=0 permanent=0
backfilled=0 backfill_failed=0 wav=0 wav_failed=2
```

was noise from a single web-music task whose two companion WAV conversions
(`ok` + `alt`) had permanently failed upstream. The sweep re-counted those two
dead conversions every pass, and the 6-hour alert cooldown made it look like a
chronic outage.

Root cause of the two failures (read from the musicapi `jobs` table on
production): the bundled `ffmpeg-static` binary could not be spawned —
`ENOENT` (missing) then `EACCES` (not executable). Over 30 days musicapi WAV jobs
were `43 complete / 2 error`, so the conversion service itself was healthy; a
deploy had left the binary absent/non-executable.

## Product impact

- The B2 sweep no longer retries or pages on WAV variants already marked
  `wav_status_* = 'failed'` (terminal upstream failure).
- Retrying a WAV download for a track with a terminal failure now submits a
  **fresh** conversion instead of re-polling the dead upstream job, so affected
  tracks can recover once the provider is healthy again.
- A musicapi deploy now fails loudly if the `ffmpeg-static` binary is missing,
  and repairs its execute bit if present — preventing the failure that caused
  this in the first place.

## Technical impact

- `platform_api/repositories/streaming_repo.py` — `list_web_music_tasks_missing_wav`
  now excludes `COALESCE(wav_status_ok/alt, '') = 'failed'` in both the selected
  `missing_wav_*` flags and the `WHERE` clause, matching the eligibility check in
  `StreamingUploadService._asset_recovery_worker`.
- `platform_api/services/web_music_service.py` — `_download_wav_inner` no longer
  keeps a terminal `wav_task_id` ("re-poll the same job"); it clears
  `wav_task_id_*`/`wav_url_*`, sets `wav_status_* = 'pending'`, and falls through
  to submit a new conversion.
- `platform_api/services/streaming_upload_service.py` — `_upload_web_music_wav`
  defensively clears a stale `wav_task_id_*` when `wav_status_* = 'failed'` so a
  submit path can create a fresh job.
- `scripts/deploy/camxora-musicapi-remote.sh` — after `npm ci`, verify
  `node_modules/ffmpeg-static/ffmpeg` exists (else `exit 1`) and `chmod +x` it.
- `scripts/deploy/diag_prod_b2_wav_backfill.py` — new read-only prod diagnostic
  (missing-WAV rows, wav_status distribution, API + musicapi logs, job errors).

No schema change.

## Migrating already-failed tracks

The query exclusion stops the noise but does not by itself re-create B2 WAVs for
tracks already marked failed. After the ffmpeg binary is repaired, a user
re-download of the WAV re-submits a fresh conversion; the subsequent sweep then
uploads the resulting WAV to B2. Clearing `wav_status_*`/`wav_task_id_*` for the
affected rows (or adding a re-arm admin action) is a possible follow-up.

## Deploy

- Sandbox first (platform_api sync). No migration.
- Production only on explicit request; `ffmpeg-static` repair on the musicapi
  host is independent of the code deploy.

## Tests

- `python -m pytest platform_api/tests -k "web_music or streaming"` → 148 passed.
- New: `test_missing_wav_query_skips_permanently_failed_conversions`,
  `test_download_wav_resubmits_after_terminal_failure`.
