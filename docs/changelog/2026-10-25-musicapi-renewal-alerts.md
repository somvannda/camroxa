# musicapi: renewal alerts for paid Suno accounts

## Summary

The alert evaluator now watches paid Suno subscriptions. It warns before a
subscription's next charge and raises a critical alert when one is past due or
has lapsed, so an operator learns about it from Telegram instead of noticing
that an account stopped refreshing its monthly credits.

## Product impact

- New alert `renewal_soon` (warning): N paid accounts renew within the configured
  window (default **7 days**), listed with their renewal dates.
- New alert `subscription_past_due` (critical): an account's subscription is
  past due, or its renewal date has already passed.
- New admin setting **Alerts → Renewal warning (days)**; `0` disables the
  warning (past-due/lapsed detection stays on).
- The Alerts status tab gains **Renewing soon** and **Past due** counters.
- No user-facing change; no change to routing yet.

## Technical impact

- `AlertSettings.renewal_warning_days` (+ default `7`, coercion clamp `0..365`,
  patch validation). Stored in the existing `settings` document, so no migration.
- `AccountHealth` / `AccountStatus` carry `pastDue` (from `billing/info.is_past_due`)
  in addition to `renewsOn`.
- New pure helpers in `src/pool.ts`:
  - `parseRenewsOn(info)` — `renews_on` first, `period_end` fallback, normalised
    to ISO, `null` for free plans or unusable values.
  - `daysUntilRenewal(renewsOn, now)` — rounds up (6 hours away = 1 day), negative
    once passed.
- `evaluateAlerts()` inserts the two checks after the low-credit check and
  reports `summary.renewals_soon` / `summary.past_due`. Alert ids are stable, so
  the existing `type|severity` dedupe and `[RESOLVED]` messages keep working.

## Files touched

- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/test/pool.test.ts`
- `musicapi/web-admin/app/admin/settings/page.tsx`
- `docs/changelog/2026-10-25-musicapi-renewal-alerts.md` (this file)

## Migration / deploy

No migration. Requires a redeploy of the core API (alert evaluation) and
`web-admin` (setting + counters).

## Tests

- `npx tsx test/run.ts` — 125/125 pass, including four new cases: `renews_on`
  preference + ISO normalisation, `period_end` fallback, free-plan/invalid
  inputs, and `daysUntilRenewal` rounding/boundaries.
- `npx tsc --noEmit` clean in `musicapi` and `musicapi/web-admin`.
- `npx eslint` clean on the touched admin page.

## Follow-ups

- Badge `pastDue` / paused subscriptions in the accounts table (#2 of the plan).
- Decide whether routing should deprioritise a past-due account once the flag is
  observed in production.
- Persist the last known `renews_on` so the column survives a failed probe.
