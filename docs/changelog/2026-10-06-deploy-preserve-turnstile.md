# Production deploy: keep Cloudflare Turnstile keys across deploys

**Date:** 2026-10-06
**Branch:** `ops/platform-deploy-preserve-turnstile`
**Surfaces:** `scripts/deploy` (deploy_production.py, camxora-production-remote.sh)
**Status:** fix implemented (not yet deployed)

## Summary

A production full install rebuilt `music_web` with **no Turnstile sitekey** and
rewrote `platform_api/.env` without the `CLOUDFLARE_TURNSTILE_*` keys, so the
`music.camxora.com` login page rendered **"Security check is unavailable"** and
users could not sign in. The installer now writes those keys from deploy
secrets, and the orchestrator exports them, so a routine deploy preserves them.

This is the same class of bug as
`2026-10-05-telegram-ops-deploy-env.md` (a `tee` heredoc dropped env keys).

## Why

Observed 2026-10-06 on production: `music_web/.env.production` contained only
`NEXT_PUBLIC_API_BASE_URL`, the built `.next` chunks contained no sitekey, and
`platform_api/.env` had no `CLOUDFLARE_TURNSTILE_*`. `TurnstileWidget` renders
the explicit error when the sitekey is empty at build time (the no-fallback rule
from `2026-10-05-music-web-turnstile-login-lockout.md`).

- `camxora-production-remote.sh` rewrites `platform_api/.env` and
  `music_web/.env.production` from heredocs that omitted the Turnstile keys.
- `deploy_production.py` did not export the Turnstile secrets to the remote
  installer, so adding them to the heredoc alone would be empty.

## What

- `camxora-production-remote.sh`:
  - `platform_api/.env` now includes `CLOUDFLARE_TURNSTILE_SITE_KEY`,
    `CLOUDFLARE_TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TURNSTILE_HOSTNAMES`.
  - `music_web/.env.production` now includes `NEXT_PUBLIC_CAMXORA_ENV=production`
    and `NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY` (the prebuild guard then
    enforces a real, non-sandbox sitekey instead of silently allowing an empty
    one).
  - the `.deploy-secrets` file preserves the three keys across runs.
  - all substitutions are unset-safe (`${VAR:-}`) under `set -u`.
- `deploy_production.py`: exports `CLOUDFLARE_TURNSTILE_SITE_KEY`,
  `CLOUDFLARE_TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TURNSTILE_HOSTNAMES` to the
  remote installer (they live in `.deploy/secrets.production.env`).

## Product impact

- A routine production deploy no longer breaks login at `music.camxora.com`.
- If the sitekey is ever missing, the `music_web` prebuild guard now fails the
  deploy loudly instead of shipping a bundle that locks every user out.

## Migration / deploy

No migration. The fix takes effect on the next `deploy_production.py` run.
Immediate restoration on 2026-10-06 was done with the existing hotfix:
`python scripts/deploy/apply_turnstile_production.py --rebuild-music-web`.

## Tests

- `python -m py_compile scripts/deploy/deploy_production.py`
- `bash -n scripts/deploy/camxora-production-remote.sh`
- Verified live after the hotfix: sitekey present in `.next/static`, `/login`
  200, `camxora-api` + `camxora-music` active.
