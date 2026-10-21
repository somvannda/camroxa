# musicapi: revert the monthly V6-Mini free allowance

## Summary

The 50-credit monthly allowance does not belong on the musicapi surface. It was
built and deployed to `musicapi.camxora.com`, but the consumer product is
`music.camxora.com`, which runs on `platform_api` / `music_web` and already has
its own Free plan and Telegram spend feed.

musicapi is reverted to paid-only credits: a new account must buy a pack before
generating, and V6-Mini is charged from the normal `pricing` row like every
other model. The 50/month V6-Mini allowance will be implemented on
`music.camxora.com` instead.

## Product impact

- No free credits on signup at `musicapi.camxora.com`.
- V6-Mini costs 10 credits from the user's purchased balance.
- V6-Mini routing returns to the pre-feature `prefer_free` default (free Suno
  accounts first, paid fallback), instead of the hard `free_only` policy.
- Existing purchased balances are untouched.

## Technical impact

- Reverts the feature merge `2b14c69a` (PR #415): `freeMonthly` config and admin
  group, allowance tables/columns, allowance charging/refund logic, `/models`
  and `/me/billing` allowance fields, playground/billing allowance UI, and the
  related tests.
- Migrations `0034`-`0036` are kept in the repo because they were applied to
  production.
- New `0037_drop_free_allowance.sql` drops `monthly_allowances`,
  `jobs.allowance_credits` / `allowance_period`,
  `usage_logs.allowance_credits`, and the model-scoped V6-Mini pricing row.
- Uncommitted "free premium previews" work found in the shared worktree was
  parked on local branch `wip/musicapi-free-previews` rather than discarded.

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/models.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/runtimeSettings.ts`
- `musicapi/src/server.ts`
- `musicapi/test/*`
- `musicapi/web-user/*`
- `musicapi/web-admin/app/admin/pricing/page.tsx`
- `musicapi/.env.example`
- `musicapi/migrations/0037_drop_free_allowance.sql`
- `docs/changelog/2026-10-21-musicapi-revert-free-allowance.md` (this file)

## Migration / deploy

- Apply `0037_drop_free_allowance.sql` to sandbox and production.
- The forward migrations `0034`-`0036` remain recorded in `schema_migrations`.
- Deploy via the normal musicapi sandbox → production chain.

## Tests

- `npm run test:unit` → 120/120 pass.
- `tsc --noEmit` clean in `musicapi` and `web-user`/`web-admin`.

## Follow-ups

- Implement the 50/month V6-Mini allowance on `music.camxora.com`
  (`platform_api` / `music_web`), where every burn is already reported to
  Telegram via `notify_web_music_spend`.
- The parked `wip/musicapi-free-previews` branch can be deleted if the preview
  concept is not needed on the API surface.
