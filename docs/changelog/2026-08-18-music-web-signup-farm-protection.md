# Music Web free-credit farm protection

**Date:** 2026-08-18  
**Surfaces:** platform_api, music_web

## Summary

Public Music Web signup stays **open** (invite-only still skipped for `music_web`). Free-credit farming is limited by requiring Turnstile on web register, capping new accounts per IP, and enforcing one free-account song budget per network per day. The existing IP abuse helper was never wired to Redis, so those caps did not run in production.

## Product impact

- `music.camxora.com/register` remains public. Studio/desktop signup stays invite-only.
- Web register must pass Cloudflare Turnstile when the API secret is configured.
- Same network: at most **3 accounts per hour** and **5 per day**.
- Same network: at most **5 free songs per day**, shared across accounts (paid subscribers are unchanged).
- Signup error copy now shows the 429 message instead of a generic failure.

## Technical impact

- `configure_abuse_detection(redis)` runs at API startup.
- Geo/VPN blocking stays **off** so wiring Redis does not start country filters.
- Register uses `X-Forwarded-For` for Turnstile `remote_ip` and IP caps.
- Register attempts are rate-limited at 8/hour per IP (no-ops when the limiter is not configured, e.g. unit tests).

## Files touched

- `platform_api/middleware/abuse_detection.py`
- `platform_api/middleware/rate_limit.py`
- `platform_api/routers/auth.py`
- `platform_api/main.py`
- `platform_api/tests/test_abuse_detection.py`
- `platform_api/tests/test_auth_router.py`
- `music_web/src/lib/auth-api.ts`

## Migration/deploy

No migration. Deploy sandbox `platform_api` and `music_web`. Production only on request.

Optional ops lever (no code): lower `web_music_free_daily_credits` in `system_settings` (currently 50).

## Tests

- `test_register_music_web_skips_invite` still passes.
- `test_register_music_web_requires_turnstile_when_configured`
- IP hourly signup cap and daily generation cap unit tests
- Geo lookup is not called by default

## Follow-ups

- Production deploy only on request.
- Consider lowering daily free credits if organic signups still burn too much Suno.
