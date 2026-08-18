# Admin Users table shows product tags

**Date:** 2026-08-18  
**Surfaces:** `admin_portal`, `platform_api`  
**Branch:** `feature/admin-users-product-tag`

## Summary

The admin Users list (`/users`) now shows a **Tag** column for each account’s
product affiliation (`music_web` → Music, `studio` → Studio).

## Product impact

- Admins can tell Music-web signups from Studio (desktop / user portal) accounts
  without opening each row.

## Technical impact

- `User.products` is typed on the admin client.
- `GET /api/v1/users` returns `products` from `users.products` even when the
  User domain model does not include that field.

## Files touched

- `admin_portal/src/pages/users/index.tsx`
- `admin_portal/src/types/models.ts`
- `admin_portal/CHANGELOG.md`
- `platform_api/routers/users.py`

## Migration / deploy

- Deploy **admin_portal** and file-scoped `platform_api/routers/users.py`.
- No database migration. `users.products` must already exist on the target DB.

## Tests

- Open the admin Users table and confirm Music / Studio badges match known
  accounts (`{music_web}` vs `{studio}` vs empty).

## Follow-ups

- Optional product filter on the list query.
- Show the same badges on user detail.
