# 2026-08-23 — Wallet API inventory, admin recast verify, designed E2E

Sandbox only (`46.250.235.83`). Production not touched.

## Inventory

Living map: `docs/credits-only-api-platform-map.md`. There is no v4. CutLuy checkout stays `/api/v1/v2/...`. Designed cases: `docs/credits-only-e2e-cases-2026-08-23.md`.

## Admin recast verified on sandbox

- `/users`: no Tag. Plan = license then CutLuy web then Free. Credits = `credit_wallets`.
- `/licenses`: desktop + web rows, Source Desktop/Web. Cancel/Add-ons hidden on web.
- `/usage` `/user-spent` `/finance` stay three jobs. Grant issued = `v3_period_grant` + `v3_daily_grant` only (3000 on this pass; leftover 1726+1400 did not inflate it).
- User-spent 500 on sandbox was a stale service still calling `list_web_subscriptions_for_users`. Shipped local `user_spend_service.py` (unified `list_active_plans_for_users`). After hotfix: 200, CutLuy `starter_monthly` included.

## Designed E2E

See the results table in `docs/credits-only-e2e-cases-2026-08-23.md`. Local wallet/charge pytest: **35 passed**. Shared integer A02: leftover users v1 `/credits/balance` = v3 `/me/credits` (1726.08 / 1400.04 / 5180). v2 monthly+topup = 0.

## Not done

Production deploy, leftover mint on prod, live CutLuy buy, portal past email-confirm, another live Suno spend.
