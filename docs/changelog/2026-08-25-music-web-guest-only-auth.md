# Guest-only login and register on music web

**Date:** 2026-08-25  
**Surfaces:** music_web

## Summary

Signed-in listeners could still open `/login` and `/register` and see the auth forms (sidebar already showed the account). Those routes are now guest-only: any session is redirected away before the form renders.

## Product impact

- Logged-in users who visit `/login` or `/register` go to **Create** (`/create`).
- A safe `?next=` in-app path is honored (auth paths like `/register` are ignored).
- Unconfirmed sessions go to `/verify-email` instead of another signup form.

## Technical impact

- Shared `destinationForSignedInUser()` decides Create vs verify-email.
- `GuestOnly` wraps both pages and hides the form while the session is loading or redirecting.

## Files touched

- `music_web/src/lib/auth-redirect.ts`
- `music_web/src/lib/auth-redirect.test.ts`
- `music_web/src/components/guest-only.tsx`
- `music_web/src/app/login/page.tsx`
- `music_web/src/app/register/page.tsx`
- `music_web/CHANGELOG.md`
- `scripts/deploy/hotfix_music_web_guest_only_auth_sandbox.py`

## Migration / deploy

No schema change. Rebuild sandbox music_web only.

```bash
python scripts/deploy/hotfix_music_web_guest_only_auth_sandbox.py
```

File-scoped music_web only (login/register + guest helper). Production only when asked.

Production only when asked.

## Tests

- `npx tsx --test music_web/src/lib/auth-redirect.test.ts`
- Manual: signed in as Duke, open `/register` and `/login` → Create (or verify-email if unconfirmed). Signed out, forms still work.

## Follow-ups

- None.
