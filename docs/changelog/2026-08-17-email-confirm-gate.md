# Email confirmation gate

**Date:** 2026-08-17  
**Surfaces:** platform_api, user_portal, music_web

## Summary

Unconfirmed users could sign in and use authenticated product APIs (library likes, dashboard, billing, generation) because `email_confirmed` was display-only. Registration also dropped people into chrome that looked like the full app (music left sidebar, portal marketing nav). Confirmation is now a locked screen, and the API rejects other authenticated work until the email code is verified.

## Product impact

- After register/login, unconfirmed users stay on the 6-digit confirmation screen.
- That screen has no left sidebar, catalog rail, player, marketing nav, or dashboard links.
- Confirmed users continue to onboarding (user portal) or library (music portal) as before.

## Technical impact

- `get_auth_state` now returns `email_confirmed`.
- `get_current_user` allows only `/users/me`, `/profiles`, `/channel-setup/profiles-status`, `/auth/logout`, and `/auth/refresh` until the email is confirmed.
- User portal onboarding hydrates only `/users/me` before confirmation so those other calls are not made.
- Sandbox music portal `/verify-email` now uses a locked header with no left sidebar. Unconfirmed sessions are redirected there.

## Files touched

- `platform_api/middleware/auth.py`
- `platform_api/repositories/user_repo.py`
- `platform_api/tests/test_auth_middleware.py`
- `user_portal/src/components/auth/portal-marketing-shell.tsx`
- `user_portal/src/app/onboarding/wizard.tsx`
- `user_portal/src/components/dashboard/control-panel-provider.tsx`
- `user_portal/src/app/login/login-form.tsx`
- `user_portal/src/app/page.tsx`
- Sandbox-only: `music_web/src/components/shell-switcher.tsx` and login redirect (live music portal is ahead of this checkout)

## Migration/deploy

No migration. Deploy sandbox `platform_api`, `user_portal`, and `music_web`. Existing users already have `email_confirmed=true` from migration `057`.

## Tests

- `platform_api/tests/test_auth_middleware.py`: unconfirmed user can `GET /users/me`, cannot hit library likes.

## Follow-ups

- Production deploy only on request.
- Desktop studio already sends unconfirmed users to the portal; generation APIs now 403 if that gate is bypassed.
