# Admin Users: durable Music credits + lifetime burn

**Date:** 2026-08-19  
**Surfaces:** `platform_api`, `admin_portal`  
**Branch:** `bugfix/admin-users-credit-burn-display`

## Summary

Production `https://admin.camxora.com/users` showed **0 cr** and Burned **—**
(or tiny negative studio micro-units). Yesterday's Music remaining/limit display
was correct until a later file-scoped `users.py` hotfix overwrote the live API
and dropped the Music credit helpers (`web_music_daily_usage` /
`web_subscriptions`).

Even with those helpers restored, Burned was **today only**. After Phnom Penh
midnight the daily pool resets, so yesterday's 466 credits vanished from the
table. Free-user **Credits** stay today's used / 50. **Burned** is now lifetime
`SUM(credits_used)` so the column does not wipe every morning.

Studio wallet fallback uses `abs(debit units)` because production debit amounts
are stored signed (`-82` units → `-0.0082 cr`).

## Product impact

- Music free users: Plan **Free**, Credits `today / 50`, Burned = all days.
- Example: 25 credits yesterday, 0 today → Credits `0 / 50`, Burned `25`.
- Paid Music subscribers still use `web_subscriptions` period used / granted.
- Studio-only rows never show negative burn.

## Technical impact

- `GET /api/v1/users` and `GET /api/v1/users/{id}/details` aggregate
  `web_music_daily_usage` as `today_used` + `lifetime_used`.
- Admin Credits column uses `limit - remaining` (today), not `credits_burned`.
- Production hotfix must merge into the live `users.py` (keep `avatar_url`);
  do not tarball-sync a local file that lacks avatar helpers.

## Files touched

- `platform_api/routers/users.py`
- `platform_api/tests/test_users_router.py`
- `admin_portal/src/pages/users/index.tsx`
- `admin_portal/src/pages/users/user-detail.tsx`
- `admin_portal/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration / deploy

No migration. File-scoped sandbox sync of the API users router and admin user
list/detail. Production: patch live `users.py` (preserve `avatar_url`) then
rebuild admin.

## Tests

- Music-tagged, today 10 / lifetime 10 → 40 / 50, burned 10.
- Today 0 / lifetime 25 → 50 / 50 remaining, burned 25.
- No usage row → 50 / 50, burned 0.
- Studio debit `-82` units → burned `0.0082`, not negative.
