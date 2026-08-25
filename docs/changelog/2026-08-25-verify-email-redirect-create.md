# Send confirmed music-web users to Create

**Date:** 2026-08-25  
**Surfaces:** music_web, platform_api

## Summary

After the email confirmation code succeeded, users landed on `/register` instead of `/create`, and a verified session was not treated as logged in. Entering the code again after the email was already verified returned “invalid code”.

This change is based on current `main` (API v3 already merged). Music web keeps `/api/v3/auth/*`. The shared `auth` router is updated only for verify-email cookies; billing/v3 wallet routes are untouched.

## Product impact

- Confirming the 6-digit code logs the user in and opens Create.
- Already-verified sessions skip the code screen and go to Create.
- Leftover `?next=/register` (or `/login` / `/verify-email`) is ignored.

## Files touched

- `platform_api/routers/auth.py` (`POST /auth/verify-email` only)
- `platform_api/tests/test_auth_router.py`
- `music_web/src/lib/auth-redirect.ts`
- `music_web/src/lib/auth-api.ts` (return type only; still `/api/v3`)
- `music_web/src/components/shell-switcher.tsx`
- `music_web/src/app/verify-email/page.tsx`
- `music_web/src/app/register/page.tsx`
- `music_web/src/app/login/page.tsx`

## Migration/deploy

No schema change. Dual-mounted at `/api/v1` and `/api/v3`. Production only when asked.
