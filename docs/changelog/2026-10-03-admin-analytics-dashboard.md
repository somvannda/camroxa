# Admin analytics dashboard: trends, richer chart, sortable tables, CSV export

## Summary

The admin **Analytics** page (`web-admin /admin/analytics`) went from a bare
stat strip + a single revenue bar chart + three static tables to a dashboard:
period-over-period KPI deltas, a metric-switchable trend chart with success vs
failed stacking and hover tooltips, sortable/searchable breakdown tables, and
CSV export. The core API now returns a `previous_totals` aggregate so the deltas
compare against the equally long window immediately before the selected range.

No new frontend dependencies — the page stays on the existing glass/violet
Tailwind tokens.

## Product impact

- Admins immediately see whether requests, failures, credits, and revenue are
  trending up or down versus the previous period of the same length.
- The trend chart can switch between **Requests** (stacked success/failed),
  **Credits**, **Revenue**, and **Failures**, with per-day hover detail.
- Breakdown tables (endpoint / model / user) sort on every numeric column, show
  success-rate pills, revenue-share bars, and the user table is searchable.
- **Export CSV** downloads totals + all breakdowns + the daily series; **Refresh**
  re-fetches without changing the range.

## Technical impact

- `musicapi/src/server.ts` — `GET /admin/analytics` now also runs one aggregate
  over the prior window (`created_at > now() - 2N days AND <= now() - N days`)
  and returns `previous_totals` alongside `totals`. Same `credits_per_usd` rate.
- `musicapi/web-admin/app/admin/analytics/page.tsx` — reworked UI:
  - KPI cards with delta chips + sparklines; success rate shows percentage points.
  - `TrendChart` with metric selector, stacked bars, gridlines, date axis, hover tooltip.
  - `BreakdownTable` with client-side sort, search, success-rate pills, share bars.
  - CSV export, skeleton loading, retry-on-error, and request cancellation guard.
  - Uses `previous_totals` when present, falls back to first-half/second-half of
    the series if an older API response omits it.
  - Fixed the `react-hooks/set-state-in-effect` lint error in this file.

## Files touched

- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/analytics/page.tsx`
- `docs/changelog/2026-10-03-admin-analytics-dashboard.md`

## Deploy

- Sandbox API + web-admin only: `python scripts/deploy/sync_musicapi_sandbox.py`.
- No migrations. The API change is additive (`previous_totals`), so the old
  web-admin keeps working during a rolling update.

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run typecheck` (web-admin) → clean.
- `npx eslint app/admin/analytics/page.tsx` → clean.

## Follow-ups

- Not yet deployed to sandbox — the working tree contains unrelated in-flight
  commits/files, and the deploy script replaces the whole `musicapi/` tree, so
  deploy from an isolated branch once this task is the only change in the tree.
