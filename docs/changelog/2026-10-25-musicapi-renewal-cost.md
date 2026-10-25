# musicapi: renewal cost visibility

## Summary

The admin console now shows what the Suno subscriptions cost to keep alive: the
Accounts table labels each paid account with its plan and monthly price, and the
dashboard totals the renewals due in the next 30 days.

Suno's `billing/info` already returns `plan.name` and `plan.monthly_price_usd`;
they were simply never mapped.

## Product impact

- **Accounts → Plan** reads `Premier Plan · $30/mo` instead of `paid`.
- **Dashboard** gains a `Renewals 30d (N)` card with the combined USD list price
  of the subscriptions charging inside the window.
- Free accounts are unchanged (`free`, no price).
- No user-facing change; no routing change.

## Technical impact

- `BillingInfo` types `plan` (`plan_key`, `name`, `level`, `monthly_price_usd`,
  `annual_price_usd`), `monthly_limit`, `monthly_usage`.
- `AccountHealth` / `AccountStatus` carry `planName` and `monthlyPriceUsd`
  (`null` when the plan price is 0/absent, i.e. a free plan).
- New pure helper `forecastRenewals(statuses, { withinDays, now })` in
  `src/pool.ts`: counts only live, active subscriptions inside the window and
  reports `count`, `monthlyUsd`, and `unpriced` (accounts whose price Suno did not
  report, so a partial total is visible).
- `GET /admin/accounts` adds `live_plan_name`, `live_plan_price_usd`.
- `GET /admin/stats` adds `renewal_forecast: { count, monthly_usd, unpriced }`.

## Files touched

- `musicapi/src/client.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/test/pool.test.ts`
- `musicapi/web-admin/app/admin/accounts/page.tsx`
- `musicapi/web-admin/app/admin/page.tsx`
- `docs/changelog/2026-10-25-musicapi-renewal-cost.md` (this file)

## Migration / deploy

No migration. Requires a redeploy of the core API and `web-admin`.

## Tests

- `npx tsx test/run.ts` — 127/127 pass, including two new cases: window
  boundaries (30 days inclusive), paused/pause-scheduled/past-due exclusion,
  already-billed dates, unpriced accounts, and the disabled-window case.
- `npx tsc --noEmit` clean in `musicapi` and `musicapi/web-admin`;
  `npx eslint` clean on the touched admin pages.
- Live check against the local pool: `Premier Plan`, `$30`, forecast
  `{ count: 1, monthlyUsd: 30, unpriced: 0 }`.

## Follow-ups

- Annual plans report `annual_price_usd`; once one exists, divide by 12 for the
  monthly forecast (or show both).
- `monthly_limit` / `monthly_usage` are typed but unused — a usage-vs-allowance
  column would show when a plan's credits are nearly spent.
