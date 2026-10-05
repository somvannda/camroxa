# musicapi: stop the `timestamped_lyrics_detail` flood + LRC aligner OOM loop

## Summary

Production `usage_logs` had **4,594 `timestamped_lyrics_detail` rows in 3 days
(4,591 in the last 24h)** — the top endpoint by volume, ~10–50 rows/minute. One
API key (`camxora desktop app`) accounted for 4,495 of them, but across only
**27 distinct clip IDs**: the same songs were requested 64–706 times each. Every
request minted a fresh job + `usage_logs` row, and **4,590 / 4,591 results came
back `aligned:false` with an empty `lrc`**, so the caller retried forever.

The empty results traced to the `camxora-musicapi-lrc` sidecar being in an OOM
crash loop (`failed with result 'oom-kill'`, restart counter had reached 40,
RSS peaking 2.3–2.6 GB against `MemoryMax=3G`), logging
`[lrc] align request failed …: fetch failed` on every restart.

## Product impact

- Detail polling no longer floods the usage log: a **usable (timed) result is
  reused for good** — a clip's alignment can't change — so once a clip is aligned
  it costs one row ever, not one per poll. In-flight jobs are coalesced, and an
  empty/failed result is only re-attempted after a retry window (default 15 min).
- The aligner stops OOM-restarting, so `/me/lyrics/:id`, `/v1/lyrics/:id`, and
  `POST /api/v1/generate/get-timestamped-lyrics` can actually return timed LRC
  again instead of silently falling back to plain lyrics.
- Webhook callers that supply a `callBackUrl` are unaffected: reuse only applies
  when the callback matches (or neither is set).

## Technical impact

- `musicapi/lrc-service/server.py`
  - `load_model()` is now guarded by a dedicated `MODEL_LOAD_LOCK` (double
    checked). Previously a burst of `/align` calls during a cold start each built
    their own `WhisperModel`, which is what spiked RSS past `MemoryMax` and made
    the unit OOM on every restart.
  - `MODEL_NAME(...)` is constructed with `num_workers=1`.
  - `ThreadingHTTPServer` is no longer unbounded: a `BoundedSemaphore`
    (`LRC_MAX_INFLIGHT`, default 8) gates `/align` before the body is read, and
    over-cap requests get `503 {"ok":false,"error":"busy"}` after
    `LRC_QUEUE_WAIT_S` (default 30s) so callers fall back instead of piling up.
- `musicapi/src/server.ts`
  - New `reusableLyricsJob(clipId, userId)` collapses repeated
    `timestamped_lyrics_detail` submits onto one job per clip: a completed
    `aligned:true` result with a non-empty `lrc` is reused indefinitely (DB is the
    durable cache), an in-flight job is reused so concurrent calls don't duplicate
    work, and an empty/failed row is reused only within `LYRICS_REUSE_TTL_MS`
    (default 15 min) so a broken aligner can recover. Wired into
    `/me/lyrics/:id`, `/v1/lyrics/:id`, `GET /api/v1/lyrics/:id`, and
    `POST /api/v1/generate/get-timestamped-lyrics`, before the credit charge so a
    reused request is never billed twice.
  - The `POST …/get-timestamped-lyrics` route only reuses when the requested
    callback matches the existing job's (or both are absent).

No schema change.

## Files touched

- `musicapi/lrc-service/server.py`
- `musicapi/lrc-service/README.md`
- `musicapi/src/server.ts`
- `docs/changelog/2026-10-05-musicapi-timestamped-lyrics-flood.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain; the LRC sidecar is
  part of the `musicapi` deploy and restarts with the new unit.
- Optional env knobs: `LRC_MAX_INFLIGHT`, `LRC_QUEUE_WAIT_S`, `LYRICS_REUSE_TTL_MS`.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `python lrc-service/test_align.py` → all checks pass.
- `python -m py_compile lrc-service/server.py` → clean.
- Read-only prod diagnostics confirmed the before-state (counts, one caller,
  27 distinct clips, 4590 `aligned:false`, OOM-kill journal lines).

## Follow-ups

- **Response-shape mismatch (root of the retries):** `platform_api`
  (`suno_api_base_url=https://musicapi.camxora.com`) calls
  `POST /api/v1/generate/get-timestamped-lyrics` and expects sunoapi.org's
  synchronous `data.alignedWords`; musicapi returns an async `{data:{taskId}}`,
  so the platform never sees timings even when alignment succeeds. Either make
  musicapi's endpoint answer synchronously or teach the platform to poll our
  task id.
- Consider applying the same reuse rule to the other `*_detail` routes if their
  pollers show up in the ledger.
