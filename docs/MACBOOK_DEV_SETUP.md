# MacBook / travel machine setup

**Audience:** engineers cloning CAMXORA on a new machine (especially macOS) to continue API / portal / website work.

**Date:** 2026-07-20

## What works on Mac

| Surface | Mac OK? | Notes |
|---------|---------|-------|
| `platform_api` | Yes | Primary travel target |
| `admin_portal` / `user_portal` / `website` / `music_web` | Yes | Node + Vite/Next |
| Desktop `camxora_python` | **No** | Windows-only (PySide + installer + optional NVENC DLL) |
| Native encode bridge | **No** | `camxora_encode_bridge.dll` — Windows + NVIDIA only |

Point the desktop app (on Windows) at sandbox while you edit API/portal on Mac.

## Clone + branch

```bash
git clone https://github.com/somvannda/camroxa.git
cd camroxa
git checkout cursor/channel-pricing-and-plan-tiers
git pull
```

## Database (required)

Local Postgres must match sandbox schema. Latest migration:

`068_video_export_telemetry`

```bash
cd platform_api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or poetry/uv if you use that

# Copy env from your password manager / Windows machine — never commit .env
cp .env.example .env              # then fill PLATFORM_DATABASE_URL, secrets

alembic upgrade head
alembic current                   # expect: 068_video_export_telemetry
```

If local DB is empty, create `platform_db` first, then upgrade.

## Run API locally

```bash
cd platform_api
source .venv/bin/activate
uvicorn platform_api.main:app --reload --port 8000
```

Health check: `http://localhost:8000/api/v1/auth/signup-mode`

## Portals / website (optional)

```bash
# User portal
cd user_portal && npm install && npm run dev

# Admin
cd admin_portal && npm install && npm run dev

# Marketing site
cd website && npm install && npm run dev
```

Set `NEXT_PUBLIC_PLATFORM_API_BASE_URL` / Vite env to your local API or sandbox as needed.

## Desktop export note (Windows only)

- Default export uses **ffmpeg pipe** (works without the native DLL).
- Optional fast path: `CAMXORA_NATIVE_ENCODE=1` + `camxora_encode_bridge.dll` (NVIDIA NVENC).
- Missing DLL → automatic fallback to ffmpeg. **No Mac build exists.**

## Sandbox API timeouts

Client default timeout is **30s**. Under heavy desktop load (many batches + auto-video + progress polls), you may see:

`Request timed out contacting https://api.sandbox.camxora.com/api/v1`

That is usually **server/network saturation**, not a missing migration. Quick check:

```bash
curl -m 15 https://api.sandbox.camxora.com/api/v1/auth/signup-mode
```

If curl is fast but the app times out, reduce concurrent desktop workers or wait for sandbox to settle.

## Checklist before leaving Windows machine

1. `git push` current branch (already on `origin/cursor/channel-pricing-and-plan-tiers` after travel prep).
2. Note sandbox vs local: both should be at alembic `068`.
3. Bring `.env` values via password manager (API keys, DB URL) — not in git.
4. On Mac: clone → `alembic upgrade head` → run API.
