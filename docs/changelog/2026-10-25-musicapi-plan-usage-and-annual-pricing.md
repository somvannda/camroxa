# musicapi: plan usage and annual pricing

## Summary

Two follow-ups that finish the renewal/plan visibility work: the Accounts table
now shows how much of a paid plan's monthly allowance has been used, and the
renewal forecast prices **annual** subscriptions at their monthly equivalent
instead of ignoring them.

## Product impact

- **Accounts → Credits** shows the remaining balance with a muted
  `7,270 / 10,000 used` line beneath it for paid accounts. Free accounts report
  their own (much smaller) allowance — Suno returns `monthly_limit = 100` for
  them — so they show e.g. `10 / 100 used` rather than a bare balance. That is
  accurate and intentional; this entry originally said "unchanged", which the
  live probe disproved (see `musicapi/docs/renewal-routing-proposal.md`).
- **Dashboard → Renewals 30d** now includes annual plans, normalised to
  `annual / 12`, so a yearly subscriber no longer looks free in the forecast.
- Plan labels stay as before (`Premier Plan · $30/mo`).

## Technical impact

- New pure helper `monthlyPlanPriceUsd(info)` in `src/pool.ts`: monthly price
  when Suno reports one; otherwise `annual_price_usd / 12` when the cadence is
  `year`; `null` for free plans (price 0) and incomplete payloads.
- `AccountHealth` / `AccountStatus` carry `monthlyLimit` and `monthlyUsage`
  (`null` on free plans / when unreported); `markCreditExhausted` and the probe
  failure path keep them coherent.
- `GET /admin/accounts` adds `live_monthly_limit` / `live_monthly_usage`.
- The Credits cell renders the allowance line only when a limit is known.
- `forecastRenewals` is unchanged — it already sums `monthlyPriceUsd`, which now
  reflects annual plans.

## Files touched

- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/test/pool.test.ts`
- `musicapi/web-admin/app/admin/accounts/page.tsx`
- `docs/changelog/2026-10-25-musicapi-plan-usage-and-annual-pricing.md` (this file)

## Migration / deploy

No migration. Requires a redeploy of the core API and `web-admin`.

## Tests

- `npx tsx test/run.ts` — 130/130 pass, including three new cases: monthly price
  preferred, annual normalised (with 2-dp rounding), and free/incomplete payloads
  returning `null`.
- `npx tsc --noEmit` clean in `musicapi` and `musicapi/web-admin`;
  `npx eslint` clean on the touched page.
- Live check against the real pool: `Premier Plan`, `$30/mo`, allowance
  `7,270 / 10,000` with `2,730` credits remaining (the numbers agree).

## Follow-ups

- If an annual plan ever appears, consider labelling it `$288/yr` in the Plan
  column instead of the monthly equivalent.
- Usage is period-to-date from Suno; a percentage bar would need the period
  start, which the payload does not expose.
