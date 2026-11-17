# Generate: a job that gives up now fails its task and refunds

**Date:** 2026-11-17
**Surface:** `platform_api` (web music queue worker)
**Found by:** the W6 provider matrix — `docs/studio/reports/2026-11-17-provider-matrix-final.md`

## Summary

A `web_music_generate` job that exhausts its attempts left the task row exactly as it was:
`status = 'pending'`, `error_message = NULL`. The queue recorded the failure
(`job_queue.status = 'failed'`, `last_error` set) and stopped trying, but nothing propagated
to `suno_tasks`, so the listener saw a song that spun forever with no way to tell it had died,
and the credit reservation was never released.

It was found the hard way: three generations were queued against a worker whose Python path
pointed at a directory that no longer existed. Every job died with
`No module named 'platform_api.services.credit_service'`, and every task stayed `pending` —
which is indistinguishable, from the outside, from a slow provider queue. The remaining ten
credits of reservation sat on the row until the database was repaired by hand.

## Change

`platform_api/worker.py` now calls `_fail_dead_generate` whenever
`mark_failed_or_retry` reports `failed` (attempts exhausted), from both the exception and the
timeout branches. It marks the task `failed` with the same user-facing message the inline
failure uses — “Could not start this song. Credits were refunded.” — through
`WebMusicService._fail_queued_generate`, so the credit reservation is released the same way.

A job that is merely retried (`delayed`) is untouched: the task stays queued and the next
attempt proceeds normally.

## Verification

- `platform_api/tests/test_web_music_generate_queue.py` — two new tests: the propagation
  (task marked failed with the refund message, correct reservation id) and the guard that
  other job types are ignored.
- Repaired the three rows that exposed it by calling the same path: all three are now
  `failed` with the message, and the wallet returned from 20 to 448 as the reservations
  released.
- `platform_api/tests`: **3,510 passed, 0 failed**.

## Operational note (not a code change)

`platform_api/.env` does not define `PLATFORM_SUNO_API_BASE_URL`, so any process that submits
to the provider and is *not* started by `scripts/dev/studio-stack.ps1` silently falls back to
the production host. A hand-started worker pointed at production musicapi and every submit
came back `401` with a valid local key. Start the worker with
`PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003` and
`PLATFORM_SUNO_CALLBACK_BASE_URL=<public tunnel>`.
