# One pack lot per purchase; settlement stops throwing

**Date:** 2026-11-10
**Branch:** `fix/credit-settlement-race`
**Surfaces:** platform_api
**Status:** implemented (tests pass); not committed, not deployed

## Summary

A single top-up could mint **two or three `pack` lots** while the wallet was
credited exactly once. Production held 17 duplicate pairs across 12 buyers:
42,300 duplicated credits, 14,942.92 still live. The daily `CREDIT INVARIANTS`
alert reported it as "wallet ≠ live lots" for 8 accounts.

The same path was also throwing `UndefinedTableError: relation
"web_subscriptions" does not exist` on **every** purchase, because migration 174
dropped that table while `WalletSyncService.after_topup_fulfill` still called
`store.subtract_web_topup()`. That failure made the payment webhook report
failure, so the provider retried — which is what produced the extra concurrent
settlements in the first place. It also aborted `_sync_v3_pack` before
`apply_referral_reward()`, so referral rewards have never been paid (0 referral
credit rows in 90 days).

Separately, the migration-091 trigger `trigger_grant_topup_credits` was still
firing on every completion and crediting `credits_purchased` as *units* — 0.1
credit for a 1,000 pack — on top of the v3 grant. That residue is why some
wallets end in `.10`.

## Root cause

1. `TopupService._fulfill_topup_payment()` ran
   `UPDATE … SET payment_status='completed' WHERE payment_status='pending'`
   and **ignored whether a row was updated**, then always called
   `_sync_v3_pack()`. The webhook and the client status poll both call it.
2. `after_topup_fulfill()` checked `has_transaction_ref()` **outside** the grant
   transaction, then inserted the lot unconditionally. Losers of the grant race
   passed the check and each inserted a lot.
3. No unique constraint existed on `(user_id, ref_id)` for pack lots (only PK on
   `id`), and `insert_lot()` did not even write `ref_id`.

Production log evidence: one top-up settled three times across two uvicorn
workers, and that user has exactly three pack lots for the purchase.

## Fix

- `V3BillingStore.insert_pack_lot_if_absent()` — writes
  `ref_id = 'v3_pack:<topup_id>'` and relies on the new partial unique index;
  a losing caller receives the existing row instead of minting a second lot.
- Migration **186** — `uq_credit_wallet_lots_pack_ref` on
  `(user_id, ref_id) WHERE tag='pack' AND ref_id IS NOT NULL`; drops the
  migration-091 trigger and function. No wallet balance is moved; existing pack
  lots already have unique references or `NULL`, so the index builds cleanly.
- `TopupService._fulfill_topup_payment()` — `UPDATE … RETURNING id` is the
  settlement gate. A caller that did not flip the row does not mint. A payment
  id that does not match the row is refused (it used to grant anyway). An
  already-completed row still runs the idempotent mint so a crash between the
  status flip and the grant can heal.
- `WalletSyncService.after_topup_fulfill()` — no longer calls
  `subtract_web_topup()`; the duplicate `insert_lot` is replaced with the
  idempotent insert.
- `after_subscription_fulfill()` — no longer calls `zero_web_monthly_remaining()`
  (same dropped table).

## Files touched

- `platform_api/services/v2/topup_service.py`
- `platform_api/services/v3/store.py`
- `platform_api/services/v3/wallet_sync.py`
- `platform_api/migrations/versions/186_pack_lot_ref_unique.py`
- `platform_api/tests/test_wallet_sync.py`
- `platform_api/tests/test_pack_credit_expiry.py`
- `platform_api/tests/test_topup_chmaba_flow.py`

## Tests

- New `test_concurrent_settlement_mints_one_lot`: both callers pass the
  pre-check (the real race), result is one credit and one lot.
- New `test_fulfill_refuses_a_mismatched_payment_id`.
- New `test_fulfill_heals_an_already_settled_row`.
- Credit/billing selection: `test_credit_repo`, `test_credit_ledger`,
  `test_credit_restore_lots`, `test_credit_invariants`, `test_wallet_sync`,
  `test_pack_credit_expiry`, `test_admin_topup_parity`,
  `test_web_ledger_conversion`, `test_topup_chmaba_flow`,
  `test_v3_credits_only`, `test_free_monthly_grant_ledger`,
  `test_credits_cutover_snapshot` — **111 passed**.

## Follow-ups (not in this change)

- Refund the 2 unrefunded web-music charges (`sommakara84`, `pengchun.pc`).
- Remove `if pro: return` from `_refund_web_music_generation_on_failure`;
  make the reconcile sweep cover `source='web_music'` (no song/batch id today).
- Correct the refund audits: `reason ILIKE '%refund%'` hides
  `suno_generation_failed` / `image_generation_*`, and the song-id join matches a
  successful retry to an earlier failed task.
- `_restore_lots` picks one lot with `LIMIT 1` and mints a non-expiring `grant`
  lot when it is full (102 such lots, 60 on one account). Walk lots with room and
  stamp a 30-day expiry on any overflow lot.
- Data repair before 2026-12-01: delete the duplicate pack lots; stamp/merge the
  non-expiring refund grant lots. Dry-run first.
- Delete the remaining `web_subscriptions` code (`web_ledger_conversion`,
  `list_active_web_subscribers`, `zero_web_*`) — it can only raise now.
