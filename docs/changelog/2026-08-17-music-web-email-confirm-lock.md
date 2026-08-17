# Lock music-web Create until email is confirmed

**Date:** 2026-08-17  
**Surfaces:** platform_api, music_web

## Summary

Unconfirmed users could leave `/verify-email` (or close that screen) and open `/create` with the full app shell. Generation APIs accepted the session. Confirmation is now required on both the UI and the API.

## Product impact

- Unconfirmed sessions stay on the verify-email screen with no sidebar, Create, or Open app links.
- Typing `/create` or using a leftover tab redirects back to verify-email.
- Generate / draft / styles return 403 until the email code is verified.

## Technical impact

- `get_auth_state` includes `email_confirmed`.
- `get_current_user` allows only profile/session paths until confirmed.
- Music web shell uses a locked header (logo + Sign out) for unconfirmed users.

## Files touched

- `platform_api/middleware/auth.py`
- `platform_api/repositories/user_repo.py`
- `platform_api/tests/test_auth_middleware.py`
- `music_web/src/components/shell-switcher.tsx`
- `music_web/src/app/login/page.tsx`
- `music_web/src/components/likes-provider.tsx`

## Migration/deploy

No schema change. File-scoped sandbox hotfix of the files above. Production stays untouched until asked.
