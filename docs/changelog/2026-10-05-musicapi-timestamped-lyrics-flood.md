# musicapi: stop the `timestamped_lyrics_detail` flood, fix the LRC aligner OOM loop, and deliver real timings

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

A second defect sat on top of it: `platform_api` (the real caller) reads
`data.alignedWords` from the **immediate** `POST /api/v1/generate/get-timestamped-lyrics`
response and never polls a task, but musicapi answered with an async
`{data:{taskId}}`. So even a healthy aligner could never deliver timings to it.

## Product impact

- Detail polling no longer floods the usage log: a **usable (timed) result is
  reused for good** — a clip's alignment can't change — so once a clip is aligned
  it costs one row ever, not one per poll. In-flight jobs are coalesced, and an
  empty/failed result is only re-attempted after a retry window (default 15 min).
- The aligner stops OOM-restarting, so the timestamped-lyrics getters can
  actually return timed LRC instead of silently falling back to plain lyrics.
- **Timings now actually reach the caller.** The getters answer synchronously in
  sunoapi.org's shape — `{code,msg,data:{taskId,aligned,lrc,alignedWords}}` — so
  `platform_api` (and the desktop LRC fetch) receive real `alignedWords` on the
  first call instead of an unusable task id.
- Response change: `/me/lyrics/:id` and `/v1/lyrics/:id` previously returned
  `{job_id,status}` (create-a-task); they now return the synchronous envelope
  above, matching their documented "Get Timestamped Lyrics" contract. No in-repo
  consumer read the old shape.

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
  - The getters now answer synchronously: they reuse a cached/in-flight job or
    create and run one inline, bounded by `LYRICS_SYNC_WAIT_MS` (default 25s,
    under the caller's ~30s HTTP timeout). On timeout the job keeps running and
    the next call is served from the cache. `sunoAlignedWords()` rebuilds the
    aligner's line-level output into sunoapi.org's newline-terminated
    `alignedWords` so the caller's `aligned_words_to_lrc` produces LRC.
  - The four routes (`/me/lyrics/:id`, `/v1/lyrics/:id`, `GET /api/v1/lyrics/:id`,
    `POST /api/v1/generate/get-timestamped-lyrics`) share the dedup + sync paths;
    the charge only happens when no reusable job exists, so a reused request is
    never billed twice.

No schema change.

## Files touched

- `musicapi/lrc-service/server.py`
- `musicapi/lrc-service/README.md`
- `musicapi/src/server.ts`
- `scripts/deploy/sync_musicapi_sandbox.py` (`--api-only` + sentinel return)
- `scripts/deploy/camxora-musicapi-remote.sh` (`MUSICAPI_SKIP_FRONTEND`)
- `docs/changelog/2026-10-05-musicapi-timestamped-lyrics-flood.md` (this file)

## Migration / deploy

- No migration. Deploy via the normal sandbox-first chain; the LRC sidecar is
  part of the `musicapi` deploy and restarts with the new unit.
- Optional env knobs: `LRC_MAX_INFLIGHT`, `LRC_QUEUE_WAIT_S`, `LYRICS_REUSE_TTL_MS`,
  `LYRICS_SYNC_WAIT_MS`.
- Backend-only changes can deploy fast with
  `python scripts/deploy/sync_musicapi_sandbox.py --api-only` (skips both Next.js
  builds via `MUSICAPI_SKIP_FRONTEND=1`). The deploy client also now returns as
  soon as the installer prints its success sentinel, instead of blocking on a
  lingering SSH channel.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `python lrc-service/test_align.py` → all checks pass.
- `python -m py_compile lrc-service/server.py` → clean.
- Read-only prod diagnostics confirmed the before-state (counts, one caller,
  27 distinct clips, 4590 `aligned:false`, OOM-kill journal lines).

## Follow-ups

- Verify on a **vocal** clip that `data.alignedWords` is non-empty end-to-end
  (the only sandbox clips to date are instrumental, so shape was verified but not
  a real alignment).
- Consider applying the same reuse/sync rule to the other `*_detail` routes if
  their pollers show up in the ledger.
