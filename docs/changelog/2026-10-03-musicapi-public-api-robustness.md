# musicapi: harden public API id handling (task 404, upload-status timeout)

## Summary

Two robustness defects on the customer-facing (sellable) `musicapi` API surface,
found while validating first-customer readiness, are fixed:

1. **Malformed task id returned HTTP 500.** `GET /v1/task/nope` and every
   `GET /api/v1/*/record-info?taskId=nope` passed the raw id straight into a
   Postgres `uuid` column, so the cast failed and Fastify surfaced a 500.
2. **Upload-status endpoints blocked for up to 60s.** `/v1/upload/status/:id`,
   `/api/v1/upload/status/:id` and `/me/upload/status/:id` reused the
   polling client method `getAudioUploadStatus()` (default `timeoutMs = 60_000`),
   so a bad/typo id held the HTTP request open for a full minute before 502.

## Product impact

- A mistyped or stale task id now returns a clean `404` instead of a `500`.
- A status poll against a bad upload id returns `502` in ~1.6s instead of hanging
  for 60s — status endpoints report current state and let the client re-poll.
- No happy-path behavior change; generation, polling and billing are unaffected.

## Technical impact

- `musicapi/src/server.ts`
  - `getJob()` now rejects non-UUID ids with `UUID_RE` (already defined in the
    file) and returns `null`, so the existing `404` path in every caller runs.
    Covers `/v1/task/:id` and all 17 `/api/v1/*/record-info` aliases.
  - The three upload-status handlers call the new non-polling client method.
- `musicapi/src/client.ts`
  - Added `fetchAudioUploadStatus()` — one Suno request, no retry loop, throws on
    a non-ok response. `getAudioUploadStatus()` (polling) is retained for the
    upload flow (`uploadAudio`), which genuinely needs to wait for processing.

No schema change, no migration.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/src/client.ts`
- `docs/changelog/2026-10-03-musicapi-public-api-robustness.md`

## Migration / deploy

1. Deploy the `musicapi` core API; both changes are in the Fastify server.
2. No `web-user` / `web-admin` rebuild and no migration.

## Tests

- `musicapi`: `npx tsc --noEmit` → clean.
- `musicapi`: `npm run test:contract` → 37/37 sunoapi.org paths present.
- Live on an isolated `:4004` build:
  - `/v1/task/nope` → `404` (was `500`).
  - `/api/v1/generate/record-info?taskId=nope` → `404` (was `500`).
  - `/v1/upload/status/nope` → `502 in 1.6s` (was a 60s hang).
- CI on PR #213: MusicAPI typecheck + build, MusicAPI smoke gate, and the other
  PR checks all green.

## Follow-ups

- Only one active Suno account is in the pool; add a second for redundancy.
- Recovery / MIDI / MP4 / voice / stems / WAV endpoints remain unproven in the
  job history — keep them out of the first-customer offer until each has a green
  live run.
- Docs marketing claims ("99.9% uptime", "24/7 support", "100%") need a product
  decision.
