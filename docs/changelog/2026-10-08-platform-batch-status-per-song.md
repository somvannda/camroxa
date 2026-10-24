# Batch status counts songs, not Suno task rows

## Summary

A batch whose songs all completed could still sit at **`partial`** forever.
`batch_repo.get_batch_status_counters` counted **`suno_tasks` rows** by status and
`batch_service._derive_batch_status` compared those raw counts against the song
counts. A song can have several `suno_tasks` rows — a superseded failure from an
earlier attempt, or a duplicate success — so the equality broke:

- a leftover `failed` row made `suno_failed > 0` → `partial`; or
- extra `success` rows made `suno_completed (16) != drafts_completed (15)` →
  not `completed` → `partial`.

In production this left **19 batches** at `partial` with **every song
`suno_success`** (e.g. `sophay` batches with 15 songs OK but 16–21 stale failed
rows; `edmbass1`/`somvannda` batches with duplicate success rows). User-visible:
the desktop showed music pipelines stuck at 9/10 while everything was delivered.

## Product impact

- A batch is now `completed` as soon as all its songs are `suno_success`,
  regardless of historical/superseded task rows.
- No more phantom `partial` batches or "missing track" impressions after a retry.
- No user-visible change for genuinely in-progress or failed batches.

## Technical impact

- `platform_api/repositories/batch_repo.py` — `get_batch_status_counters`:
  - `suno_submitted` = `COUNT(DISTINCT song_id)` for the batch's `suno_tasks`
    (was `SUM` of per-status task counts).
  - `suno_completed` = `songs.status = 'suno_success'` count.
  - `suno_failed` = `songs.status = 'suno_failed'` count.
  - Removed the per-status `suno_tasks` aggregation; the song is the source of
    truth for a generation's terminal state.
- `_derive_batch_status` is unchanged — it now receives coherent per-song
  counters.
- `platform_api/tests/test_batch_repo_status_counters.py` (new) — the counter is
  per song and `suno_submitted` is a DISTINCT song count; failed songs counted
  per song.
- `platform_api/tests/test_batch_service.py` — a derive test for "all songs
  success → completed".

No schema change. `platform_api` only. Existing `partial` batches flip to
`completed` on the next `refresh_batch_status` (history view / pending-downloads).

## Files touched

- `platform_api/repositories/batch_repo.py`
- `platform_api/tests/test_batch_repo_status_counters.py` (new)
- `platform_api/tests/test_batch_service.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-10-08-platform-batch-status-per-song.md` (this file)

## Migration / deploy

- No migration. Deploy `platform_api`, restart `camxora-api` and the
  `camxora-worker-*` services. Existing stale batches self-heal on their next
  status refresh.

## Tests

- Full `platform_api` suite: **3198 passed** (adds 3 tests).

## Follow-ups

- Superseded `failed` `suno_tasks` rows are retained as attempt/COGS history and
  are no longer read for status. If the table growth matters, consider pruning
  old superseded rows in a separate task.
