# musicapi: show the next renewal date for paid Suno accounts

## Summary

The admin console's **Suno Accounts** table now has a **Renews** column. It shows
Suno's own next-charge timestamp for each paid account, so an operator can see
when a subscription will renew (and when credits are due to refresh) without
logging into each Suno account.

## Product impact

- `/admin/accounts` (`admin.musicapi.camxora.com/admin/accounts`) gains a
  **Renews** column: `Nov 7, 2026 (in 13d)`.
- The relative hint turns amber when the charge is within 7 days or today, and
  reads `Nd ago` when the date has passed — i.e. a lapsed or paused subscription.
- Free accounts, and accounts whose live probe failed, render `—`.
- No user-facing change on `music.camxora.com` or `musicapi.camxora.com`.

## Technical impact

- Suno's `GET /api/billing/info/` already returns `renews_on` (with `period_end`
  as an equivalent fallback) — `src/pool.ts` simply was not mapping it through.
- `BillingInfo` types the new fields (`renews_on`, `period_end`, `period`,
  `is_paused`).
- `AccountHealth` / `AccountStatus` carry `renewsOn`; `markCreditExhausted`
  preserves it.
- `GET /admin/accounts` returns `live_renews_on`.
- The data rides the pool's existing 30 s health cache — no new outbound calls
  and no schema change.

## Files touched

- `musicapi/src/client.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/server.ts`
- `musicapi/web-admin/app/admin/accounts/page.tsx`
- `docs/changelog/2026-10-25-admin-accounts-renewal-column.md` (this file)

## Migration / deploy

No migration. Requires a redeploy of both the core API and `web-admin`; the
column stays empty (`—`) if only one of them is updated.

## Tests

- `npx tsc --noEmit` clean in `musicapi` and `musicapi/web-admin`.
- `npx eslint app/admin/accounts/page.tsx` clean.
- Verified against a live pooled account that Suno returns
  `renews_on: "2026-11-07T14:43:06Z"` for a Premier plan.

## Follow-ups

- Surface `is_paused` / `is_past_due` as a status badge if paused subscriptions
  become common.
- Optionally block routing to an account whose paid subscription has lapsed
  instead of only flagging the date.
