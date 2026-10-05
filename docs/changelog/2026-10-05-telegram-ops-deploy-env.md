# Ops Telegram: keep the feed env across production deploys

**Date:** 2026-10-05
**Surfaces:** `scripts/deploy`
**Branch:** `fix/telegram-ops-deploy-env`

## Summary

A production deploy rewrote `platform_api/.env` without the
`PLATFORM_TELEGRAM_*` variables, so `get_telegram_ops_service()` returned
`None` on production and the whole ops activity feed (signups, logins,
payments, credit spends, `/stats`, the daily burn report) went silent. The
full-stack installer now writes those variables from deploy secrets, and
`deploy_production.py` exports them so the installer can. The production
hotfix script's embedded-Python step is also fixed (it aborted before
writing anything).

## Why

Observed 2026-10-05: no Telegram message for a login or a music generation.
A read-only probe of the production host showed `platform_api/.env` had
`PLATFORM_ENVIRONMENT=production` but no `PLATFORM_TELEGRAM_*` keys at all;
hooks, `config.py` fields, and the DB kill-switch were all fine.

- `scripts/deploy/camxora-production-remote.sh` rewrites
  `platform_api/.env` from a `tee` heredoc that omitted the Telegram keys.
- `scripts/deploy/deploy_production.py` did not export the Telegram secrets
  to the remote installer, so adding them to the heredoc alone would be empty.
- `scripts/deploy/hotfix_telegram_ops_production.py` used a non-raw f-string
  for a `cmd` that embeds a `\n` inside a Python heredoc; the f-string turned
  it into a real newline, so the remote Python died with `SyntaxError` before
  the env write / restart.

## What

- `camxora-production-remote.sh`: the generated `platform_api/.env` now
  includes `PLATFORM_TELEGRAM_BOT_TOKEN`, `PLATFORM_TELEGRAM_CHAT_ID`, and
  `PLATFORM_TELEGRAM_OPS_ENABLED`, sourced from `PLATFORM_TELEGRAM_*` then
  `TELEGRAM_*`; ops-enabled defaults to `true`. The defaults are unset-safe
  under `set -u`.
- `deploy_production.py`: adds the Telegram secret keys to the exported set
  passed to the remote installer (`PLATFORM_TELEGRAM_BOT_TOKEN`,
  `PLATFORM_TELEGRAM_CHAT_ID`, `PLATFORM_TELEGRAM_OPS_ENABLED`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
- `hotfix_telegram_ops_production.py`: `cmd = f"""` → `cmd = rf"""` so the
  embedded `\n` stays literal and the heredoc Python parses.

## Product impact

- A routine production full install no longer silently disables the ops
  Telegram activity feed.
- No customer-facing change.

## Migration / deploy

No migration. This only changes deploy scripts. The live production feed was
restored separately on 2026-10-05 (the three env vars written, then
`camxora-api` + workers restarted and a test ping sent); a future full install
now preserves it.

## Tests

- `python -m py_compile scripts/deploy/deploy_production.py scripts/deploy/hotfix_telegram_ops_production.py`
- `bash -n scripts/deploy/camxora-production-remote.sh`
