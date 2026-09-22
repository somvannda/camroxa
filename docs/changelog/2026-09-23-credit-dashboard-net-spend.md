# Credits dashboard — net refunds out of spend totals

**Date:** 2026-09-23
**Branch:** `fix/credit-audit-reporting-and-refund-idempotency`
**Surfaces:** platform_api, user_portal
**Status:** implemented; sandbox deploy

## Summary

A production credit audit (`somvannda@gmail.com`) showed the user portal and desktop
dashboard reporting **gross** lifetime debits as "Credits spent" and deriving
"Credits total" from `spent + remaining`. Because failed/deferred operations are
refunded, both figures were inflated:

| Figure | Before | After |
|---|---:|---:|
| Credits spent | 285.1126 | 129.5558 |
| Credits remaining | 1970.4442 | 1970.4442 |
| Credits total | 2255.5568 | 2100.0000 |

The wallet balance itself was always correct; only the derived dashboard figures were
wrong.

## Change

- `platform_api/routers/stats.py` — `/stats/dashboard` now computes net wallet spend:
  debits minus `direction='refund'` minus legacy `direction='credit'` rows with
  `reason LIKE 'refunded_%'`, clamped at 0. `credits_total` stays `spent + remaining`
  but now reconciles to credits actually granted.
- `user_portal/src/app/dashboard/credits/credits-panel.tsx` — caption no longer claims
  "Wallet balance only"; states refunds are netted out of spend.

## Not included (follow-up)

Refund idempotency was audited but not changed here. Image-job retries legitimately
charge and refund once per attempt (`charge()` is idempotent on
`(user_id, reason, ref_id)`, but the image path passes no `ref_id`, and
`credit_repo.refund()` has no dedupe). A unique index on `(user_id, ref_id, reason)`
for `direction='refund'` would reject valid retry refunds and fail to build on
existing duplicate rows. The correct fix is a per-charge id threaded from
`charge()` → `OperationHold` → refund, plus an `idempotency_key` column and partial
unique index — a separate billing-core task.

## Tests

- `platform_api/tests/test_stats_router.py` — net-spend query shape and totals.
- `platform_api/tests/test_credit_repo.py` — unaffected, still green.
- Full run: 36 passed (stats + credit_repo).
