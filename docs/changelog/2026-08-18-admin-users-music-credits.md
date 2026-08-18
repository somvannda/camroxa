# Admin Users list: Music plan, credits, and burned

**Date:** 2026-08-18  
**Surfaces:** `platform_api`, `admin_portal`  
**Branch:** `feature/admin-users-product-tag`

## Summary

The admin Users table was reading **desktop studio** data only:

- **Plan** came from `licenses` (Camxora desktop). Camxora Music plans live in
  `web_subscriptions`, so Music subscribers showed *No plan*.
- **Credits** came from `credit_wallets.balance` converted with `units_to_credits`
  (1 display credit = 10,000 micro-units). A leftover **400 units** renders as
  **0.04 cr**. That is not the Music pool (e.g. 1,377 / 1,400).

The list now joins active `web_subscriptions`, shows remaining/limit Music
credits, and adds a **Burned** column (`monthly_used` plus spent top-up).

## Product impact

- Music subscribers show their Music plan name and `remaining / limit`.
- **Burned** matches period consumption (monthly used + top-up spent).
- Studio-only rows show wallet credits (`X cr`) and wallet **Burned** (`X cr`
  from debit transactions). Music subscribers keep integer Music burned.

## Technical impact

- `GET /api/v1/users` adds `music_credits_remaining`, `music_credits_limit`,
  `credits_burned`. `plan_name` prefers the active Music plan when present.
- Studio wallet remains in `credit_balance` (tooltip on Music rows).

## Files touched

- `platform_api/routers/users.py`
- `admin_portal/src/pages/users/index.tsx`
- `admin_portal/src/types/models.ts`
- `admin_portal/CHANGELOG.md`
- `platform_api/CHANGELOG.md`

## Migration / deploy

- Deploy **platform_api** (file-scoped `users.py`) and **admin_portal** to sandbox.
- No database migration.

## Tests

- `kongsomvannda1987@gmail.com` should show the Music plan, ~1377 / 1400 credits,
  and burned ≈ 23 (not 0.04 cr / No plan).
