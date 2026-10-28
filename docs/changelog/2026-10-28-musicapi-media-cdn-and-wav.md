# musicapi: CDN-cacheable media, and WAV demoted to on-demand

## Summary

Three related fixes to generated-media storage. All were found by measuring the
live bucket rather than reading the code, and all stem from the same place:
`musicapi/` media is written with no cache headers, with a WAV that most users
never download, and with no way to reclaim any of it.

1. **Nothing was cacheable.** `putObject()` sent only `ContentType`. With no
   `Cache-Control`, Cloudflare caches an unmarked 200 for ~120 minutes.
2. **WAV was stored eagerly for every clip.** Measured: 223.14 of 269.07 GiB in
   `musicapi/` (**82.9%**), 6,225 objects at ~36.7 MiB. WAV is gated behind the
   `wav_download` pricing row, so most of those bytes back a product nobody bought.
3. **No reclamation path.** There is no `DeleteObjectCommand` anywhere in the
   codebase and the bucket had zero lifecycle rules.

Separately, the doc describing all of this instructed the opposite — "Do not add
an expiry/delete rule" — and claimed only MP3 was ingested.

## Product impact

- No user-visible behaviour change. Playback, downloads, and pricing are untouched.
- WAV downloads still work: the first buyer triggers an on-demand transcode from
  the stored master, and the result is cached for everyone after them.
- Faster repeat playback accrues only once a CDN sits in front of the bucket
  (`MUSICAPI_B2_PUBLIC_BASE_URL`); this change is a prerequisite, not the fix.

## Technical impact

- `src/storage.ts` — `putObject()` writes an explicit `Cache-Control`
  (`public, max-age=604800, stale-while-revalidate=86400`), overridable per call.
  Deliberately **not** `immutable`: clip keys are stable but the bytes can be
  rewritten by the content-type repair path and by video re-renders at the same key.
- `src/config.ts` — new `storage.cacheControl`, env `MUSICAPI_B2_CACHE_CONTROL`.
- `src/server.ts` — `ingestMedia()` no longer transcodes or stores WAV; it stores
  MP3 + master only. `ensureAudio()` already rebuilt WAV on demand from the
  master, so the eager copy was pure duplication.
- `scripts/b2-wav-lifecycle.ts` (new) — applies an expiry rule to `<prefix>/wav/`
  only, plus a 7-day abort of incomplete multipart uploads. Dry-run by default,
  `--apply` to write, `--remove` to drop only its own rule; merges with existing
  rules instead of replacing the configuration.
- `docs/durable-storage-b2.md` — rewritten: corrected ingest flow, added the
  `wav/` and `masters/` keys, documented the shared-bucket hazard, replaced the
  blanket no-lifecycle-rule instruction with a per-prefix retention table, added
  the Cloudflare cutover checklist, and recorded the measured footprint.
- `.env.example` — documented the storage variables, none of which were listed.

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/storage.ts`
- `musicapi/src/server.ts`
- `musicapi/scripts/b2-wav-lifecycle.ts` (new)
- `musicapi/docs/durable-storage-b2.md`
- `musicapi/.env.example`

## Migration/deploy

- No database migration. API-only change; restart the musicapi process.
- No new required env var. `MUSICAPI_B2_CACHE_CONTROL` and
  `MUSICAPI_B2_PUBLIC_BASE_URL` are both optional.
- **The lifecycle rule is not applied by deploying.** Run
  `npx tsx scripts/b2-wav-lifecycle.ts` (dry run) then `--apply` to reclaim the
  ~223 GiB already stored.
- **`MUSICAPI_B2_PUBLIC_BASE_URL` is absent from production secrets.** Until a
  Cloudflare-proxied hostname exists and is set, `getReadUrl()` keeps returning
  per-request presigned URLs, which no CDN can cache. Setting it before the
  hostname resolves would break playback.
- Bucket is shared with the live `platform_api` stack (`web-music/`, `images/`,
  14 bare-UUID prefixes). The lifecycle script is scoped to `musicapi/wav/` and
  must never be widened to cover those.

## Tests

- `npx tsc --noEmit` — clean.
- Lifecycle script dry run against `productions-camxora-song`: 0 existing rules,
  prefix `musicapi/wav/`, rule set renders as expected; nothing written.
- Confirmed the B2 lifecycle API is supported (typed `NoSuchLifecycleConfiguration`
  rather than an unsupported-operation error).
- Verified `ensureAudio()` and the download route are the only remaining `wav/`
  writers and both are on demand.
- No storage unit tests exist under `test/`, so none were added or skipped silently.

## Follow-ups

- [ ] Create `media.camxora.com` (Cloudflare, proxied) and set
      `MUSICAPI_B2_PUBLIC_BASE_URL`. **Decision required first:** a CDN base turns
      clip URLs into stable, non-expiring public URLs, where today they die after
      7 days. Accept that, or front the bucket with a Worker that enforces auth.
- [ ] Run `scripts/b2-wav-lifecycle.ts --apply` to reclaim ~223 GiB.
- [ ] `web-music/` (legacy `platform_api`, live on `music.camxora.com`) has the
      same eager-WAV pattern — 100.75 GiB, 58.6% of that prefix — plus ~44 GiB of
      `.cxa`/`.cxo` protected copies. Separate stack, separate task; the license
      rotation path must be understood before touching `.cxo`.
- [ ] No delete path exists: deleting a clip in the app still leaves its objects.
- [ ] Reconcile `AGENTS.md` (which lists `platform_api/` as reference-only) against
      `docs/PRODUCT_SCOPE.md` (which lists it in scope). nginx confirms it is live.
