# musicapi: monthly scoped V6-Mini allowance (universal after a same-month purchase)

## Summary

Every CAMXORA account now receives **50 credits per calendar month (UTC)** that
can only be spent on **V6-Mini** (`chirp-goose`). V6-Mini costs 10 credits per
request, so the grant is 5 requests / 10 songs (Suno returns two versions per
request). The grant resets on the 1st, unused credits expire, and the balance
never carries over — a free user can never hold more than 50.

Purchased pack credits are separate and universal. If a user buys any credit
pack **during the same month**, the remaining monthly allowance also becomes
universal for that month, so it can pay for V6 / V6-WILD; the next month starts
V6-Mini-only again unless they purchase again.

V6-Mini always runs on the **free Suno account pool**, even when a paying user
funds it with purchased credits or unlocked allowance. V6 / V6-WILD stay on paid
Suno accounts. A failed generation refunds both the allowance and the purchased
portion.

## Product impact

- Zero-balance users can generate 5 V6-Mini tracks/month (10 songs) without
  buying credits.
- Burning the 50 with no pack blocks generation until the next month or a pack
  purchase.
- Buying a pack mid-month upgrades the remaining allowance to universal for that
  month (a loyalty perk, not permanent).
- The allowance and purchased balance are shown separately in billing and the
  playground; models the combined balance cannot cover are locked with a
  buy-credits CTA.
- An admin toggle can allow a dead free pool to fall back to a paid Suno account
  (off by default, so free credits never spend paid Suno credits).

## Technical impact

- `src/config.ts`: `freeMonthly { enabled, model, credits, allowPaidFallback }`
  (`FREE_MONTHLY_*`, defaults true / chirp-goose / 50 / false).
- `src/runtimeSettings.ts`: new **Settings → Integrations → Free monthly
  (V6-Mini)** group, applied live with no restart.
- `src/models.ts`: `isAllowanceModel`, `canSpendAllowance` (purchase unlocks
  premium models), `freeModelRoutingPolicy` (free-only unless fallback).
- `src/server.ts`:
  - `ensureAllowance` lazily mints a row per UTC month (also on Google sign-in).
  - `consumeAllowance` / `refundAllowance` are atomic guarded updates.
  - `allowanceUniversal` checks for a `purchase` ledger row **inside the current
    period**, so the unlock is month-scoped.
  - `chargeForMusic` spends allowance first, charges the remainder to purchased
    credits, refunds the allowance if the purchased charge fails, and picks
    `free_only` for V6-Mini (`prefer_free` only with the admin fallback).
  - Jobs store `allowance_credits` / `allowance_period`; `settleCredits` refunds
    the allowance on failure and only moves the purchased portion through the
    wallet.
  - `GET /models` returns per-model `credits` + `allowance_model` and an
    `allowance` block; `/me/billing`, `/v1/credits` and `get-credits` return the
    current allowance with `universal`.
  - `usage_logs.allowance_credits` records how much of a successful job came from
    the allowance.
- `src/pool.ts`: `free_only` policy and `matchesPolicy` (hard free/paid filters).
- `web-user`: model prices, allowance-aware locks, buy-credits CTA, allowance
  card in billing, docs updated.
- `web-admin`: pricing note; the free-monthly settings tab is generated from the
  backend group definition.

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/models.ts`
- `musicapi/src/pool.ts`
- `musicapi/src/runtimeSettings.ts`
- `musicapi/src/server.ts`
- `musicapi/test/credit-gate.test.ts`
- `musicapi/test/models.test.ts`
- `musicapi/test/pool.test.ts`
- `musicapi/web-user/app/dashboard/playground/page.tsx`
- `musicapi/web-user/app/dashboard/billing/page.tsx`
- `musicapi/web-user/app/docs/page.tsx`
- `musicapi/web-user/lib/api.ts`
- `musicapi/web-admin/app/admin/pricing/page.tsx`
- `musicapi/migrations/0034_free_monthly_allowance.sql`
- `musicapi/migrations/0035_usage_allowance.sql`
- `musicapi/migrations/0036_allowance_no_carryover.sql`
- `musicapi/.env.example`
- `docs/changelog/2026-10-20-musicapi-monthly-mini-allowance.md` (this file)

## Migration / deploy

- `0034_free_monthly_allowance.sql` — `monthly_allowances`, `jobs.allowance_credits`
  / `allowance_period`, and `pricing (music, chirp-goose) = 10`.
- `0035_usage_allowance.sql` — `usage_logs.allowance_credits`.
- `0036_allowance_no_carryover.sql` — `CHECK (used <= granted)`.
- Sandbox deploy (`sync_musicapi_sandbox.py`) applied all three and restarted the
  API, web-user and web-admin; `/health`, `/models`, and both portals returned
  200.
- Production requires the normal explicit production gate; migrations are
  forward-only.

## Tests

- `npm run test:unit` → 97/97 pass.
- `tsc --noEmit` clean in `musicapi`, `web-user`, `web-admin`.
- Local live checks: allowance mint/refund, same-month purchase unlock, old
  purchase does not unlock, no carry-over (old month's 50 ignored), DB rejects
  `used > granted`.
- Sandbox live check: V6-Mini request was admitted with `allowance_credits=10`;
  the free account (`acct-1`) failed with "no active Clerk session", the job
  errored, and the allowance was refunded to 50/50 with purchased credits
  untouched.

## Follow-ups

- Refresh the free Suno account cookie: both local and sandbox `acct-1` have a
  dead Clerk session, so strict `free_only` V6-Mini runs currently fail (and
  refund). Either refresh the cookie or enable **Allow paid-account fallback**.
- Production free account status is unknown; verify before deploying.
- Allowance consumption is recorded in `usage_logs.allowance_credits`, but
  `credit_transactions` only records the purchased portion. Add an allowance
  ledger type if revenue reporting needs to separate free-tier traffic.
- The unlock is month-scoped and based on purchase rows; a refunded purchase does
  not re-lock that month.
