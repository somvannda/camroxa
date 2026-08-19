# Fix Turnstile env var loading (CLOUDFLARE_* vs PLATFORM_*)

**Date:** 2026-08-16

## Problem

Login/register returned 500 on sandbox because Turnstile verification failed with `missing-input-secret`.
API logs showed `Expected hostnames: set()` even after adding vars to `platform_api/.env`.

## Root cause

`Settings` uses `env_prefix="PLATFORM_"`, so pydantic looked for:
- `PLATFORM_CLOUDFLARE_TURNSTILE_SECRET_KEY`

But secrets and `.env` used Cloudflare's standard names:
- `CLOUDFLARE_TURNSTILE_SECRET_KEY`

The secret key and hostnames were never loaded into the running API.

## Fix

- `platform_api/config.py`: map Turnstile fields to `CLOUDFLARE_*` env names via `AliasChoices` (also accepts `PLATFORM_*` fallback).
- Deployed to sandbox and verified settings load correctly on server.

## Verification

```text
secret_set: True
hostnames: music.sandbox.camxora.com,localhost,127.0.0.1
```
