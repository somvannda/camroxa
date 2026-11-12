# Studio dev stack: moto + platform API

The Studio editor talks to four processes. `camxora.com` and `musicapi` are started the way
they always were; this folder exists because **the platform API needs two environment
details that are easy to lose when the process is restarted**:

1. The database. `platform_api/.env` sets `PLATFORM_DATABASE_URL` to `platform_db`, but the
   Studio sandbox lives in `camxora_pfm_sandbox`. `python-dotenv` does not override an
   existing environment variable, so the sandbox URL must be exported *before* uvicorn
   reads the env file.
2. The Studio internal token. `platform_api` sends `x-internal-token` to `musicapi` on every
   clip operation; `musicapi` compares it with `STUDIO_INTERNAL_TOKEN`. A restart without
   that token silently disables Extend/Cover/Remaster/Vocals/Instrumental/Replace/Mashup,
   stems and personas — the UI shows *"Studio operations are not configured."*

Because the token is a secret, this script **never hard-codes it**: it reads
`PLATFORM_STUDIO_INTERNAL_TOKEN` from the environment (or `-Token`) and refuses to start
without it, so a degraded API cannot be launched by accident.

## Usage

```powershell
# 1. Export the same value musicapi runs with (session only; never commit it)
$env:PLATFORM_STUDIO_INTERNAL_TOKEN = "<the value musicapi uses>"

# 2. Start moto (if needed), the bucket and the platform API on :8100
pwsh -File scripts/dev/studio-stack.ps1

# 3. Bring up the whole stack (musicapi + web too) or just check what is running
pwsh -File scripts/dev/studio-stack.ps1 -All
pwsh -File scripts/dev/studio-stack.ps1 -Status

# 4. Dry run: print what would start, touch nothing
pwsh -File scripts/dev/studio-stack.ps1 -DryRun

# 5. Stop the processes (API + moto, or the whole stack with -All)
pwsh -File scripts/dev/studio-stack.ps1 -Stop
pwsh -File scripts/dev/studio-stack.ps1 -Stop -All
```

`-Status` prints the health of `:3103` (web), `:8100` (platform API), `:4003` (musicapi)
and whether moto is listening, which is the quickest way to spot a half-down stack —
musicapi in particular can be down while everything else looks fine.

## Generation needs provider keys

The script also starts `platform_api.worker` (logs in `%TEMP%\camxora-platform-worker*.log`).
Every `/create` generation is enqueued in `job_queue` and submitted by that worker. On a
fresh sandbox, `api_key_entries` is empty, so the worker reports
`No available API keys for provider 'suno'` and the task stays `PENDING` forever — the
editor and exports are unaffected. Seed pool rows from the admin console (or a sandbox
fixture) before expecting live generations.

The script also starts an S3 stand-in (moto) on `:9000` and creates the
`camxora-studio` bucket, because uploads (recorded takes, in-place bounce, Library
uploads) need storage. Without it the API answers `storage_not_configured`, which is the
designed fallback (B-006/B-007), not a crash.

## Requirement for uploads

Storage is only used when the resolver finds credentials. If the sandbox database already
holds `streaming.b2.*` rows with values encrypted under a different
`PLATFORM_ENCRYPTION_MASTER_KEY`, those rows win over the environment and the resolver
fails to decrypt them (B-007). Re-save the streaming settings from the admin console, or
clear those rows, before expecting the env fallbacks below to apply:

```
PLATFORM_STREAMING_B2_KEY_ID=minioadmin
PLATFORM_STREAMING_B2_APPLICATION_KEY=minioadmin
PLATFORM_STREAMING_B2_BUCKET=camxora-studio
PLATFORM_STREAMING_B2_REGION=us-east-1
PLATFORM_STREAMING_B2_ENDPOINT=http://127.0.0.1:9000
```

## Verify

```powershell
(Invoke-WebRequest http://127.0.0.1:8100/health).StatusCode              # 200
cd camxora.com
$env:STUDIO_UPLOAD_PROXY_URL = "http://127.0.0.1:8100"
npx playwright test tests/e2e/studio-bounce.spec.ts                       # real upload
```

The gated bounce spec is skipped without `STUDIO_UPLOAD_PROXY_URL`; setting it makes the
test exercise the live upload path instead of the download fallback.
