# Durable media storage — Backblaze B2

> Status: implemented 2026-10-02 on `feat/musicapi-sunoapi-parity`.
> Goal: stop depending on Suno's expiring links; serve stable, self-hosted media
> URLs and enable "download without limitation".

## Why

Today `GET /me/download` streams live from Suno (3-step authorize → poll → signed
S3 URL) and clip links expire. sunoapi.org caches generated output for 14 days
(MP3) / 15 days (WAV) and re-issues links via a `recovery` endpoint. This layer
gives us the same durability.

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

## Config (`src/config.ts` → `config.storage`)

| Env var | Default | Purpose |
|---|---|---|
| `MUSICAPI_B2_ENDPOINT` | `PLATFORM_STREAMING_B2_ENDPOINT` | S3 endpoint |
| `MUSICAPI_B2_REGION` | `PLATFORM_STREAMING_B2_REGION` | region |
| `MUSICAPI_B2_BUCKET` | `PLATFORM_STREAMING_B2_BUCKET` | bucket |
| `MUSICAPI_B2_KEY_ID` | `PLATFORM_STREAMING_B2_KEY_ID` | access key id |
| `MUSICAPI_B2_APPLICATION_KEY` | `PLATFORM_STREAMING_B2_APPLICATION_KEY` | secret |
| `MUSICAPI_B2_PREFIX` | `musicapi` | object key prefix (namespace isolation) |
| `MUSICAPI_B2_PUBLIC_BASE_URL` | _(empty)_ | optional CDN base; empty → presigned URLs |
| `MUSICAPI_B2_URL_TTL_SECONDS` | `604800` (7d) | presigned GET lifetime |

`storageConfigured()` is true only when endpoint + bucket + key id + secret are all
present. Unconfigured ⇒ everything degrades to today's live-Suno behaviour.

Deploy plumbing: emit these from `camxora-musicapi-remote.sh` into `musicapi/.env`
(same pattern as `CHMABA_*`). Per project rules, edit the secrets file, not the host.

## Key layout

Derivable from the clip id, so any route can find the object without a DB index:

```
musicapi/clips/<clipId>.mp3     # finished audio
musicapi/images/<clipId>.<ext>  # cover art (jpg/png/webp)
```

## Flow (`src/server.ts`)

1. On a completed job, `finalizeJob()` schedules `trackJob(ingestMedia(job))` —
   detached and best-effort, so it never delays the terminal state the client polls.
2. `ingestMedia()`:
   - downloads the real MP3 via a pooled account (`client.downloadBuffer(clipId, "mp3")`);
   - mirrors the cover image from its public URL;
   - stores object keys on each track (`audio_storage_key`, `image_storage_key`);
   - persists the updated `job.result`.
   Any failure is logged and leaves the original Suno URLs in place.
3. Reads:
   - `GET /api/v1/generate/record-info` (and every `*/record-info`) re-signs storage
     URLs at read time from the stored keys, so links never go stale.
   - `GET /me/download` now tries the B2 object first, then falls back to live Suno.

## Verified

- `npm run typecheck` clean.
- B2 round trip against the real bucket: `put → get → presigned GET 200 → delete`.
- Storage config resolves from `.deploy/secrets.env` (`configured: true`).

## Ops follow-ups

- [ ] **Lifecycle rule** on the `musicapi/` prefix → delete after 14 days (parity)
      if retention is desired. Set in the B2 console/CLI; not done in code.
- [ ] Point `MUSICAPI_B2_PUBLIC_BASE_URL` at Cloudflare in front of B2 for free
      egress + public CDN URLs (currently presigned B2 URLs).
- [ ] Optional: mirror WAV (only MP3 is ingested today) and separated stem outputs.
- [ ] Finish the 3 `/api/file-*-upload` convenience endpoints on top of this layer.
