# Both Suno versions of a generation now complete (Version 2 no longer stuck)

## Summary

A single `/generate` returns **two** Suno clips — rendered on music.camxora.com as
Version 1 (`variant=ok`) and Version 2 (`variant=alt`). Users reported that only
Version 1 completed/downloaded; Version 2 spun forever.

Root cause was in `musicapi`'s `pollClips`: it returned as soon as **any
non-empty subset** of the `/api/feed/` response was terminal. Suno's feed can
transiently return only one of a generation's two clips (the other not indexed
yet), so the poll returned with a single clip, the job finalized/stored one
track, and Version 2 never existed downstream.

The integration chain is
`music.camxora.com` (`music_web`) → `platform_api` (`suno_api_base_url =
https://musicapi.camxora.com`) → `musicapi`. `platform_api` maps
`sunoData[0] → ok`, `sunoData[1] → alt`, so a one-track `musicapi` result is
exactly "Version 1 works, Version 2 missing".

## Product impact

- A normal generation now yields **both** versions; Version 2 completes and is
  downloadable like Version 1.
- `platform_api` no longer reports a generation as successful when the upstream
  explicitly failed after producing partial audio — the user gets an honest
  failure (and refund) instead of a half-broken result.
- `web-user` playground playback is resilient: it plays through the backend DRM
  proxy and falls back through durable → stream → download, with a load timeout.

## Technical impact

- `musicapi/src/client.ts`, `musicapi/src/suno.ts`: `pollClips` indexes the feed
  by clip id and returns only once **every requested id** is present and
  terminal, preserving submitted order (so `ok`/`alt` mapping stays correct).
- `musicapi/test/poll-clips.test.ts` (new) + `test/run.ts`: regression tests for
  partial feeds, mid-generation status, timeout, and the single-clip case.
- `platform_api/clients/suno_client.py`: `parse_suno_generate_poll` checks
  `is_suno_failure_status(status)` **before** returning success on partial audio.
- `platform_api/tests/test_suno_status_messages.py`: regression test
  (`GENERATE_AUDIO_FAILED` + one audio URL → `state="failed"`).
- `musicapi/web-user`: the playground renders `AuthorizedAudio` (DRM-safe proxy)
  instead of a raw `<audio>` on Suno's encrypted CloudFront URL; both
  `clipAudio` helpers prefer the durable B2 `audio_url`; `AuthorizedAudio` times
  out a stalled load.

No schema change.

## Files touched

- `musicapi/src/client.ts`
- `musicapi/src/suno.ts`
- `musicapi/test/poll-clips.test.ts`
- `musicapi/test/run.ts`
- `musicapi/web-user/app/dashboard/playground/page.tsx`
- `musicapi/web-user/components/playground.tsx`
- `platform_api/clients/suno_client.py`
- `platform_api/tests/test_suno_status_messages.py`
- `platform_api/CHANGELOG.md`
- `docs/changelog/2026-10-07-musicapi-both-versions-complete.md` (this file)

## Migration / deploy

- No migration.
- Requires a restart/redeploy of **both** `musicapi` and `platform_api`.
- Sandbox-first: `sync_musicapi_sandbox.py` + `sync_platform_api_sandbox.py`,
  then the production twins (`deploy_musicapi_production.py`, production
  platform_api deploy).

## Tests

- `musicapi`: `npm run typecheck` clean; `npm run test:unit` 56/56 pass.
- `platform_api`: `test_suno_status_messages.py` 17 pass, suno-client subset 83
  pass, `test_web_music_router.py` 12 pass.
- `web-user`: `tsc --noEmit` clean.
- CI on PR #370: all 7 checks green (MusicAPI typecheck+build + smoke gate,
  Python syntax, gitleaks, secret-path block, admin build, web-admin units).

## Follow-ups

- Validate with a fresh production generation: `/api/v1/generate/record-info`
  should return two `sunoData` tracks with both `audio_url_ok` and `audio_url_alt`
  populated.
- If a clip genuinely never appears in the feed, `pollClips` now times out and
  the job fails (refunded) rather than reporting a partial success.
