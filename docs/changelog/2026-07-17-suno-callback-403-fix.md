# Suno callback 403 fix — songs stuck pending despite Suno success

**Date:** 2026-07-17  
**Status:** implemented (sandbox deployed)

## Summary

Suno provider webhooks to `/api/v1/callbacks/suno` were returning **403 Forbidden** on sandbox because Suno sends a non-HMAC signature header while `PLATFORM_SUNO_CALLBACK_HMAC_SECRET` is configured. Invalid signatures were rejected before the IP allowlist was checked, so successful Suno generations never updated song status or MP3 URLs until the desktop client happened to poll `/music/downloads/pending` (reconcile).

## Product impact

**Before:** User sees success in Suno provider logs; CAMXORA history stays on Draft ready / Suno pending; MP3s do not download until reconcile runs (requires app open + download coordinator polling).

**After:** Suno callbacks from allowlisted provider IPs are accepted even when signature headers do not match our HMAC. History refresh also triggers reconcile so status catches up without waiting for MP3 sync.

## Technical impact

- **API:** `_validate_callback_request` falls through to IP allowlist when HMAC validation fails but client IP is in `PLATFORM_SUNO_CALLBACK_ALLOWED_IPS`.
- **API:** `GET /music/history` calls `reconcile_pending_suno_tasks` before loading rows.
- **Evidence:** Sandbox nginx showed `POST /api/v1/callbacks/suno` → 403 from Suno IPs `47.89.217.55`, `47.77.231.163`, `47.251.163.235` on 2026-07-17.

## Files touched

- `platform_api/routers/callbacks.py`
- `platform_api/routers/music_history.py`
- `platform_api/wire_dependencies.py`
- `platform_api/tests/test_callback_auth_and_refund_guard.py`
- `platform_api/tests/test_music_history_router.py`
- `scripts/deploy/diag_suno_client_gap_sandbox.py`

## Migration / deploy

- Deploy `platform_api` to sandbox via `scripts/deploy/sync_platform_api_sandbox.py` (done).
- No DB migration.
- Production: deploy same API change; verify nginx shows 200 for Suno callback POSTs.

## Tests

- `pytest tests/test_callback_auth_and_refund_guard.py tests/test_music_history_router.py tests/test_callbacks_router.py tests/test_suno_audio_resolver.py` — 20 passed.

## Follow-ups

- Suno lyrics callbacks hit `/api/v1/callbacks/suno-lyrics` → 404 (endpoint not implemented; lyrics flow uses polling today).
- Consider server-side periodic reconcile for users who never open the desktop app.
