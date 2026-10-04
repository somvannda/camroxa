# Tasks — musicapi Timestamped Lyrics / LRC

## Core (testable locally)
- [x] T1 `src/lrc.ts` — port `suno_lrc.py` (word/line → LRC, LRC → SRT, payload parse).
- [x] T2 `scripts/test-lrc.ts` + `npm run test:lrc` — 25 checks, all pass.
- [x] T3 `lrc-service/server.py` — `/health` + `/align` (faster-whisper + snap).
- [x] T4 `lrc-service/test_align.py` — pure-logic checks, no model required.

## Wiring
- [x] T5 `server.ts` — `LRC_SERVICE_URL` / `LRC_SERVICE_ENABLED`, `alignLyrics`,
      `runTimestampedLyricsJob`, `runDescribedJob` intercept.
- [x] T6 Fallback path preserved (`JOB_OPS.timestamped_lyrics_detail`) with
      `aligned: false` when disabled/unavailable.
- [x] T7 Update `client.ts` TODO comments to point at the implemented pipeline.

## Deploy / docs
- [x] T8 `lrc-service/provision.sh` + `README.md`.
- [x] T9 `camxora-musicapi-lrc.service`; registered in
      `install_musicapi_services.sh`; provisioned in
      `camxora-musicapi-remote.sh` (best-effort).
- [x] T10 Spec + parity-checklist note.

## Verify
- [x] V1 `npm run typecheck` → 0 errors.
- [x] V2 `npm run test:lrc` → pass.
- [x] V3 `python lrc-service/test_align.py` → pass.
- [ ] V4 Host smoke: `curl localhost:4011/health` after provisioning.
- [ ] V5 Host E2E: generate a clip → `GET /me/lyrics/:id` returns LRC.
