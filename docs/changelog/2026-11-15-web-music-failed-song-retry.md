# Web Create: a failed song can be retried, not just deleted

**Date:** 2026-11-15
**Surface:** `platform_api` (web music) + `music_web`
**Branch:** `feat/web-music-failed-song-retry`

## Summary

A failed Simple-mode song used to leave one thing behind: a red row saying *"This
song could not be written. Credits were refunded."* with a **Delete** button. The
desktop Create page has offered "Retry this song" for years; the web offered only
removal, so the listener had to re-create the song by hand — which re-runs the
whole batch and can re-charge the songs that already succeeded.

Two gaps made that unavoidable:

- the description that produced the song (`prompt`, `theme`, `structure`, `title`)
  lived **only in the job payload**, so once the row failed nothing could rebuild
  it;
- a *transient* lyrics failure was refunded on the first attempt, marking the row
  failed even though the job queue still had two attempts left.

## Product impact

- A failed song keeps its **one row** (never two: a failed task has no
  ok/alt clips), now with **Retry** next to **Delete**.
- Retry is an ordinary **new, charged** create — the button says so, and asks for
  confirmation with the cost, because the failed attempt was already refunded.
- A transient provider failure no longer costs the listener the song: the row
  stays queued and the job retries. The row only fails when the provider's answer
  cannot change (a refused prompt) or the attempts are exhausted.
- Failed rows age out of the Create list after **7 days** instead of piling up
  forever. Nothing is deleted: the row (and the refund it records) stays in the
  database.

## Technical impact

- Migration **204**: `suno_tasks.lyrics_brief jsonb` (nullable). Advanced-mode
  songs, sounds and pre-existing rows have no brief.
- `_enqueue_web_generate()` stores the brief on the row as well as in the job
  payload.
- `retry_failed_generation()` (`POST /api/v3/web-music/generations/{id}/retry`,
  `202`) validates ownership + `status='failed'` + not trashed + a saved brief,
  honours the queue cap, charges, flips the row back to `pending` with
  `error_message`/`external_task_id`/audio cleared, and re-enqueues with the
  stored brief. If the charge or the enqueue fails, the refund runs and the row
  returns to `failed` rather than looking queued forever.
- `write_queued_lyrics()` takes `final_attempt`; the worker passes
  `job.attempts >= job.max_attempts`. A retryable failure before the last attempt
  propagates without a refund or a failed row.
- `list_generations()` hides `failed` rows older than 7 days from both the count
  and the page query.
- `music_web`: `retryWebMusicGeneration()` plus a Retry button (with cost) on the
  failed card.

## Migration / deploy

```
python scripts/deploy/sync_platform_api_production.py   # applies migration 204 on API start
python scripts/deploy/sync_music_web_production.py
```

## Tests

- `platform_api/tests/test_web_music_retry.py` (7): requeues the saved brief and
  charges; refuses a song that did not fail, another user's song, a song without a
  brief and a full queue; refunds when the row was already claimed by another tab;
  refunds and restores `failed` when the enqueue fails.
- `platform_api/tests/test_web_music_diversity.py` (+2): a retryable failure with
  attempts left neither refunds nor marks the row failed; a content refusal does.
- Full suite: 3471 passed (2 deselected, Windows-only media paths).
- `music_web`: `npm run build` (Next + TypeScript) clean.

## Follow-ups

- The `camxora.com` CreateStudio (local-only app) has no failed-song rendering and
  gets no Retry button yet.
- Advanced-mode songs and sounds cannot be retried from the row (no brief); the
  API tells the client to use the form instead.
