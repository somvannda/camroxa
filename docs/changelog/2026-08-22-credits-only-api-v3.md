# Credits-only API v3 (2026-08-22)

## What shipped
New `/api/v3` billing door beside unchanged `/api/v1`. Desktop generate, Admin portal, CutLuy webhooks, and `GET /api/v1/plans/public` keep the old quota-first behavior.

v3 reads and writes the **same** `plans`, `credit_pricing`, `credit_wallets`, `licenses`, and fail-absorb counters Admin already uses.

## Endpoints
- `GET /api/v3/plans` / `GET|PATCH /api/v3/admin/plans/{id}`
- `GET /api/v3/plans/public` (`is_active AND is_public` only)
- `GET /api/v3/credits/pricing`
- `GET /api/v3/me/credits` and `GET /api/v3/users/{id}/credits`
- `POST /api/v3/billing/quote|charge|refund`
- `POST /api/v3/admin/billing/conversion/dry-run|apply` (apply needs `confirm=true`)
- Docs: `/api/v3/docs`

## Schema
Migration `116_credits_only_v3`: additive plan per-op columns, `credit_wallet_lots`, `billing_conversion_runs`.

## Rollback
Stop mounting the v3 routers. Do not run conversion apply while clients still generate on v1.

## Deploy
Sandbox: `platform_api` sync + `alembic upgrade head`. Production only on explicit ask.
