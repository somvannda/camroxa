# Camxora Studio release runbook

Status: release candidate, not yet approved for production.
Branch: `feat/camxora-apex`
Last updated: 2026-10-27

## 1. Purpose

This runbook is the delivery gate for Camxora Studio v1. It covers:

1. Environment configuration
2. Database migrations
3. Readiness verification
4. Live Suno acceptance tests
5. Collaboration acceptance
6. Export smoke tests
7. Sandbox and production rollout
8. Rollback

Do not add new Studio features until this runbook passes.

## 2. Required configuration

### Platform API

```text
PLATFORM_SUNO_API_BASE_URL
PLATFORM_SUNO_CALLBACK_BASE_URL
PLATFORM_STUDIO_INTERNAL_TOKEN
Durable streaming storage configuration
Existing database and Redis configuration
```

`PLATFORM_SUNO_CALLBACK_BASE_URL` must be a public host. Without it the
client falls back to `https://localhost/...`, which Suno rejects, and
readiness now reports the gate as not ready.

### musicapi

```text
STUDIO_INTERNAL_TOKEN
Suno account pool with at least one active account
Suno account encryption/API environment
Durable storage configuration
```

The platform token and musicapi token must match exactly.

### Web

```text
web-camxora connected to the platform API
Authenticated test user
Second authenticated test user for edit-link collaboration
```

Never commit real tokens or cookies. Use the deployment secret store.

## 3. Migration gate

Run from the repository root:

```bash
python -m alembic -c platform_api/alembic.ini upgrade head
```

Required head:

```text
163_studio_presence_playhead
```

Verify:

```sql
SELECT version_num FROM alembic_version;
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'studio_projects'
  AND column_name IN ('pinned', 'tags', 'archived');
```

Expected columns:

```text
pinned
tags
archived
```

## 4. Readiness gate

With a signed-in platform session:

```http
GET /api/v3/web-music/studio/readiness
```

Expected:

```json
{
  "ready": true,
  "checks": {
    "tables": true,
    "pricing": true,
    "storage": true,
    "internal_token": true,
    "suno_api_base_url": true,
    "musicapi": true,
    "musicapi_accounts": true
  },
  "missing_tables": [],
  "missing_pricing": [],
  "storage_error": null,
  "musicapi_accounts": 1,
  "musicapi_error": null
}
```

Local status on 2026-10-27:

```text
tables/pricing/storage/token/base URL/musicapi: true
musicapi_accounts: false (0 accounts)
ready: false
```

Do not proceed while `ready` is false.

## 5. Automated non-Suno checks

Use a test account with no Premier dependency:

```bash
set CAMXORA_WEB_URL=http://localhost:3103
set CAMXORA_TEST_EMAIL=...
set CAMXORA_TEST_PASSWORD=...
python scripts/studio_release_checks.py --allow-not-ready
```

The checker creates and deletes a temporary project and verifies:

```text
readiness response
project list/create/pin/tags/archive/duplicate
view and edit share creation/list/revoke
comment create/reply/list
presence with playhead and selected lane
long-poll change detection
public share page
revoked share rejection
project cleanup
```

Expected result: all checks pass, with readiness blockers reported separately.
The current local run passes 17/17 checks; readiness remains blocked only by
`musicapi_accounts: false`.

## 6. Live Suno acceptance matrix

Run each operation with a controlled test account and record:

```text
operation
credits charged
Suno result
refund on failure
result clip usable in Studio
```

### Stems

```text
[ ] 2-track vocals + instrumental
[ ] 12-track advanced stems
[ ] 12-track adds 12 lanes, not 24
[ ] 12-track charges 60 credits
```

### Edits

```text
[ ] Extend
[ ] Cover
[ ] Add vocals
[ ] Add instrumental
[ ] Replace section
[ ] Remaster
[ ] Mashup
[ ] Cover image
```

### Uploads

```text
[ ] Uploaded-audio Extend
[ ] Uploaded-audio Cover
[ ] Signed storage URL is reachable by Suno
[ ] Result audio durability verified
```

### Personas and lyrics

```text
[ ] Create persona from clip
[ ] Persona-backed Replace section uses the provider persona id
[ ] Aligned lyrics load word timestamps
[ ] Plain lyrics fallback works
```

### Billing and failure

```text
[ ] Normal edit charges 12 credits
[ ] 2-track stems charge 12 credits
[ ] 12-track stems charge 60 credits
[ ] Failed submission refunds the charge
[ ] Missing token/account returns a clear error
[ ] Duplicate submission does not double-charge
```

## 7. Two-user collaboration acceptance

Use two separate browser contexts:

```text
User A: owner
User B: edit-link collaborator
```

Check:

```text
[ ] User A creates an editable share link
[ ] User B opens it in Studio
[ ] Presence avatars appear
[ ] Collaborator playhead cursor appears
[ ] Collaborator track-selection badge appears
[ ] Clicking the avatar seeks to the collaborator playhead
[ ] Follow mode tracks the collaborator while stopped
[ ] User A edit raises User B change banner
[ ] Long-poll update arrives without a 5-second wait
[ ] Auto-apply reloads when enabled and idle
[ ] Conflicting save is rejected with a clear message
[ ] User A revokes the link
[ ] User B loses access immediately
[ ] View-only link cannot write
[ ] Expired link fails cleanly
```

Comments:

```text
[ ] Public comment can be posted
[ ] Reply uses parent_id and renders nested
[ ] Owner sees comment count
[ ] Unread badge clears after opening Share
[ ] Revoked link comments fail
```

## 8. Project regression

```text
[ ] Create project
[ ] Save and reopen
[ ] Autosave
[ ] Rename
[ ] Duplicate
[ ] Pin and unpin
[ ] Add and remove tags
[ ] Filter by tag
[ ] Archive and restore
[ ] Search and sort
[ ] Save a version
[ ] Restore a version
[ ] Export `.camxora.json`
[ ] Import `.camxora.json`
[ ] Groups persist
[ ] Track collapse persists
[ ] Mixer changes persist
```

## 9. Export smoke tests

```text
[ ] WAV full mix
[ ] MP3 full mix
[ ] WAV loop range
[ ] MP3 loop range
[ ] Stem ZIP
[ ] MIDI export
[ ] MIDI import round trip
[ ] Reverse audio
[ ] Varispeed audio
[ ] Automation curves
[ ] Group mute/solo
[ ] Master limiter
```

Verify audio is not silent, not clipped and not truncated.

## 10. Browser and layout checks

```text
[ ] Chrome current
[ ] Firefox current
[ ] Safari current where supported
[ ] Mobile timeline usable
[ ] Mixer scrolls horizontally
[ ] Inspector tabs usable
[ ] Keyboard shortcuts
[ ] No uncaught console errors
[ ] No failed Studio requests other than expected 401s
```

## 11. Sandbox rollout

```text
1. Deploy platform API, musicapi and web-camxora.
2. Run migrations.
3. Verify readiness.
4. Run a create/save/share/export smoke test.
5. Run Stems 2-track and one normal edit.
6. Check credits, refunds and logs.
7. Soak for at least 30 minutes.
```

Go/no-go:

```text
[ ] Readiness true
[ ] Migrations at head
[ ] Live operations pass
[ ] Refunds pass
[ ] Collaboration pass
[ ] No new 5xx spike
[ ] Error budget acceptable
```

## 12. Production rollout

```text
1. Snapshot database and confirm restore point.
2. Deploy migrations.
3. Deploy musicapi.
4. Deploy platform API.
5. Deploy web-camxora.
6. Verify readiness.
7. Run production smoke test with a controlled account.
8. Watch errors, credit charges and refunds.
```

Do not deploy while readiness is false.

## 13. Rollback

```text
[ ] Previous web build available
[ ] Previous platform API image available
[ ] Previous musicapi image available
[ ] Database restore point confirmed
[ ] Studio feature flag or route disable path confirmed
[ ] Share links can be disabled without deleting projects
```

Rollback triggers:

```text
- readiness false after deploy
- duplicate or missing charges
- failed refunds
- data loss or project corruption
- sustained 5xx spike
- share links exposing another user's project
```

## 14. Sign-off

```text
Engineering:      ____________________
Operations:       ____________________
Product:          ____________________
Date:             ____________________
Environment:      ____________________
Commit/image:     ____________________
Readiness result: ____________________
```

## 15. Current blockers

```text
[x] At least one active Suno account in the local musicapi pool (JWT-seeded, expires ~1h)
[x] Two-user collaboration acceptance (18/18, see section 16)
[ ] Public Suno callback base URL for live generation (see section 16)
[ ] Readiness must validate account health, not pool size (see section 16)
[ ] Production Studio internal token
[ ] Production durable storage credentials
[ ] Live Suno acceptance matrix (sandbox, not local)
[ ] Sandbox deploy
[ ] Production approval
```

## 16. Local gate results and defects (2026-10-27)

### Passed locally

```text
readiness: ready=true, all seven checks true, musicapi_accounts=1
non-Suno release suite: 17/17
two-user collaboration: 18/18
  distinct owner + collaborator identities, two presence entries with
  separate playheads and lane selections, long-poll propagation,
  non-owner write rejected, view-only write rejected, nested comment
  reply, revoked link 404, cleanup 204
pricing: studio_edit=12, studio_stems_2=12, studio_stems_12=60
refund on failure: verified twice, net zero
  debit 120000 -> refund 120000 (studio_stems_2)
  debit 150000 -> refund 150000 (music generation)
```

A generation costs 150 credits; the pricing table above covers edits and
stems only.

### Defect 1 — live generation cannot run locally

`platform_api/clients/suno_client.py` falls back to
`https://localhost/api/v3/callbacks/suno` when
`PLATFORM_SUNO_CALLBACK_BASE_URL` is unset. Suno rejects that host:

```text
Suno API error 400: submit_lyrics_task
{"error":"callback_url must not target a local host."}
```

Consequence: no clip can be generated locally, so no `asset_owners` row is
written, so every derivative operation then fails with
`"The source clip's Suno account is not recorded."` Clips generated before
an account was seeded into the pool have no ownership row and cannot be
used either.

Run the live matrix in sandbox, where the callback host is public. If local
live testing is required, set `PLATFORM_SUNO_CALLBACK_BASE_URL` to a public
tunnel and accept that the local API becomes internet-reachable while it
runs; close the tunnel immediately after.

### Defect 2 — readiness is a false green over time

`get_studio_readiness` derives `musicapi_accounts` from `pool.size` only.
A pool holding an expired or revoked credential still reports
`ready: true` while every live call fails. A stored JWT with a 2027 `exp`
was observed returning 401, so expiry is not evidence of validity.

Fix before trusting the gate: have readiness call the musicapi health check
for live account state, and treat an unreachable or unauthenticated account
as not ready.

Resolved in this change: `GET /internal/studio/health` now returns
`active_accounts` (accounts that just authenticated against Suno), and
readiness requires it to be non-zero while still reporting `musicapi_pool_size`
for diagnostics. Readiness also gained a `suno_callback_base_url` check.
Verified both directions: an expired credential reports
`pool_size: 1, accounts: 0, ready: false`; a live credential reports
`pool_size: 1, accounts: 1` with only the callback gate still red.

Note: `serve.ts` seeds from `SUNO_CLIENT_COOKIE`/`SUNO_JWT` only when the pool
is empty. To re-seed an existing row, clear its `client_cookie` and set
`is_active=false` first, otherwise the stale credential is reloaded.

### Credential note

Seeding `acct-1` from a Clerk session JWT works but cannot self-refresh;
`musicapi` only refreshes accounts that hold a durable `__client` cookie.
Re-seed from a signed-in browser session before each local live run, or
store the durable cookie for long-lived local pools.

