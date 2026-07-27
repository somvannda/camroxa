# Admin set user password from Users table

**Date:** 2026-07-27  
**Status:** implemented (sandbox deployed)

## Summary

Admins can reset any user’s password from the Users list (key icon) or user detail Actions, without SSH/scripts. The API hashes the new password with the same complexity rules as self-service change, then revokes existing sessions.

## Product impact

- **Before:** Password resets required deploy scripts or DB access.
- **After:** Admins open Change password, enter a strong password twice, and the user can sign in immediately; old sessions are signed out.

## Technical impact

- `POST /api/v1/users/{user_id}/set-password` with body `{ "password": "..." }` (admin-only).
- Shared `_validate_password_complexity` (≥8 chars, upper, lower, digit).
- Admin portal: `useSetUserPassword` hook; dialog on users index + user detail.

## Files touched

- `platform_api/routers/users.py` — endpoint + request model + validation helper
- `platform_api/tests/test_users_router.py` — `TestAdminSetPassword`
- `admin_portal/src/hooks/use-users.ts` — `useSetUserPassword`
- `admin_portal/src/pages/users/index.tsx` — KeyRound action + dialog
- `admin_portal/src/pages/users/user-detail.tsx` — Change Password action + dialog

## Migration / deploy

- No DB migration.
- Sandbox: sync platform API + admin portal.

## Tests

- `pytest platform_api/tests/test_users_router.py::TestAdminSetPassword`

## Follow-ups

- Optional audit log entry for admin password resets (who/when).
