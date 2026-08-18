# Admin user-detail 500: missing upload_path_exists import

**Date:** 2026-08-18  
**Surfaces:** platform_api (production)

## Summary

Admin user detail (`GET /api/v1/users/{id}/details`) returned 500 for studio users who have channel profiles. Production `users.py` calls `upload_path_exists()` while building profile summaries, but the import was replaced with avatar helpers (`resolve_upload_path`, `uploads_root`) and `upload_path_exists` was dropped. That raises `NameError` only when the user has at least one channel profile.

Music-web users with no profiles still loaded. Sandbox already imports `upload_path_exists` and was not affected.

## Product impact

- Admin → Users → open a studio account with channel profiles showed a 500 / failed to load user.
- Example: Hai Chamnan (`edmbass1@gmail.com`).

## Technical impact

- Restore `upload_path_exists` on the production `upload_paths` import.
- Do not replace the live production `users.py` with this checkout; this tree is missing later avatar / music-credit fields that production already has.

## Files touched

- Production-only: `/opt/camxora/repo/platform_api/routers/users.py` (import line)
- `scripts/deploy/hotfix_admin_user_details_upload_path_production.py`

## Migration/deploy

No migration. File-scoped production import patch + `camxora-api` restart.

## Tests

- Open `https://admin.camxora.com/users/ad6eda59-18f0-4ffb-b80e-fdae60028980` — page should load.
- Open a music-web user without profiles — still loads.
