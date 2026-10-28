# Camxora Studio sandbox setup

Purpose: make a sandbox deploy of Studio mechanical, and encode the
configuration traps found on 2026-10-27 so they are not rediscovered. Pair this
with `docs/studio-release-runbook.md`, which defines the gates this enables.

## 1. What sandbox must provide

| Requirement | Why |
|---|---|
| Postgres reachable by both services | platform owns users/credits/projects; musicapi owns Suno accounts and assets |
| Public HTTPS host for **platform_api** | Suno refuses to call back to a local or private host |
| Backblaze bucket + application key | durable audio; key needs bucket read **and** write |
| Suno account(s) with a durable `__client` cookie | a bare JWT works but cannot self-refresh |
| 2Captcha key | generation, add-instrumental, replace-section, mashup, personas, uploaded audio |
| Studio internal token (one value, both services) | platform → musicapi service calls |

## 2. Environment

### musicapi

```text
DATABASE_URL=postgres://...
STUDIO_INTERNAL_TOKEN=<same value as platform>
JWT_SECRET=<>=32 chars, not a placeholder>
COOKIE_ENCRYPTION_KEY=<64 hex chars>
TWOCAPTCHA_KEY=<2captcha key>
SUNO_ACCOUNT_LABEL=<label to seed, e.g. the account email>
SUNO_CLIENT_COOKIE=<durable __client cookie>   # preferred
# or SUNO_JWT=<access token>                    # expires ~1h, cannot refresh
MUSICAPI_B2_ENDPOINT / _REGION / _BUCKET / _KEY_ID / _APPLICATION_KEY
```

`COOKIE_ENCRYPTION_KEY` must stay stable: changing it makes every stored
`client_cookie` undecryptable.

### platform_api

```text
PLATFORM_DATABASE_URL=postgresql+asyncpg://...
PLATFORM_STUDIO_INTERNAL_TOKEN=<same value as musicapi>
PLATFORM_SUNO_API_BASE_URL=https://<musicapi host>
PLATFORM_SUNO_CALLBACK_BASE_URL=https://<platform host>   # public, no localhost
PLATFORM_ENCRYPTION_MASTER_KEY=...
PLATFORM_FRONTEND_BASE_URL=https://<web host>
```

`PLATFORM_SUNO_CALLBACK_BASE_URL` must be public. Readiness rejects empty
values, non-http(s) schemes, `localhost`, `*.localhost`, and
loopback/private/link-local/reserved IPs.

### camxora.com

```text
NEXT_PUBLIC_API_BASE_URL=https://<platform host>
```

## 3. Database

```bash
python -m alembic -c platform_api/alembic.ini upgrade head
```

Expected head: `163_studio_presence_playhead` (plus any later revisions).
Required tables: `studio_projects`, `studio_operations`, `studio_uploads`,
`studio_personas`, `studio_project_shares`, `studio_project_comments`,
`studio_project_versions`, `studio_project_presence`.

Pricing rows needed by readiness (`credit_pricing`, `ai_service='suno'`):
`studio_edit`, `studio_stems_2`, `studio_stems_12`.

## 4. Streaming storage settings

Readiness reads these from `platform_db.system_settings`, **not** only env:

```text
streaming.b2.key_id
streaming.b2.application_key
streaming.b2.bucket
streaming.b2.region
streaming.b2.endpoint
```

Store them as **plain text**, not JSON. JSON-quoting leaks quote characters into
`region_name` and breaks the client with
`Provided region_name '"us-east-005"' doesn't match a supported format`.

All Camxora environments use bucket `productions-camxora-song` with the key id
`00516ad00876f4d0000000003`. A value of `camroxa-song-storage` is stale and must
be corrected; so is a 12-character key id (a real B2 key id is 25 characters).

## 5. Readiness

```http
GET /api/v3/web-music/studio/readiness   (signed-in user)
```

Expected:

```json
{
  "ready": true,
  "checks": {
    "tables": true, "pricing": true, "storage": true,
    "internal_token": true, "suno_api_base_url": true,
    "suno_callback_base_url": true, "musicapi": true,
    "musicapi_accounts": true
  },
  "musicapi_accounts": 1,
  "musicapi_pool_size": 1
}
```

These checks are live, not presence-only:

- `musicapi_accounts` counts accounts that just authenticated against Suno, so
  an expired credential reports `pool_size: 1, accounts: 0, ready: false`.
- `storage` performs an authenticated `HeadBucket`; a rejected credential
  reports `storage_probe_failed`.

## 6. Acceptance order

Run in this order; each step is independently refundable on failure.

```text
1  generate one short instrumental        (cheap; proves callbacks end to end)
2  stems_2 on that clip                   (12)
3  extend / cover on that clip            (12 each)
4  add vocals / add instrumental          (12 each, needs 2captcha)
5  replace section / mashup               (12 each, needs 2captcha)
6  persona create + persona-backed replace (0 + 12)
7  cover image                            (12; returns batch_id while images process)
8  aligned lyrics                         (free; expect word timestamps)
9  uploaded audio -> extend/cover         (see known gaps)
```

Record for each: credits charged, provider result, refund on failure, and
whether the result is usable in Studio.

## 7. Known gaps to expect

| Area | State |
|---|---|
| Uploaded-audio Extend/Cover | A completed upload is not a clip root: upload id, session id both 404, and uploads never appear in `/api/feed`. Suno's UI must convert the upload into a library clip; that step is unidentified. |
| Remaster | Requires an account with `remaster_model_types[].can_use = true`. Without it the request is accepted and never processed; the client now fails fast instead of polling for 300s. |
| Stuck provider queue | Two accepted-but-never-processed remasters occupy Suno's 2-song queue and block all generation with `429 queue_used: 2`. They can only be removed from Suno's Library UI; no cancel endpoint exists in the API or client bundles. |
| Lyrics callback | `/api/v1/callbacks/suno-lyrics` now shares the `/suno` handler. Both must exist; the client posts generation callbacks to the lyrics path. |

## 8. Post-deploy smoke

```text
[ ] readiness ready:true
[ ] create project, save, reopen
[ ] generate one track; confirm it completes (callbacks working)
[ ] stems_2 on it; confirm durable audio URL
[ ] share link view + edit; second user sees presence
[ ] export WAV and MIDI
[ ] credits charged once per success; failures refunded
```

## 9. Rollback

Keep the previous images and a DB restore point. Studio can be disabled
independently: readiness failing closes the gate, and share links can be revoked
without deleting projects.
