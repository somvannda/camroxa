# Web music credit hardening (P1)

**Date:** 2026-08-17  
**Surface:** platform_api

## Summary

Improves refund accounting integrity and removes duplicate legacy wallet updates from the v2 credit path.

## Changes

### Refund to correct pools
- Subscription debits log `{monthly, topup}` split in `credit_transactions.metadata`
- Refunds restore credits to the same pools (monthly `credits_used` reduced first, then top-up)
- Generation uses a reservation UUID linked to the Suno task id after submit for accurate callback refunds

### Idempotency
- Migration `102_credit_refund_idempotency`: unique index on `(user_id, ref_id, reason)` for refund credits

### Ledger cleanup
- Removed `credit_wallets` updates from v2 `consume_credits` and `grant_credits` (web music uses `web_subscriptions` + daily usage only)

## Files

- `platform_api/services/v2/credit_service.py`
- `platform_api/services/web_music_service.py`
- `platform_api/migrations/versions/102_credit_refund_idempotency.py`
- `platform_api/tests/test_web_music_credit_hardening.py`
