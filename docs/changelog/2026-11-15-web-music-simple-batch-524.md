# Web Create: Simple-mode batches no longer die on HTTP 524

**Date:** 2026-11-15
**Surface:** `platform_api` (web music), `music_web`, `camxora.com`
**Branch:** `feat/web-song-diversity`

## Summary

Batching Simple-mode songs stopped after the first one:

> Created 1 of 5 songs, then stopped: Request failed (524)

`POST /api/v3/web-music/generate` wrote the song's lyrics **inside the request**.
Simple mode has no lyrics of its own, so the handler called Suno's lyrics task and
polled it (`generate_lyrics_blocking`: 30s submit timeout, 2s poll, up to
`_SUNO_LYRICS_MAX_WAIT_SECONDS = 120`). A single submit could legitimately hold
the response for ~150s.

Cloudflare terminates any origin response at ~100s and returns **524**. The
browser only fires the batch loop sequentially (`BATCH_SUBMIT_GAP_MS` apart), so
the first song usually finished inside the budget and every later one died at
the edge — with credits already reserved for the song that timed out.

nginx is not the culprit: every platform_api location already allows 300s
(`scripts/deploy/nginx-camxora-production.conf`).

## Product impact

- `POST /api/v3/web-music/generate` returns in well under a second in Simple
  mode, so 5- and 10-song batches no longer depend on an edge timeout.
- The song is queued immediately and its card appears with the provisional title;
  the worker fills in the real title and lyrics before submitting to Suno.
- A lyrics failure now refunds the song and says so, instead of surfacing a bare
  `524`.
- A 524 that still reaches a client no longer looks like "nothing happened": both
  create screens explain that the song may be queued and reload the library.

## Technical impact

- `platform_api/services/web_music_service.py`
  - `generate()` (Simple mode) no longer calls Suno. It queues a row with empty
    lyrics and a `lyrics_brief` (`prompt`, `theme`, `structure`, `title`) in the
    job payload, then returns.
  - New `write_queued_lyrics()` writes the title and lyrics through
    `_write_simple_song()` (content-pool seeds, avoid list, blocklist check) and
    persists them with `_persist_written_song()`. The worker calls it **before**
    taking the Suno submit lock, so a batch writes in parallel and only the
    provider submit stays serialized. It is idempotent: a retried job finds the
    lyrics already stored.
  - `_fail_queued_generate()` refunds and marks a queued song failed if the
    lyrics or the submit fail; pool seeds are released on the same path.
  - The row is inserted with a per-task placeholder `request_hash`, because
    `suno_tasks` is `UNIQUE(user_id, request_hash)` and Simple-mode songs have no
    lyrics to hash yet. The real hash replaces it once the lyrics exist; a
    collision keeps the placeholder instead of failing the song.
- `platform_api/clients/suno_client.py`: `_SUNO_LYRICS_MAX_WAIT_SECONDS`
  120 → 45, below the edge budget, so a slow lyrics task fails fast and
  retryably instead of becoming a 524.
- `platform_api/worker.py`: forwards `lyrics_brief` to the service.
- `music_web/src/components/create-page-client.tsx` and
  `camxora.com/components/CreateStudio.tsx`: detect a 524 / gateway timeout,
  explain it, and reload the library so a song the edge hid is never re-ordered.
- Tests: `platform_api/tests/test_web_music_diversity.py` now covers the split —
  one test asserts the POST queues without calling Suno, one asserts the worker
  writes the lyrics (theme, avoid list, pool title) before submitting.

## Related

- `platform_api/CHANGELOG.md` § `[2026-11-13] - Web Create: distinct titles and
  lyrics per batch` — the batch planner whose `theme`/`structure` now travel in
  the queued brief.
