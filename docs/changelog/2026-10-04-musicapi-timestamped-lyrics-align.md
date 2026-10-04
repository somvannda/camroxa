# musicapi timestamped lyrics → self-hosted LRC alignment

Closed the last known product gap: `musicapi`'s timestamped-lyrics endpoints
(`GET /me/lyrics/:id`, `GET /v1/lyrics/:id`,
`POST /api/v1/generate/get-timestamped-lyrics`) were wired and credit-billed but
returned `aligned_words: []` and no LRC, because Suno's **direct** API
(`studio-api-prod.suno.com`) exposes lyric text only.

## What changed

- **New microservice** `musicapi/lrc-service/` — a localhost faster-whisper
  service. `POST /align {url|audio_b64, lyrics}` transcribes the clip with word
  timestamps and snaps the recognised words onto the known lyric lines, returning
  `lines`, `words`, and line-level `lrc`. Pure alignment logic is model-free and
  unit-tested (`test_align.py`). Mirrors the `midi-service` pattern (uv venv,
  systemd, no Docker).
- **`musicapi/src/lrc.ts`** — ports `platform_api/services/suno_lrc.py`
  (word/line → LRC, LRC → SRT, payload parsing); covered by `npm run test:lrc`
  (25 checks).
- **Wiring** — `server.ts` runs a server-side alignment job for
  `timestamped_lyrics_detail` and returns `aligned`, `lrc`, `lrc_format`,
  `aligned_lines`, `aligned_words`. Billing and routes are unchanged.
- **Graceful fallback** — if the service is disabled/unreachable or storage is
  unavailable, the job returns plain lyrics with `aligned: false`; timing is
  never fabricated. `LRC_SERVICE_ENABLED=0` forces the old path.
- **Deploy** — `camxora-musicapi-lrc.service` + `lrc-service/provision.sh`,
  provisioned best-effort in the musicapi remote deploy (model pre-downloaded
  once).

## Still to verify (host)

- `bash musicapi/lrc-service/provision.sh` then `curl localhost:4011/health`.
- Live E2E: generate a clip → `GET /me/lyrics/:id` → confirm `[mm:ss.xx]` tags.
