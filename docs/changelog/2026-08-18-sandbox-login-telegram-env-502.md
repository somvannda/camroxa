# Sandbox login restored after Telegram env 502

**Date:** 2026-08-18  
**Surfaces:** `platform_api` (sandbox only)  
**Branch:** sandbox ops restore (no production)

## Summary

Sandbox sign-in failed with **502 Bad Gateway** on `/api/v1/auth/login`. Nginx could not reach `127.0.0.1:8100` because `camxora-api` workers crashed during Settings load.

A Telegram ops setup wrote `PLATFORM_TELEGRAM_BOT_TOKEN`, `PLATFORM_TELEGRAM_CHAT_ID`, and `PLATFORM_TELEGRAM_OPS_ENABLED` into sandbox `.env` and restarted the API **before** `Settings` had those fields. Pydantic rejected the extras (`extra_forbidden`), workers never bound port 8100, and every login (music / app / admin / API) returned 502.

After commenting those env vars, login still returned 500 because the live auth router used `AccountLockedError` without importing it (same gap as 2026-08-17).

## Product impact

**Before:** Sandbox login failed with 502. Production login was unaffected.

**After:** Health is 200. Login returns a normal 401 for bad credentials.

## What was applied (sandbox only)

- Commented the three `PLATFORM_TELEGRAM_*` lines in `/opt/camxora/repo/platform_api/.env` (values kept).
- Imported `AccountLockedError` in the live `platform_api/routers/auth.py`.
- Restarted `camxora-api`. Telegram ops was **not** completed here.

## Tests

- `https://api.sandbox.camxora.com/health` → 200, `database: true`
- Login probes on API / music / app → 401 `AUTHENTICATION_ERROR`
