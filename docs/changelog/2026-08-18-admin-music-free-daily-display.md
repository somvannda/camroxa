# Admin Users: Free Music daily credits

**Date:** 2026-08-18  
**Surfaces:** `platform_api`, `admin_portal`  
**Branch:** `feature/admin-music-free-daily-display`

## Summary

Music users on the free daily pool (50 credits/day, no `web_subscriptions` row)
showed **0 cr**, **No plan**, and Burned as studio micro-units (`-0.001 cr`).
The 50/day allowance is a virtual pool in `web_music_daily_usage`, not the
studio wallet.

Admin now infers **Free** for Music-tagged users without a paid Music plan
and shows today's remaining / 50 plus whole-credit burned. No wallet grant and
no Free subscription row (that would switch charging onto the monthly pool).

## Product impact

- Music free users: Plan **Free**, Credits `used / 50` (e.g. `10 / 50`), Burned = today's
  `credits_used` (e.g. 10, not `-0.001 cr`).
- Paid Music subscribers unchanged (`remaining / limit` from `web_subscriptions`).
- Studio-only rows still use the wallet.

## Technical impact

- `GET /api/v1/users` and `GET /api/v1/users/{id}/details` read
  `web_music_daily_usage` for the current `Asia/Phnom_Penh` billing day and
  `system_settings.web_music_free_daily_credits` (default 50).
- Detail response adds `music_credits_remaining`, `music_credits_limit`,
  `credits_burned`.

## Files touched

- `platform_api/routers/users.py`
- `platform_api/tests/test_users_router.py`
- `admin_portal/src/pages/users/user-detail.tsx`
- `admin_portal/src/types/models.ts`
- `admin_portal/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration / deploy

No migration. File-scoped sandbox sync of the API users router and admin user
list/detail. Production only on request.

## Tests

- Music-tagged, no sub, usage 10 → Free, 40 / 50, burned 10.
- Same with no usage row → 50 / 50, burned 0.
- Paid Music sub still wins over Free inference.
- Studio-only still uses wallet + `units_to_credits`.
