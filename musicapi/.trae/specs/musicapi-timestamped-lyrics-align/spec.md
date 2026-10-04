# musicapi Timestamped Lyrics / LRC (self-hosted alignment) — Spec

## Overview
- **Summary**: Make `musicapi`'s timestamped-lyrics endpoints return real
  line-level LRC by computing word/line alignment ourselves, without the
  sunoapi.org reseller the legacy `platform_api` used.
- **Purpose**: Close the one known product gap: `/me/lyrics/:id`,
  `/v1/lyrics/:id`, and `POST /api/v1/generate/get-timestamped-lyrics` existed
  and were credit-billed but returned `aligned_words: []` and empty `lrc`,
  because Suno's **direct** API exposes lyric text only.
- **Target users**: API consumers + the streaming/desktop clients that
  karaoke-scroll only when real LRC is present.

## Background
- `musicapi` talks directly to Suno (`studio-api-prod.suno.com`); the clip
  record carries lyric text in `metadata.prompt`, no timing.
- The legacy `platform_api` got timings from the sunoapi.org reseller
  (`POST /api/v1/generate/get-timestamped-lyrics` → `alignedWords`) and already
  has the LRC conversion (`platform_api/services/suno_lrc.py`).
- `musicapi/midi-service` established the accepted pattern for filling a Suno
  API gap locally: a localhost Python sidecar, systemd + `uv`, no Docker.

## Design
1. **LRC microservice** — `musicapi/lrc-service/` (Python, faster-whisper):
   - `POST /align` takes the clip audio (URL or base64) + known lyric text,
     transcribes with word timestamps, snaps recognised words onto lyric lines
     with monotonic sequence matching, and returns `lines`, `words`, `lrc`.
   - Pure logic (`tokenize`, `snap_to_lyrics`, `interpolate_nones`, `build_lrc`)
     is model-free and unit-tested (`test_align.py`).
   - CPU-friendly (`int8`, default `small` model); model loaded once per process.
2. **TS conversion** — `musicapi/src/lrc.ts` ports `suno_lrc.py`
   (`alignedWordsToLrc`, `alignedLinesToLrc`, `parseAlignedWordsPayload`,
   `looksLikeLrc`, `lrcToSrt`), unit-tested by `scripts/test-lrc.ts`.
3. **Wiring** — `server.ts` intercepts the `timestamped_lyrics_detail`
   descriptor in `runDescribedJob` and runs `runTimestampedLyricsJob`, which
   reads the clip's lyric text, aligns its audio via `alignLyrics`, and stores
   `{ ...clip, lyrics, aligned, lrc, lrc_format, aligned_lines, aligned_words }`.
   Every existing route keeps its billing (`pricing.timestamped_lyrics_detail`).
4. **Graceful fallback** — when the service is disabled/unreachable or media
   storage is unavailable, the job returns plain lyrics with `aligned: false`
   and the original `JOB_OPS` path still answers (`LRC_SERVICE_ENABLED=0`).
   Timing is never fabricated.
5. **Deploy** — systemd unit `camxora-musicapi-lrc.service`, `provision.sh`
   (venv + model pre-download), and best-effort wiring in
   `scripts/deploy/camxora-musicapi-remote.sh` +
   `scripts/deploy/systemd/install_musicapi_services.sh`.

## Non-Goals
- No reseller dependency (rejected option B).
- No estimated/derived timing (rejected option C — the streaming UI removed it).
- No change to billing architecture or auth.
- True phoneme-level forced alignment (WhisperX/wav2vec2) is a future upgrade
  behind the same `/align` contract.

## Acceptance Criteria
- **AC-1**: `npm run test:lrc` passes (conversion parity with `suno_lrc.py`).
- **AC-2**: `python lrc-service/test_align.py` passes (no model required).
- **AC-3**: `npm run typecheck` exits 0.
- **AC-4**: With the service up, `/me/lyrics/:id` (and the parity routes) return
  `lrc` containing `[mm:ss.xx]` tags and non-empty `aligned_words`.
- **AC-5**: With the service down / `LRC_SERVICE_ENABLED=0`, the same routes
  still settle with `aligned: false`, plain `lyrics`, and no fake timings.
- **AC-6**: Deploy provisions the venv/model only when missing and never fails
  the deploy if provisioning fails.

## Open Questions
- [ ] Model default: `small` balances CPU latency vs accuracy on sung vocals.
      Confirm on the API host; bump to `medium`/`large-v3` if needed.
- [ ] Should section-marker lines (`[Verse]`) be emitted as timed LRC lines or
      dropped? Currently kept (matches legacy behaviour), time borrowed from the
      next matched line.
- [ ] Expose SRT from `subtitle_detail` using `lrcToSrt` (not wired yet).
