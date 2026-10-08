# musicapi: free generation endpoints require a funded account

## Summary

A customer with **0 credits** could still run the free (0-cost) generation
endpoints and their derivative flows — for example `timestamped lyrics` — with
no balance at all. The admission guard everywhere was `if (cost > 0 && !key)`,
so when `cost === 0` the request proceeded with no key and no credits; on the
API-key surface `charge(key, 0)` likewise returned true at 0 credits.

"Free" now means **free in price, but only for funded customers**: free
generation endpoints require a minimum account balance and are still never
charged.

## Product impact

- A 0-credit / never-paid account can no longer run free generation or its
  derivative flows. The rejection is HTTP 402 with the message
  `"Insufficient credits."` (unchanged wording; on `/api/v1` it is still remapped
  to 429 for sunoapi.org parity).
- Paying customers keep free operations for free — the floor is a gate on
  admission, not a charge: satisfied balances are not deducted.
- Paid endpoints are unaffected and keep their own per-cost gate (e.g. `sounds`
  still needs 3 credits).
- Read/detail/download routes stay open to a drained customer, so someone who
  spent down to 0 can still view and download what they already own.
- Operators can tune the floor at
  `admin.musicapi.camxora.com/admin/settings` → **Integrations → Customer credit
  gate** (`Min credits to run free endpoints`, default 10; `0` disables).

## Technical impact

- `src/config.ts` — new `creditGate.minCredits` (`USER_MIN_CREDITS`, default 10,
  clamped ≥ 0).
- `src/runtimeSettings.ts` — boot-time `CREDIT_GATE_DEFAULTS` snapshot; new
  `creditGate` group in `INTEGRATION_GROUPS` (rendered automatically by the
  existing generic Integrations UI — no frontend change); `applyToConfig()`
  writes `config.creditGate.minCredits` live.
- `src/server.ts`
  - `requireFundedAccount(userId)` — `accountCredits(userId) >=
    config.creditGate.minCredits`; short-circuits true when the floor is 0.
  - `oldestActiveKey(userId)` — attributes a free, uncharged job.
  - `charge()` / `chargeUserKey()` — for `amount <= 0`, require the funded floor
    (returning an active key for attribution) instead of passing through /
    returning null.
  - `chargeRead(key, cost)` — read/detail/download variant that skips the floor
    for 0-cost.
  - `/me` generation guards tightened from `if (cost > 0 && !key)` to
    `if (!key)`; read/detail/download guards keep `cost > 0 && key === null`.
  - `/v1` `*_detail` reads (via `detailRoute`), timestamped-lyrics reads, and the
    WAV delivery routes now use `chargeRead`.
  - All 402 messages normalized to `"Insufficient credits."`.

## Files touched

- `musicapi/src/config.ts`
- `musicapi/src/runtimeSettings.ts`
- `musicapi/src/server.ts`
- `musicapi/test/credit-gate.test.ts` (new)
- `musicapi/test/run.ts`

## Migration / deploy

- No DB migration. The value lives in the existing `app_settings` table.
- Deploy the API (`--api-only` is enough; the admin UI renders the new group).

## Tests

- `npm run typecheck` (musicapi) → clean.
- `npm run test:unit` → 65/65 pass (adds `test/credit-gate.test.ts`).
- Alias audit: `sunoAlias` re-injects into the charged targets; its GETs only
  target `record-info` routes (no charge). No remaining cost-0 read routes on
  `charge`.

## Follow-ups

- Prerequisite/flow enforcement (e.g. requiring a prior owned, completed
  generation before a derivative endpoint) is out of scope — tracked separately.
- Behavioral/integration test with a fake pool (current coverage is static-source
  + config-default).
- Confirm the new admin settings field renders/saves in production.
