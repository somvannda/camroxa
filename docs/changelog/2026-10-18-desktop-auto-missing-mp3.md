# Desktop: automatic recovery of missing MP3s

**Date:** 2026-10-18
**Surfaces:** `camxora_python` (desktop)
**Status:** implemented (tests pass); desktop build + release pending

## Summary

The desktop no longer requires a manual right-click to re-fetch MP3s that are
missing **on this PC**. After the account-wide pending-download sync was fixed
server-side (`docs/changelog/2026-10-02-pending-downloads-poll-latency.md`), the
poll and downloads resumed — but tracks the **server** already recorded as
downloaded (`downloaded_ok` / `pipeline_complete`) and whose file is absent
locally were still never re-fetched automatically. The Progress page now runs
the same recovery the right-click action does, one channel at a time.

## Problem

`GET /music/downloads/pending` is driven purely by server state: it only returns
rows with `COALESCE(downloaded_ok, false) = false` and
`COALESCE(batch_channel_assets.pipeline_complete, false) = false`
(`platform_api/repositories/batch_repo.py`). `downloaded_*` is **account-wide,
not per-device**.

So any track whose file is missing on this machine — deleted, moved, or pulled
on another device — is invisible to the auto sync. The only way to recover it is
the per-batch `POST /music/downloads/batch-redownload-plan` path, which
deliberately ignores `downloaded_*` and re-derives from real disk state. Until
now that path had exactly one entry point: the Progress row right-click
(**Download missing MP3s**). Everything else only *detected* the gap and told
the user to act:

- `features/video/services/pipeline_automation_service.py` →
  `"Cannot regenerate MP4s — download missing MP3s first"`
- `features/progress/lib/continue_progress.py` →
  `"Download missing MP3s before regenerating MP4s"`

Observed in production: after the poll fix deployed, a user still had to
right-click each batch in turn (7 manual runs in one session).

## Product impact

- A run whose MP3s are missing on this PC heals itself while the Progress page
  is open — no right-click needed.
- One channel is recovered per 60s tick; a channel is not retried for 10 minutes
  after an attempt, so a track with no fetchable URL cannot loop.
- Manual right-click behaviour is unchanged (same worker, same notices).

## Technical impact

- `shared/lib/missing_mp3.py` — new pure selector
  `pick_auto_missing_mp3_target(rows, attempted_at=…, now=…, cooldown_s=…)`
  returning the first `AutoMissingMp3Target` (batch/profile/role/run_dir/
  missing_n) whose role MP3s are missing on disk and not recently attempted.
  `missing_counter` is injectable, so the logic is unit-tested without disk I/O.
- `features/progress/views/progress_view.py`:
  - New 60s `QTimer` + per-channel attempt map (`_auto_missing_mp3_attempted`,
    600s cooldown).
  - `_maybe_auto_download_missing_mp3s()` guards on: rows ever loaded, page
    active, no load/missing-MP3/run-folder-recovery worker already running, and
    app not quitting.
  - Worker construction extracted to `_start_missing_mp3_download(...)`, shared
    by the manual and automatic paths — the manual path is otherwise untouched.
- No API, schema, or migration change.

## Files touched

- `camxora_python/shared/lib/missing_mp3.py`
- `camxora_python/features/progress/views/progress_view.py`
- `camxora_python/tests/test_missing_mp3_auto.py` (new)
- `CHANGELOG.md` (desktop)
- `docs/changelog/2026-10-18-desktop-auto-missing-mp3.md` (this file)

## Migration / deploy

- Desktop-only: ships in the next `camxora_python` build. No server deploy.
- The server-side complement already shipped (PR #394, deployed 2026-10-18).

## Tests

- `python -m pytest tests/test_missing_mp3_auto.py tests/test_missing_mp3.py -q`
  → 14 passed
- `python -m pytest tests/test_progress_view.py tests/test_missing_mp3_download_worker.py -q`
  → 25 passed

## Follow-ups

- Deeper fix (deferred): per-device scoping so `/music/downloads/pending` can
  return disk-missing tracks even when `downloaded_ok = true` for that device.
  See `docs/changelog/2026-07-31-desktop-startup-freeze-hardening.md`.
- Consider surfacing an in-app summary when the automatic recovery downloads
  tracks, so the user knows it happened without reading the log.
