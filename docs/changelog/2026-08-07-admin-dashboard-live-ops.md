# Admin dashboard live ops + money glance

## Summary

Redesigned the Admin Portal dashboard as a priority-first glance board: live system/worker health, provider credits remaining, money (income / COGS / profit / credits purchased), and top 10 spenders — without manual refresh for the critical signals.

## Product impact

- Admins see ops + money answers on open without digging into Finance / User Spent / Job Queue.
- Health, Suno balance, key balances, and job-queue metrics poll automatically.
- Top 10 spenders toggle between COGS and wallet spend (last 30 days).

## Technical impact

- Admin dashboard rewritten around sectioned components with independent loading/error.
- Provider key balances poll cached (`refresh=false`); force refresh uses `refresh=true`.
- Usage summary gains `credit_pack_revenue_cents` / `credit_pack_payment_count` from billing payments metadata.
- Shared `computeFinanceGlance` helper for dashboard money strip.

## Files touched

- `admin_portal/src/pages/dashboard.tsx`
- `admin_portal/src/components/dashboard/operations-status-hero.tsx`
- `admin_portal/src/components/dashboard/money-glance-strip.tsx`
- `admin_portal/src/components/dashboard/top-spenders-table.tsx`
- `admin_portal/src/components/dashboard/provider-key-balances-panel.tsx`
- `admin_portal/src/hooks/use-dashboard.ts`
- `admin_portal/src/hooks/use-job-queue.ts`
- `admin_portal/src/lib/finance-estimates.ts`
- `admin_portal/src/types/models.ts`
- `platform_api/repositories/credit_repo.py`
- `platform_api/routers/admin.py`

## Migration / deploy

- Deploy **platform_api** (usage summary fields) and **admin_portal** to sandbox.
- No DB migration.

## Tests

- `admin_portal` `finance-estimates` unit tests for glance helpers.
- Manual: open Admin Dashboard — live stamp advances; money + top 10 populate; force-refresh balances.

## Follow-ups

- Optionally refactor Finance page to call `computeFinanceGlance` directly.
- Split legacy `subscription_revenue_cents` into plan-only vs all cash if Finance needs stricter accounting.
