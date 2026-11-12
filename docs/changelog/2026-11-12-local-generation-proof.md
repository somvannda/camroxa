# Local generations now complete through the real Suno provider

**Date:** 2026-11-12
**Branch:** `feat/studio-rebuild`
**Surfaces:** platform API, dev stack, docs
**Status:** verified locally, gates green, not deployed

## Summary

A Studio generation can now be exercised end to end on the dev machine: platform API →
worker → `musicapi` → Suno web account → callback → packaged clips in the bucket. This was
blocked on three separate setup gaps, and the fix is tooling, not product code.

## What was wrong

1. **No worker.** `/create` enqueues a job in `job_queue`; without
   `platform_api.worker` the task stays `PENDING` with `external_task_id = NULL`.
2. **No pool key.** The worker then failed with
   `No available API keys for provider 'suno'` — `api_key_entries` is empty in the sandbox.
3. **Localhost callback.** After seeding a key that points at `127.0.0.1:4003`, `musicapi`
   answered `400 callback_url must not target a local host`: the platform had no
   `PLATFORM_SUNO_CALLBACK_BASE_URL`, so it sent `https://localhost/api/v1/callbacks/suno`.

## What changed

- `scripts/dev/seed-local-suno-key.py` — encrypts a `musicapi` API key with the platform's
  `KeyEncryption` and upserts one `suno` pool row whose `base_url` matches the local
  `musicapi`. Reusable; takes `--env-file`/`--database-url`/`--key`/`--base-url`.
- `scripts/dev/studio-stack.ps1` — passes `PLATFORM_SUNO_API_BASE_URL` and
  `PLATFORM_SUNO_CALLBACK_BASE_URL` through to the API/worker, starts the worker, and
  redirects the API's stdio (without redirect a non-interactive `-File` run never returns).
- `scripts/dev/run-platform-worker.py` — accepts `PLATFORM_ENV_FILE` so the worker reads the
  same master key/provider secrets as the API.
- `scripts/dev/README.md` and `docs/studio/PROJECT_BLOCKERS.md` — the complete recipe,
  including the cloudflared callback tunnel, and B-008 marked resolved.

## Verified

| Check | Result |
|---|---|
| `POST /api/v3/web-music/generate` (V6, instrumental) | `202 QUEUED` → **`SUCCESS`** |
| Task | `3899e06d-81e8-482b-9435-617cf3f38c18` |
| Both variants | `ready: true`, `package_status: ready`, stream + download URLs |
| Bucket objects | ~2.8 MB `audio/mpeg` originals and `application/vnd.camxora.audio` packaged per variant |
| Encrypted playback | device registered → license session (`package_status: ready`) → `GET /licenses/play/{token}` returned **206 `audio/mpeg`**, 262,144 bytes, `ID3` header |
| Suno credits (`iamduke1987@gmail.com`) | 3,450 → 3,350 across two V6 jobs (platform run + direct probe) |
| `musicapi` key credits | 873 → 853 (10 credits per job) |

Packaged tracks answer `422 encrypted_playback_required` on the plain stream route by
design; playback goes through the license flow, which was verified against the same task
(`devices/register` → `licenses/sessions` → `licenses/play/{token}` → `206 audio/mpeg`).

## Migration/deploy

None. The seeded pool row and routing env are local-only; production continues to use
sunoapi.org with its configured callback host.

## Tests

| Layer | Result |
|---|---|
| `npm run typecheck` | clean |
| `npm run check:ui` | compliant |
| Vitest | **277 passed** (31 files) |
| Playwright | **135 passed / 2 skipped** |
| `platform_api` pytest | **3361 passed** (previous run, no backend change here) |

## Follow-ups

- S61 (no credits) still needs a zero-credit Suno account; S60 (moderation) needs a
  deliberate policy-refused prompt. `scripts/dev/suno-session.cjs` opens the working
  reference session for both.
