# Admin fail/retry absorb UI + configurable daily budget

**Date:** 2026-08-04  
**Status:** implemented  
**Branch:** `feature/admin-fail-absorb-ui`

## Problem

Core fail/retry absorb (platform absorbs plan-covered failed gens, daily Redis counter, `FAIL_BUDGET_EXCEEDED`) was already on `main`, but:

1. Admin portal UI to view/reset a user's counter was never committed (API restored 2026-08-03).
2. Max retries per user/day was env-only (`PLATFORM_DAILY_FAIL_ABSORB_BUDGET`), not editable in Settings.

## Fix

- **Settings → Fail / Retry Absorb:** set `daily_fail_absorb_budget` in `system_settings` (overrides env; clear to fall back).
- **User detail:** show today's used/budget/blocked + **Reset today**.
- **API:** `UsageEnforcementService.resolve_daily_fail_absorb_budget()` reads admin setting first, then env.

## Surfaces

- `platform_api` — enforcement + wiring
- `admin_portal` — settings tab + user detail card
