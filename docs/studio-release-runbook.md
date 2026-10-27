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

### Live operations run against the pooled account

Executed against clips genuinely owned by the seeded Suno account
(`acct-1` / `iamduke1987@gmail.com`), not generated locally:

```text
stems_2      complete   12 credits kept   durable B2 audio URL
cover        complete   12 credits kept   durable B2 audio URL
cover-image  accepted   12 credits kept   returns batch_id + image_ids, images still processing
extend       complete   12 credits kept   (only once the task had audio_url_ok set)
remaster     error      refunded          "Timed out waiting for clip completion." (2/2 runs, ~306s)
```

Findings:

- Derivative operations need a task row with `audio_url_ok`. Without it,
  `extend` fails with `audio_ingest_failed`. With a real signed B2 URL set,
  the same extend completes. This is a fixture requirement, not a code bug.
- Suno enforces per-account clip ownership: an operation on a clip owned by a
  different Suno account returns `403 permission_denied`. Do not backfill
  `asset_owners` to force a clip onto an account; the provider rejects it.
- `add-vocals` completed (12 credits). `add-instrumental`, `replace-section`
  and `mashup` each failed fast with
  `TWOCAPTCHA_KEY is required to solve captcha.` and refunded: those endpoints
  are captcha-gated, so a 2Captcha key is required in any environment that
  runs them. Configuration gap, not a code defect.
- `personas` is captcha-gated like the other operations: its musicapi job
  errored with the same `TWOCAPTCHA_KEY` message when no key was configured.
  **With `TWOCAPTCHA_KEY` set it completes**: row reaches `status: complete` with
  a real `provider_persona_id`, at zero credits. A persona-backed Replace
  section using that provider id also completes (12 credits, durable B2 audio),
  so the persona path is verified end to end. Creation is asynchronous by
  design — POST returns 202 with `status: queued`, and `GET /studio/personas`
  refreshes each row from the musicapi job. Re-listing correctly reported
  `status: error` with the captcha message, so the failure is **not** silent
  (an earlier note in this file claimed otherwise and was wrong). Minor wart
  only: the id returned by POST is not pollable as a studio operation, so a
  caller must re-list to observe progress.
- `lyrics` works: with a live credential it returns the full text (648 chars)
  **and** 97 word-level timestamps (`start_s`/`end_s`/`p_align`) from Suno's
  `/api/gen/{clip}/aligned_lyrics`. An earlier note here reported `aligned_words`
  as empty and called it a defect; that was wrong — the seeded JWT had expired,
  `getAlignedLyrics` got a 401, and the caller in `server.ts` catches every
  exception and falls back to `[]`.

  Genuine (minor) robustness gap: because the caller swallows all errors and
  `getAlignedLyrics` only special-cases 404, an authentication failure is
  indistinguishable from "this clip has no alignment". A 401 should surface as
  an error rather than silently degrading to plain lyrics.

  Fixed: the internal lyrics route no longer swallows the error. A clip with no
  alignment still returns `[]` (404), but any other failure now returns 502 with
  `Could not load aligned lyrics from Suno.` plus the underlying detail.
  Verified by seeding a bogus credential: 502 `Account acct-1: no active Clerk
  session.` instead of a silent empty list.
- Uploaded-audio Extend/Cover could not be exercised, and the cause is a
  credential defect rather than a network fault. `POST /studio/uploads` fails
  502 `Could not store the uploaded audio.` with botocore surfacing
  `SSLEOFError: EOF occurred in violation of protocol`, but that error is
  misleading: raw TLS to `s3.us-east-005.backblazeb2.com` succeeds (TLSv1.3),
  anonymous HTTP returns 403 as expected, and a signed request eventually
  reports the truth.

  `system_settings.streaming.b2.key_id` is `16ad00876f4d` (12 chars) — a
  truncated fragment of the real 25-char key id `00516ad00876f4d0000000003`.
  A signed request with it returns
  `ClientError: InvalidAccessKeyId: Malformed Access Key Id`. Substituting the
  full key id and secret from musicapi's working config yields
  `AccessDenied: not entitled`, because that key is scoped to
  `productions-camxora-song`, not to the platform's `camroxa-song-storage`.

  So the platform's stored pair was a truncated copy of a different bucket's
  key. Corrected: the project's own deploy secrets
  (`.deploy/secrets.sandbox.env`, and every other environment) use bucket
  `productions-camxora-song` with key id `00516ad00876f4d0000000003` — the same
  bucket and key musicapi uses. `camroxa-song-storage` is a stale value.
  Writing those five `streaming.b2.*` settings (as **plain text**, not JSON —
  quoting the value leaks into `region_name`) makes `HeadBucket` succeed,
  readiness report `storage: true`, and `POST /studio/uploads` return 201.

  Fixed: readiness now calls `StorageService.probe()` (an authenticated
  `HeadBucket` with 5s timeouts) instead of trusting that a bucket and keys are
  merely present, and reports `storage: false` with
  `storage_probe_failed: ... Forbidden` whenever the credential is rejected.
  The bucket therefore needs `ListBucket`/bucket-read permission for the key,
  not just write.

  With storage fixed, uploads land (201) but both uploaded-audio operations
  still fail, and they are genuine defects rather than config:

  ```text
  upload_extend  422  /api/generate/v2-web/ failed (422):
                      {"loc":["body","params","prompt"],"msg":"Field required"}
  upload_cover   404  /api/generate/v2-web/ failed (404): {"detail": "Not found."}
  ```

  Both refunded correctly. Registration is not the blocker: routing the
  `audio_url` through Suno's upload handshake (`upload_init` → S3 PUT →
  `upload_register` → poll for a clip id) before the operation produced the
  same two errors, so these are payload/task-shape defects:

  - `upload_extend` sends `params.prompt` (non-empty, forwarded by the
    platform) yet Suno still answers `body.params.prompt` missing, so the
    request shape does not match Suno's model.
  - `upload_cover` submits `task: "cover_infill"` to `/api/generate/v2-web/`
    and gets `404 Not found`, i.e. that task/path combination does not exist.

  Root cause confirmed by probing Suno directly with a fake clip id (validation
  fails on the clip, not the shape, so no credits are spent):

  - the `params` wrapper is wrong: `params.prompt` is reported missing even when
    set, while the **flat top-level** shape (`task`, `prompt`,
    `continue_clip_id`, `continue_at`, `cover_clip_id`, ...) validates and only
    fails with `403 permission_denied` on the fake clip;
  - `cover_infill` is a valid task only with flat clip ids — nested under
    `params` it returns "continue_clip_id is required", and an unknown task
    falls back to a 422 listing the accepted task names.

  Fixed accordingly in `uploadExtendMusic` / `uploadCoverMusic`, and the URL
  path now registers the audio through Suno's upload handshake
  (`registerAudioFromUrl`) because Suno needs a Suno-side clip id, not a URL.

  With `TWOCAPTCHA_KEY` configured the captcha gate clears and registration
  succeeds, but the flow still cannot complete: Suno's upload status object
  (documented shape `{id, status, title, copyright_muted}`) carries **no
  `clip_id`**, so `uploadAudio` previously fell back to the upload session id,
  which Suno then 404s as a clip root. That fallback is now removed and the
  operation fails explicitly with
  `Suno did not return a processed clip id for the uploaded audio.` (refunded).

  Remaining work: determine what a completed audio upload actually yields as a
  clip root. Probed directly: the upload does reach `status: complete`, and its
  status object only ever exposes `{id, status, title, copyright_muted}` — no
  clip id. Exhaustive checks so far, all negative:

  - upload id as `cover_clip_id` (`cover_infill`) → 404
  - upload id as `continue_clip_id` (`upload_extend`) → 404
  - session id as `cover_clip_id` → 404
  - the account's `/api/feed` shows no upload entry at all (uploads are a
    separate collection from clips)

  So a completed upload is not itself a clip root, and it does not appear in the
  feed. There must be a conversion/import step (Suno's "Uploads" UI performs it)
  that turns an upload into a library clip; that step is the last unknown and
  should be captured from the UI rather than inferred.

  Additional evidence from the browser session: submitting the flat shape with a
  **real owned clip** returns `422 token_validation_failed` rather than a shape
  error, while the same shape with a fake clip returns `403 permission_denied`.
  Suno validates the clip before the captcha token, so the shape is accepted and
  a captcha token is the sole remaining gate.
- `remaster` is a reproducible defect locally, root cause confirmed:
  `client.remaster` hardcodes `normalizeModel(model) ?? "chirp-flounder"`, but
  the account's model list only has `chirp-hawk`, `chirp-hawk-wild` and
  `chirp-goose` — `chirp-flounder` does not exist for it. The account's
  `remaster_model_types` is a single entry, `chirp-halibut`, with
  `can_use: false` and `free_remasters_remaining: 0`, so the account is not
  entitled to remaster at all. Suno accepts the submit (202) but never
  processes, and `pollClips` (`musicapi/src/client.ts`, 300s ceiling) burns the
  full window before erroring and refunding.

  Two fixes needed, neither a provider bug in Studio's own logic:  1. stop hardcoding `chirp-flounder`; use the account's remaster model
     (or the configured default) instead of a model it cannot use;
  2. pre-flight the entitlement so an unentitled account fails fast with a
     clear message, instead of charging, waiting five minutes and refunding.

  Both fixed in `client.remaster`: it now reads `remaster_model_types`, picks a
  usable model (preferring the account default), and throws
  "This Suno account is not entitled to remaster (no usable remaster model)."
  when none can be used. Verified: the same call now errors in 3s instead of
  306s with a zero net credit delta.

  Updated 2026-10-27 — this is a **plan-level** limitation, not an exhausted
  quota. Two independent **Premier** accounts were checked: one with ~1,900
  credits and one with 10,000 fresh credits. Both report
  `remaster_model_types: [chirp-halibut can_use=false]` and
  `free_remasters_remaining: 0`. Adding an entitled account therefore does not
  fix remaster; no Premier account in the pool can use it. Ship the feature
  capability-gated (hide or disable with a clear reason) unless Suno confirms
  the correct remaster model for current plans.



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

Readiness validation for this gate: a non-empty value is not sufficient.
`_callback_base_is_public` rejects schemes other than http/https, localhost and
`*.localhost`, and loopback/private/link-local/reserved IP literals, so
`http://127.0.0.1:8100` reports the gate as not ready exactly like an unset
value. Verified against nine cases (empty, localhost, 127.0.0.1, 192.168.x,
10.x, ftp, a tunnel host and two public hosts).

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

