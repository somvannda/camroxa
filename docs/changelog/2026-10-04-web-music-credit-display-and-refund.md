# Web music: frozen credit card and failed-generation refunds

**Date:** 2026-10-04
**Branch:** `fix/web-music-credit-display-and-refund`
**Surfaces:** music_web, platform_api
**Status:** implemented (not deployed)

## Summary

Two bugs made `music.camxora.com` Create look like it never spent credits:

1. **The balance card froze at the plan's monthly pool.** For a free user the
   sidebar/header showed `remaining = grant_remaining`, which `splitCreditBalance`
   clamps to the Free plan's monthly allowance (50). A wallet holding more than
   that (stacked grants, top-ups) kept showing **"50 / 50 credits · 50 left"**
   while credits were really being debited, so spend appeared to do nothing.
2. **Failed generations were charged but not refunded.** The v3 charge is held in
   the API process's in-memory `_open_charges` map. The Suno submit + failure run
   in the **worker process**, which built a fresh `WebMusicService` with an empty
   map, so `_release_daily_slot` found no charge and silently no-oped — even
   though the DB error says "Credits were refunded."

## Product impact

- The account credit card now reports the real spendable wallet. Spending moves
  the number down (and the top-up portion is labelled) instead of staying pinned
  to the free allowance.
- A song that fails to start at Suno is now actually refunded, once, even across
  worker retries and process restarts. The existing "Credits were refunded"
  message becomes true.

## Technical impact

- `music_web/src/lib/credit-display.ts`: moved the header math into a pure
  `computeCreditDisplay()` (new `CreditDisplayInput`/`CreditDisplay` types), unit
  tested. The non-subscription case now uses the authoritative `total_credits`
  for `remaining` and a capacity of `max(planAllowance, remaining, 1)` so it can
  never freeze; extra credits are surfaced via the top-up promo. `credit-header.tsx`
  imports it instead of defining it locally.
- `music_web/src/components/credit-balance-card.tsx`: the free branch reads the
  wallet total (daily or monthly Free grant) rather than only `daily_free_*`.
- `platform_api/repositories/credit_repo.py`: new `refund_once()` — refunds at
  most once per `(user_id, reason, ref_id)`. It locks the wallet row first, so
  concurrent refunds for the same reference serialize and the loser no-ops.
- `platform_api/services/v3/credits_only_billing_service.py`: when `ref_id` is
  present, `refund()` uses `refund_once()` (falls back to `refund()` for repos
  without it).
- `platform_api/services/web_music_service.py`: `_release_daily_slot()` accepts a
  `task_id` and, when the in-memory charge is missing, reverses the recorded
  `v3_music` debit by `ref_id` (reservation id and/or task id) via a refund-only
  `CreditsOnlyBillingService` (no Redis/enforcement dependency in the worker).
  `fulfill_queued_generate()` passes the task id.
- Refund idempotency is keyed on the **debit row id**, so a job's retried submits
  cannot credit the user more than once.

## Files touched

- `music_web/src/lib/credit-display.ts`
- `music_web/src/lib/credit-display.test.ts`
- `music_web/src/components/credit-header.tsx`
- `music_web/src/components/credit-balance-card.tsx`
- `platform_api/repositories/credit_repo.py`
- `platform_api/services/v3/credits_only_billing_service.py`
- `platform_api/services/web_music_service.py`
- `platform_api/tests/test_credit_repo.py`
- `platform_api/tests/test_web_music_v3_charge.py`
- `platform_api/tests/test_web_music_generate_queue.py`

## Migration / deploy

- No schema migration, no settings change. Deploy `platform_api` (restart
  `camxora-api` **and** the worker) and rebuild `music_web`. Sandbox first;
  production only on explicit request.

## Tests

- `platform_api`: `test_credit_repo.py` (`refund_once` first/second/distinct/no-ref/
  zero), `test_web_music_v3_charge.py` (durable refund by reference, both ids,
  no debit), `test_web_music_generate_queue.py` (worker passes the task id).
  Full run of the touched suites + `test_v3_credits_only.py` / `test_web_music_router.py`:
  **83 passed**.
- `music_web`: `node --experimental-strip-types --test "src/lib/*.test.ts"` —
  **42 passed**, including the new `computeCreditDisplay` cases reproducing the
  frozen-card regression.
