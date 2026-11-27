# Musicapi: spend credits that expire at renewal first

## Summary

Suno replaces a paid plan's monthly allowance on the renewal date, so credits
left on an account that renews soon are lost. Account selection now puts those
accounts ahead of richer ones, spending the soonest-expiring balance first.
Highest-credit-first still orders accounts inside the window.

## Product impact

- Fewer wasted credits: a paid balance is drained before the reset instead of
  disappearing while a later-renewing account is used.
- Admin console: `/admin/accounts` shows an **Expiring credits** badge (with a
  tooltip naming the renewal date and balance) on accounts the router will spend
  first.
- New admin-editable setting **"Spend expiring credits first (days before
  renewal)"** under *Suno concurrency*, env `SUNO_RENEWAL_WINDOW_DAYS`
  (default `2`, `0` disables).

## Technical impact

- `orderForDispatch` ranking is now: per-account in-flight cap → renewal window →
  `prefer_free` → highest effective balance (skipped when the strategy is `off`)
  → least in-flight.
- `resetsSoon()` counts only whole days ahead (`1..withinDays`). A date that
  already billed is excluded, as are free accounts, unknown/unreachable
  accounts, and `pastDue` / `paused` / `pauseScheduled` plans, which will not
  bill again.
- `/admin/accounts` computes `expiring_credits` with the same helper, window and
  credit floor as the dispatcher, and returns `renewal_window_days`, so the
  badge cannot drift from routing behaviour.
- No schema change and no new API calls: the decision uses the existing 30s
  `billing/info` health cache.

## Files touched

- `musicapi/src/pool.ts` — `resetsSoon`, dispatch rank, `orderCandidates` wiring
- `musicapi/src/config.ts` — `SUNO_RENEWAL_WINDOW_DAYS`
- `musicapi/src/runtimeSettings.ts` — admin field + apply
- `musicapi/src/server.ts` — `expiring_credits` / `renewal_window_days`
- `musicapi/web-admin/app/admin/accounts/page.tsx` — badge
- `musicapi/test/pool.test.ts` — boundary + ordering tests
- `musicapi/REQUIREMENTS.md`, `musicapi/.env.example` — docs

## Migration/deploy

- No database migration.
- Sandbox: `python scripts/deploy/sync_musicapi_sandbox.py`
- Production: `python scripts/deploy/deploy_musicapi_production.py --yes` from a
  clean checkout whose `HEAD` equals `origin/main`.
- Takes effect on the next dispatch after the API restarts; in-flight jobs keep
  their already-acquired account.

## Tests

- `npm run typecheck` — clean (`musicapi`, `musicapi/web-admin`)
- `npx tsx test/run.ts` — 204/204 pass, including six new cases: window
  boundary, already-billed and disabled-window exclusions, expiring account
  before a richer one, balance order inside the window, and the in-flight cap
  still winning.
- `npx eslint app/admin/accounts/page.tsx` — clean

## Follow-ups

- Annual plans expose only the annual charge date, so they never enter the
  window; revisit if Suno reports a monthly refresh date.
- Optional: a per-account "burn first" override, and highlighting the badge on
  the accounts page row rather than only in the status column.
