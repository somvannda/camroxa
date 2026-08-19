# Empty Music product tag on an existing subscriber

**Date:** 2026-08-18  
**Surfaces:** `platform_api`  
**Branch:** `feature/admin-users-product-tag`

## Summary

`kongsomvannda1987@gmail.com` showed **no Tag** on the admin Users table.
`users.products` was `{}`. The account has an active Camxora Music plan
(`starter_monthly`) and no desktop license or channel profiles.

Tags are written at **register** (`product` / `X-Signup-Product`) and when
studio onboarding finishes. Buying a Music plan did **not** add `music_web`.
This user was created on 2026-08-17 after the `products` column existed
(default empty) but without a persisted signup tag — the only such row.

## Fix

- Backfill `music_web` onto empty-tag users who already have `web_subscriptions`.
- Activating a Music subscription now appends `music_web` to `users.products`.

## Files touched

- `platform_api/services/v2/subscription_service.py` (sandbox: tag on payment
  activation)
- `platform_api/CHANGELOG.md`

## Migration / deploy

- Sandbox SQL backfill + API restart. No Alembic revision.
