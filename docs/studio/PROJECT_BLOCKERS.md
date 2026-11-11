# PROJECT BLOCKERS

Open items that stop work. Each names the unblocking action and the owner.

## B-001 — Reference session (RESOLVED 2026-11-06)

**State:** the user signed in to the reference in the connected browser on 2026-11-06.
The live Studio opened, and the three remaining `PART` gaps were exercised against real
data (S44 IR library, S30 stretch + tempo change, S32 CC lane tabs). Screenshots still
need the OpenCode desktop window visible; the browser tool refuses to capture while it
is minimised.

**Remaining:** S60 (moderation) and S61 (no-credit account) still need genuine triggers.
See `reference/CAPTURE_GAPS.md` for the evidence captured and the parts still pending.

## B-002 — No Studio test harness

**Blocks:** M11 and the `VERIFIED` roll-up for most features.

**State:** `camxora.com` has no test runner configured. Adding one is a dependency
decision (vitest vs. node:test vs. Playwright only).

**Unblock:** approve vitest + Playwright as dev dependencies, then W5.1.

**Interim:** manual journeys W-A…W-H recorded in `PROJECT_PROGRESS.md`.

## B-003 — Local services not running (RESOLVED 2026-11-10)

**State:** the Studio stack now runs from this worktree: musicapi `:4003` (after adding
`musicapi/.env` with the canonical `COOKIE_ENCRYPTION_KEY`, which must match the rows in
`sunoapi`), platform API `:8100` with the sandbox DB, Redis, moto S3 `:9000`, and the
web dev server `:3103`. Real generation and stems are verified end to end — see B-005
for the exact environment and the callback tunnel.

**Local UI login:** set `NEXT_PUBLIC_TURNSTILE_DISABLED=1` in `camxora.com/.env.local`
and restart `next dev`. The backend already accepts a missing Turnstile token in
development, but the widget never issues one on localhost, so the form stays disabled
without the flag. Verified with a Playwright form login.

## B-004 — Stems tab needs a listing API (RESOLVED 2026-11-10)

**Was:** a stem set existed only as a `studio_operations` row with a provider-shaped
`result_json`, and no stems job had ever completed in this environment (B-005), so the
projection could not be written against real data.

**Resolved:** B-005 now has a real result, and `GET /api/v3/web-music/studio/stems`
flattens completed `stems` operations into one typed row per stem clip (deduped, with
audio URL, group name, duration and timestamps). The library's Stems tile and toolbar
chip open that list; each row auditions and adds the stem at the playhead. Covered by
`platform_api/tests/test_web_music_studio_stems.py` and the library e2e.

## B-005 — Studio ops need one genuinely generated clip (RESOLVED LOCALLY 2026-11-10)

**Blocks:** the last step of W4.2 (receiving an actual stem set) and the stems half of
W4.3. **Unblocked:** a real generation plus a real stems job both completed locally, so
B-004 can now be written against a real `studio_operations.result_json`.

**Was:** the forward reached musicapi, which answered `409 "The source clip's Suno
account is not recorded."` because the seeded clip never came from a Suno account, and
the platform reported `suno_callback_base_url: false` because Suno refuses to call back
to localhost.

**Local recipe that works (2026-11-10).** Three processes, all from the repo root:

```powershell
# 1. musicapi, with the canonical worktree key (COOKIE_ENCRYPTION_KEY must match
#    the rows in the sunoapi database) and the B2/S3 storage env.
cd musicapi && npm run build && npm start        # http://127.0.0.1:4003

# 2. a public callback tunnel (Suno rejects localhost callbacks)
cloudflared tunnel --url http://127.0.0.1:8100 --no-autoupdate
#    take the https://<name>.trycloudflare.com it prints

# 3. platform API (+ worker for queued generation), sandbox DB, tunnel callback,
#    v3 credit charging, and the platform-prefixed internal token.
$token = ((Get-Content musicapi/.env | Where-Object { $_ -match '^STUDIO_INTERNAL_TOKEN=' }) -split '=',2)[1]
$env:PLATFORM_DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/camxora_pfm_sandbox'
$env:PLATFORM_STUDIO_INTERNAL_TOKEN=$token
$env:PLATFORM_SUNO_CALLBACK_BASE_URL='https://<name>.trycloudflare.com'
$env:PLATFORM_CREDITS_ONLY_V3_CHARGE='true'
python -m uvicorn platform_api.main:app --host 127.0.0.1 --port 8100 `
  --env-file "G:\Developments\Projects\Camxora\platform_api\.env"
python -m platform_api.worker
```

Notes learned the hard way:

- `STUDIO_INTERNAL_TOKEN` in `.env` is ignored (settings use the `PLATFORM_` prefix);
  set `PLATFORM_STUDIO_INTERNAL_TOKEN` or Studio stems answer
  `502 studio_internal_token_missing`.
- The sandbox has no key-pool rows, so generation there stops at
  `NO_AVAILABLE_KEYS`; run against the checkout's `platform_db` (which has keys) to
  exercise the real provider, then restore the sandbox for tests.
- The worker needs the same env as the API (`PLATFORM_ENCRYPTION_MASTER_KEY`), otherwise
  it cannot load the key pool.
- Sandbox DBs with `credits_only_v3_charge` off hit the legacy reserve path whose credit
  service is not wired (`credit_service=None`); set `PLATFORM_CREDITS_ONLY_V3_CHARGE=true`.

**Verified:** `POST /web-music/generate` → 202, callback → `SUCCESS`, both clips
packaged and uploaded to B2; `POST /studio/generations/{id}/stems` → 202, then
`GET /studio/operations/{id}` → `complete` with four stem clips (Vocals/Instrumental ×2).

**Do not** point a seeded task at another user's real asset id: it would run a paid
Studio operation against someone else's Suno asset.

## B-006 — Library upload needs streaming storage (RESOLVED LOCALLY 2026-11-07)

**State:** `POST /api/v3/web-music/studio/uploads` answered `503 "Studio uploads are not
configured."` because `resolve_streaming_storage_config` found no bucket. The control
existed and posted the file; the panel showed the backend's message.

**Resolved locally** with an S3-compatible server and the env fallbacks the resolver
already reads (no database rows needed):

```
# S3 stand-in (moto is in the Python env; no Docker image needed)
python -m moto.server -p 9000
python -c "import boto3; boto3.client('s3', endpoint_url='http://127.0.0.1:9000',
  aws_access_key_id='minioadmin', aws_secret_access_key='minioadmin',
  region_name='us-east-1').create_bucket(Bucket='camxora-studio')"

# restart platform_api with:
PLATFORM_STREAMING_B2_KEY_ID=minioadmin
PLATFORM_STREAMING_B2_APPLICATION_KEY=minioadmin
PLATFORM_STREAMING_B2_BUCKET=camxora-studio
PLATFORM_STREAMING_B2_REGION=us-east-1
PLATFORM_STREAMING_B2_ENDPOINT=http://127.0.0.1:9000
```

With that, the browser upload returns the new row (no alert): verified through the Studio
drawer and `studio-library.spec.ts` (which still accepts either the row or an explained
refusal, so it stays portable).

**Production unblock remains:** a real bucket (B2/S3) configured the same way. The
sandbox API is currently running with the moto env; restart it without those five
variables to return to the previous behaviour.

**Do not** stub the endpoint to return a fake upload: the Add button would then place a
clip whose URL 404s.

## B-007 — Render-in-place needs configured storage

**Blocks:** end-to-end verification of the in-place bounce on a real bucket. The code
path ships (D-031 update): render → `uploadStudioAudio` → `(bounced)` track with the
source muted, falling back to a download when the upload refuses.

**State:** the running sandbox API answers `POST /api/v3/web-music/studio/uploads` with
`502 storage_not_configured`, so the fallback is what executes locally; the in-place
path is covered by a stubbed upload in `tests/e2e/studio-bounce.spec.ts`.

**Unblock:** start `platform_api` with the moto/streaming env from B-006 (or a real
bucket) and re-run the bounce spec with `STUDIO_EXPECT_UPLOADS=1` semantics, then confirm
the bounced track plays after a reload.

**Attempted 2026-11-11** with a second API instance on `:8101` and moto on `:9000`, and
the browser's upload proxied to it (`STUDIO_UPLOAD_PROXY_URL` in
`tests/e2e/studio-bounce.spec.ts`). Two things surfaced:

1. `--env-file platform_api/.env` points at `platform_db`, not the sandbox database, so
   the studio user's session is unknown there (`401 User not found`). The sandbox run
   needs `PLATFORM_DATABASE_URL=.../camxora_pfm_sandbox` set explicitly, because
   `python-dotenv` does not override an existing environment variable.
2. With the sandbox database, `resolve_streaming_storage_config` still reports
   unconfigured: that database already holds `streaming.b2.*` rows that fail to decrypt
   with the current `PLATFORM_ENCRYPTION_MASTER_KEY` ("Incorrect padding"), and the
   resolver prefers the database secret over the environment fallback. Re-saving the
   streaming config in admin Settings (or deleting those rows) is the real unblock.

## Closed

| ID | Was | Closed by |
|---|---|---|
| — | Studio charge died on `relation "plans" does not exist` | D-009 — studio ops price from `credit_pricing` |
