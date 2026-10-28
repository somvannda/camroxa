# musicapi: surface past-due and paused paid accounts

## Summary

The Accounts page and the dashboard now carry Suno's subscription state, so a
paid account that is behind on payment, paused, or set to stop renewing is
visible as a badge instead of only as a date in the **Renews** column.

## Product impact

- Accounts table status badges gain **Past due** (danger), **Paused** and
  **Won't renew** (warning). An account showing one of these is no longer also
  labelled **Healthy**, because its monthly credits will not refresh.
- Dashboard account-health chips gain **Past due** and **Paused / won't renew**,
  matching the Accounts page counters.
- Renewal alerts no longer fire `renewal_soon` / `subscription_past_due` for a
  paused or pause-scheduled plan — that date will not charge, and the badge
  already explains why.
- No user-facing change; routing is unchanged.

## Technical impact

- `BillingInfo` types `is_pause_scheduled` and `is_past_due` explicitly.
- `AccountHealth` / `AccountStatus` carry `paused` and `pauseScheduled` alongside
  `pastDue`.
- `GET /admin/accounts` adds `health.past_due`, `health.paused`,
  `health.pause_scheduled`.
- `GET /admin/stats` adds `account_health.past_due` and `account_health.paused`
  (a pause-scheduled account counts as paused), and excludes both from
  `healthy` so the overview and the accounts table cannot disagree.
- `evaluateAlerts()` skips paused/pause-scheduled accounts when computing
  `renewal_soon` and lapsed subscriptions.

## Files touched

- `musicapi/src/client.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/accounts/page.tsx`
- `musicapi/web-admin/app/admin/page.tsx`
- `docs/changelog/2026-10-25-musicapi-account-subscription-flags.md` (this file)

## Migration / deploy

No migration. Requires a redeploy of the core API and `web-admin`; the new
badges stay hidden until both are updated.

## Tests

- `npx tsx test/run.ts` — 125/125 pass.
- `npx tsc --noEmit` clean in `musicapi` and `musicapi/web-admin`.
- `npx eslint` clean on the touched admin pages.

## Follow-ups

- Watch `is_past_due` / `is_paused` in production before letting routing
  deprioritise those accounts — a transient flag should not shrink the pool.
- Persist the last known `renews_on` so the Renews column survives a failed
  probe.
