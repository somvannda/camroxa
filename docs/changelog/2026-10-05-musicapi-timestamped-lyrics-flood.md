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
- **Timings now reach the caller.** The getters answer in sunoapi.org's shape —
  `{code,msg,data:{taskId,aligned,lrc,alignedWords}}` — instead of an unusable
  task id, so `platform_api`'s immediate read of `data.alignedWords` works.
  Alignment runs in the background: CPU faster-whisper takes ~1 minute per track
  (longer than any HTTP timeout), so the first call(s) return an empty list and a
  later call is served the real timings from the cache. Each clip is aligned once.
- Response change: `/me/lyrics/:id` and `/v1/lyrics/:id` previously returned
  `{job_id,status}` (create-a-task); they now return the envelope above. No
  in-repo consumer read the old shape.

## Technical impact

- `musicapi/lrc-service/server.py`
  - **VAD is off by default** (`LRC_VAD` default `0`). Silero VAD is speech-tuned
    and dropped nearly all *sung* vocals — it transcribed only 7 words of a
    2-minute song, so `snap_to_lyrics` matched almost nothing and stamped every
    lyric line with one timestamp. `transcribe_words()` now also retries without
    VAD when an enabled-VAD transcript is implausibly sparse for the audio length.
  - `load_model()` is now guarded by a dedicated `MODEL_LOAD_LOCK` (double
    checked). Previously a burst of `/align` calls during a cold start each built
    their own `WhisperModel`, which is what spiked RSS past `MemoryMax` and made
    the unit OOM on every restart.
  - `MODEL_NAME(...)` is constructed with `num_workers=1`.
  - `ThreadingHTTPServer` is no longer unbounded: a `BoundedSemaphore`
    (`LRC_MAX_INFLIGHT`, default 8) gates `/align` before the body is read, and
    over-cap requests get `503 {"ok":false,"error":"busy"}` after
    `LRC_QUEUE_WAIT_S` (default 10s) so callers fall back instead of piling up.
  - The accept backlog is widened (`request_queue_size=128`, daemon threads) so a
    burst no longer overflows the default backlog and surfaces as Node
    `fetch failed` (connection refused) instead of a clean 503.
- `musicapi/src/server.ts`
  - `alignLyrics()` skips clips whose lyric text has no real words
    (`[Instrumental]`, section-only prompts). Transcribing them wasted ~a minute
    of CPU each and starved genuine vocal requests.
  - Alignments run through a small in-process gate (`LRC_MAX_CONCURRENT`, default
    2) with up to 3 attempts. Firing the whole clip batch at the single-CPU
    sidecar at once overflowed it (503 / connection resets), and every failure
    was cached `aligned:false` and re-queued — a retry storm that kept the flood
    alive even after dedup. The gate keeps the sidecar fed without thrashing.
  - `finalizeJob()` no longer re-ingests the clip's media for a
    `timestamped_lyrics_detail` job (the originating music job already stored
    it); the redundant download/decrypt/upload was slow and held a Suno slot.
  - New `reusableLyricsJob(clipId, userId)` collapses repeated
    `timestamped_lyrics_detail` submits onto one job per clip: a completed
    `aligned:true` result with a non-empty `lrc` is reused indefinitely (DB is the
    durable cache), an in-flight job is reused so concurrent calls don't duplicate
    work, and an empty/failed row is reused only within `LYRICS_REUSE_TTL_MS`
    (default 15 min) so a broken aligner can recover. Wired into
    `/me/lyrics/:id`, `/v1/lyrics/:id`, `GET /api/v1/lyrics/:id`, and
    `POST /api/v1/generate/get-timestamped-lyrics`, before the credit charge so a
    reused request is never billed twice.
  - The getters answer in sunoapi.org's shape without holding the request for the
    (slow) alignment: they reuse a cached/in-flight job or start one in the
    background, wait only `LYRICS_SYNC_WAIT_MS` (default 3s grace, to catch a warm
    cache), then return whatever is cached. `sunoAlignedWords()` rebuilds the
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
