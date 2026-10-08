# Version 2 no longer stranded by a first-clip success

## Summary

Follow-up to the [2026-10-07 both-versions fix](./2026-10-07-musicapi-both-versions-complete.md).
The prior change stopped a **failed** generation from being reported as a success on
partial audio, but a **still-running** one could still be reported as success.

A `/generate` returns two Suno clips — rendered on `music.camxora.com` as Version 1
(`variant=ok`) and Version 2 (`variant=alt`). `musicapi` reports status `FIRST_SUCCESS`
as soon as the **first** clip is playable, and keeps that status while it finishes the
B2 ingest (decrypt + transcode + upload) of the second clip. During that window the
first clip already has a durable `audio_url` while the second does not.

`parse_suno_generate_poll` builds its URL list first and then returned `success` as soon
as **any** clip had an audio URL — *before* checking the upstream status. A poll that
landed in that window therefore marked the `platform_api` task `SUCCESS` with
`audio_url_alt` empty. Because the task was no longer `pending`/`running`,
`web_music_service._refresh_pending_from_suno` never polled it again, so Version 2 sat
on "Waiting"/"Loading…" forever while Version 1 played and downloaded normally.

## Product impact

- A normal generation now waits for the terminal `SUCCESS` before Version 1 or
  Version 2 is shown as ready, so **both** versions complete and download.
- No more permanently-spinning Version 2 with an empty `audio_url_alt`.

## Technical impact

- `platform_api/clients/suno_client.py` — `parse_suno_generate_poll` now returns
  `pending` when the upstream status is a **non-terminal** status
  (`PENDING` / `RUNNING` / `TEXT_SUCCESS` / `FIRST_SUCCESS`) even if one clip already
  has a URL. The guard is placed after the failure check and before the partial-audio
  success return, mirroring the existing failure-first rule.
- An **empty** status is intentionally left to the audio-URL branch, so providers that
  omit `status` but return audio still resolve as success (the empty string is itself a
  member of the "pending" status set).
- A terminal `SUCCESS` is unaffected: it keeps mapping to `success` with both
  `audio_url_ok` and `audio_url_alt`.
- `platform_api/tests/test_suno_status_messages.py` — regression tests for
  non-terminal-status-with-partial-audio (`pending`), terminal `SUCCESS` with both URLs
  (`success`), and empty-status-with-audio (`success`).

No schema change. This is a `platform_api`-only change; `musicapi` already sends the
correct `FIRST_SUCCESS` → `SUCCESS` progression.

## Files touched

- `platform_api/clients/suno_client.py`
- `platform_api/tests/test_suno_status_messages.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-10-08-version2-first-success-still-pending.md` (this file)

## Migration / deploy

- No migration.
- Requires a redeploy of **`platform_api`** only. Sandbox-first
  (`sync_platform_api_sandbox.py`), then the production platform_api deploy.

## Tests

- `platform_api/tests/test_suno_status_messages.py`: 20 passed.
- `test_suno_audio_resolver.py` + `test_generation_router.py` +
  `test_callback_auth_and_refund_guard.py`: 90 passed.

## Follow-ups

- Validate a fresh production generation: `parse_suno_generate_poll` should stay
  `pending` while `record-info` reports `FIRST_SUCCESS`, then resolve to `success` once
  it reports `SUCCESS` with both `audio_url_ok` and `audio_url_alt`.
- If a clip genuinely never finishes, `musicapi`'s `pollClips` timeout fails the job
  (refunded) and the poll reports `failed`, rather than hanging.
