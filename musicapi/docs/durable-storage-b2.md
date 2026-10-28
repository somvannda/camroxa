# Durable media storage — Backblaze B2

> Status: implemented 2026-10-02 on `feat/musicapi-sunoapi-parity`.
> Revised 2026-10-28 (`feat/musicapi-cdn-cache-and-drop-eager-wav`): CDN caching,
> WAV demoted to on-demand, lifecycle policy, measured footprint.
> Goal: stop depending on Suno's expiring links; serve stable, self-hosted media
> URLs and enable "download without limitation".

## Why

`GET /me/download` originally streamed live from Suno (3-step authorize → poll →
signed S3 URL) and clip links expired. sunoapi.org caches generated output for
14 days (MP3) / 15 days (WAV) and re-issues links via a `recovery` endpoint. This
layer gives us the same durability.

## Bucket

The platform already runs Backblaze B2 via its S3 API:

| Setting | Value |
|---|---|
| bucket | `productions-camxora-song` |
| region | `us-east-005` |
| endpoint | `https://s3.us-east-005.backblazeb2.com` |
| addressing | path-style + SigV4 |

musicapi reuses the platform's `PLATFORM_STREAMING_B2_*` deploy secrets by default,
and `MUSICAPI_B2_*` wins when set (so it can point at its own bucket/key later).

### ⚠️ This bucket is shared with a second, live stack

`productions-camxora-song` is not musicapi's bucket. It holds:

| Prefix | Owner | Notes |
|---|---|---|
| `musicapi/` | **this app** (Node/Fastify) | clips, masters, images, wav, videos, uploads |
| `web-music/` | **`platform_api`** (legacy Python) | serves `music.camxora.com`: mp3, wav, `.cxa`/`.cxo` protected playback, HLS |
| `images/` | `platform_api` | |
| 14 bare-UUID prefixes | `platform_api` | ~91 GiB, user-id-keyed, no namespace |

Both stacks run in production simultaneously — `music.camxora.com` → `music_web:3102`
+ `platform_api:8100`, while `musicapi.camxora.com` → `musicapi:4003`. **Never
apply retention or cleanup to another owner's prefix.** Everything below is
scoped to `musicapi/` only.

Note also: `AGENTS.md` lists `platform_api/` as "reference only", while
`docs/PRODUCT_SCOPE.md` lists it as in-scope, and the nginx config confirms it is
live. Those two docs disagree and should be reconciled separately.

## Config (`src/config.ts` → `config.storage`)

| Env var | Default | Purpose |
|---|---|---|
| `MUSICAPI_B2_ENDPOINT` | `PLATFORM_STREAMING_B2_ENDPOINT` | S3 endpoint |
| `MUSICAPI_B2_REGION` | `PLATFORM_STREAMING_B2_REGION` | region |
| `MUSICAPI_B2_BUCKET` | `PLATFORM_STREAMING_B2_BUCKET` | bucket |
| `MUSICAPI_B2_KEY_ID` | `PLATFORM_STREAMING_B2_KEY_ID` | access key id |
| `MUSICAPI_B2_APPLICATION_KEY` | `PLATFORM_STREAMING_B2_APPLICATION_KEY` | secret |
| `MUSICAPI_B2_PREFIX` | `musicapi` | object key prefix (namespace isolation) |
| `MUSICAPI_B2_PUBLIC_BASE_URL` | _(empty)_ | CDN base; empty → presigned URLs |
| `MUSICAPI_B2_URL_TTL_SECONDS` | `604800` (7d) | presigned GET lifetime |
| `MUSICAPI_B2_CACHE_CONTROL` | `public, max-age=604800, stale-while-revalidate=86400` | written on every upload |

`storageConfigured()` is true only when endpoint + bucket + key id + secret are all
present. Unconfigured ⇒ everything degrades to the live-Suno behaviour.

Deploy plumbing (**done**): `scripts/deploy/camxora-musicapi-remote.sh` emits
`MUSICAPI_B2_*` into `musicapi/.env`, falling back to the `PLATFORM_STREAMING_B2_*`
values already sourced from the host secrets file — so storage activates on deploy
without a manual `.env` edit. Per project rules, edit the secrets file, not the host.

## Key layout

Derivable from the clip id, so any route can find the object without a DB index.

```
musicapi/clips/<clipId>.mp3     # finished audio — the playable object
musicapi/masters/<clipId>.m4a   # decrypted source of truth; WAV is derived from this
musicapi/wav/<clipId>.wav       # ON DEMAND ONLY — created when someone buys the WAV
musicapi/images/<clipId>.<ext>  # cover art (jpg/png/webp)
musicapi/videos/<clipId>.mp4    # rendered music video
musicapi/uploads/<id>/<uuid>.<ext>
```

`masters/` is **never served to clients** — it exists so `ensureAudio()` can
re-encode. It is the only irreplaceable artifact in the tree: Suno's stream is
AES-CTR encrypted and re-decrypting needs a live account with the right license.
**Never add a retention rule to `masters/`.**

## Flow (`src/server.ts`)

1. On a completed job, `finalizeJob()` schedules `trackJob(ingestMedia(job))` —
   detached and best-effort, so it never delays the terminal state the client polls.
2. `ingestMedia()`:
   - decrypts the progressive URL with the owning account (`decryptSunoClip`);
   - transcodes MP3 and stores it, plus the decrypted m4a as `masters/`;
   - mirrors the cover image from its public URL;
   - stores object keys on each track (`audio_storage_key`, `master_storage_key`);
   - persists the updated `job.result`.
   Any failure is logged and leaves the original Suno URLs in place.
3. WAV is **not** produced at ingest. `ensureAudio(clipId, "wav")` checks
   `objectExists()`, transcodes from `masters/` only when missing, and caches the
   result. The paid download route calls it, so the first buyer pays the CPU cost
   and everyone else reads the cached object.
4. Reads: every `*/record-info` re-signs storage URLs at read time from the stored
   keys, so links never go stale.

### Why WAV is no longer eager

Ingest used to write MP3 + WAV + master for every clip. Measured on the live
bucket, WAV was **82.9% of all `musicapi/` bytes** (223.14 of 269.07 GiB; 6,225
objects at ~36.7 MiB each) — for a download gated behind the `wav_download`
pricing row that most clips never had taken. The master already makes WAV
derivable, so the eager copy was pure duplication.

## Media caching & CDN

### The problem today

`MUSICAPI_B2_PUBLIC_BASE_URL` is **not set in production secrets**, so
`getReadUrl()` falls back to `getSignedUrl(...)` on every read. That means:

- every play goes **straight to `s3.us-east-005.backblazeb2.com`** — B2 has no
  APAC region, so listeners in Cambodia take a US round trip;
- each call mints a **different signature**, so the URL differs on every request
  and no CDN can ever key a cache entry on it (cache keys include the query string);
- the CDN therefore helps **0%**, no matter what sits in front.

`putObject()` now writes an explicit `Cache-Control`; without one Cloudflare
applies a ~120-minute default to unmarked 200s.

It is deliberately **not** `immutable`: clip keys are stable but the bytes can be
rewritten by the content-type repair path and by video re-renders at the same key.

### Cutover checklist (not done — requires console/DNS access)

1. **Decide public-vs-presigned first.** A CDN base turns `getReadUrl()` into
   `https://media.camxora.com/clips/<id>.mp3` — a stable, non-expiring URL.
   Today links die after 7 days. After cutover, **anyone holding a clip id can
   stream it forever.** Unguessable ids are the only protection. Accept that
   consciously, or put a Cloudflare Worker in front to enforce auth.
2. Make the bucket (or the `musicapi/` prefix's objects) publicly readable, via a
   B2 application key scoped to that bucket. Confirm the bucket's friendly URL
   host for `us-east-005` (`f005.backblazeb2.com`) in the B2 console.
3. In Cloudflare, create `media.camxora.com` as a proxied CNAME to that host.
4. Add a Cache Rule so `*.wav` is cached too — Cloudflare's default cached-extension
   list covers `mp3`, `mp4`, `flac`, `ogg`, `jpg`, `png`, but **not `wav`**.
   (Low priority now that WAV is on-demand.)
5. Set `MUSICAPI_B2_PUBLIC_BASE_URL=https://media.camxora.com` in
   `.deploy/secrets.production.env` and redeploy. `storageInfo().cdn` flips to
   `true`, and `/health` reflects it.
6. Verify: `curl -I https://media.camxora.com/clips/<id>.mp3` returns
   `cache-control: public, max-age=604800...` and `cf-cache-status: HIT` on the
   second request.

**Do not set step 5 before step 3 resolves** — pointing the app at a hostname
that does not resolve breaks playback outright, which is worse than today's
presigned URLs.

## Retention & lifecycle

Policy for `musicapi/`:

| Prefix | Retention | Why |
|---|---|---|
| `clips/` | **indefinite** | the playable object; deleting it breaks playback |
| `masters/` | **indefinite** | only source for re-encoding; needs a live Suno account to rebuild |
| `wav/` | **expirable** | derivable from `masters/` by `ensureAudio()` |
| `images/`, `videos/` | indefinite | user-visible assets, cheap |
| `uploads/` | review | user-supplied, currently never deleted |

Apply the WAV rule with:

```bash
npx tsx scripts/b2-wav-lifecycle.ts              # dry run
npx tsx scripts/b2-wav-lifecycle.ts --apply      # 14-day expiry + abort stale multipart uploads
npx tsx scripts/b2-wav-lifecycle.ts --apply --days 30
npx tsx scripts/b2-wav-lifecycle.ts --remove     # drop only this rule
```

The script merges with existing rules rather than replacing the config, and is
scoped to `<prefix>/wav/`. As of 2026-10-28 the bucket had **zero** lifecycle
rules configured.

> An earlier revision of this doc said "do not add an expiry/delete rule" without
> qualification. That was written when WAV was indistinguishable from MP3 in the
> ingest path. The distinction above is what actually matters: never expire
> `clips/` or `masters/`; `wav/` is safe because it is regenerated.

## Measured footprint (2026-10-28)

`productions-camxora-song`, 188,796 objects, **540.40 GiB, ~$4.03/month** at
$6.95/TB.

| Prefix | Objects | GiB | Cost/mo |
|---|---|---|---|
| `musicapi/` | 24,926 | 269.07 | $2.01 |
| — `wav` | 6,225 | 223.14 | $1.67 |
| — `clips` | 6,214 | 26.51 | $0.20 |
| — `masters` | 6,233 | 19.24 | $0.14 |
| `web-music/` | 139,977 | 171.87 | $1.28 |
| bare-UUID prefixes | ~21,500 | ~91 | $0.68 |
| `images/` | 2,462 | 8.35 | $0.06 |

Context: storage is **not** the cost driver — ECS/RDS/bandwidth is. The reason to
care is that nothing in either codebase ever deletes an object, so cost only
accrues. Each new clip costs ~11.5 MiB (mp3 + master) instead of ~48.5 MiB.

## Verified

- `npm run typecheck` clean.
- B2 round trip against the real bucket: `put → get → presigned GET 200 → delete`.
- Storage config resolves from `.deploy/secrets.env` (`configured: true`).
- Lifecycle dry run against the live bucket: 0 existing rules, prefix
  `musicapi/wav/`, rule set renders correctly.

## Ops follow-ups

- [ ] Cloudflare cutover (section above) — the latency fix is inert until done.
- [ ] `scripts/b2-wav-lifecycle.ts --apply` to reclaim ~223 GiB.
- [ ] Consider expiring `uploads/` — user files are never deleted today.
- [ ] No `DeleteObjectCommand` exists in the codebase; deleting a clip in the app
      does not delete its objects.
