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

## B-003 — Local services not running

**Blocks:** end-to-end manual verification right now.

**State:** at session start only the web dev server was up (3103); `musicapi` (4003)
and `platform_api` (8100) were stopped. PostgreSQL (5432) is up.

**Unblock:** start the two services (see `README.md` / `musicapi/README.md`), ensure
`camxora.com/.env.local` points at `PLATFORM_API_URL=http://localhost:8100`.

## B-004 — Stems tab needs a listing API

**Blocks:** G12's stems tab, and PRJ-023.

**State:** uploads and workspaces now list (`GET /studio/uploads`, `GET /workspaces`
with `song_count`), and workspace selection filters the song list. Stems do not: a stem
set exists only as a `studio_operations` row with a provider-shaped `result_json`, and
no stems job has ever completed in this environment (B-005), so the projection cannot be
written against real data.

**Unblock:** finish B-005, capture one successful stems result, then project it as a
typed list endpoint. Not on the critical path.

## B-005 — Studio ops need one genuinely generated clip

**Blocks:** the last step of W4.2 (receiving an actual stem set) and the stems half of
W4.3.

**State:** the credit path is fixed and verified (D-009). The forward now reaches
musicapi, which answers `409 "The source clip's Suno account is not recorded."` because
`findAssetAccountAny` finds nothing for the seeded `sandbox-clip-ok`: it reads
`asset_owners` / `jobs.result_json` in the `sunoapi` database, and the seeded clip never
came from a Suno account.

**Unblock:** generate one real clip in the sandbox (needs a public
`PLATFORM_SUNO_CALLBACK_BASE_URL` — Suno refuses to call back to localhost, which the
readiness endpoint reports as `suno_callback_base_url: false`), then request stems on it.

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

## Closed

| ID | Was | Closed by |
|---|---|---|
| — | Studio charge died on `relation "plans" does not exist` | D-009 — studio ops price from `credit_pricing` |
