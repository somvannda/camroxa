# Web music credit system hardening (P0)

**Date:** 2026-08-17  
**Surface:** platform_api

## Summary

Implements P0 credit security and correctness fixes: async Suno failure refunds, subscription period enforcement, background expiry maintenance, and removal of public credit consume API.

## Changes

### Refunds
- Suno callback `FAILED` for `web_music` tasks refunds 10 credits (skips desktop Pro)
- Idempotent refunds via `reference_id` (task id) — duplicate callbacks safe

### Subscription period enforcement
- `consume_credits()` and `get_detailed_balance()` refresh subscription state and require `current_period_end > NOW()`
- Background loop every 15 minutes runs `process_due_subscriptions()` (expire or reset monthly quota)
- Download access no longer uses stale `balance.has_subscription` fallback

### Security
- Removed public `POST /v2/credits/consume` endpoint (service-internal only)

## Files

- `platform_api/services/v2/credit_service.py`
- `platform_api/services/v2/subscription_service.py`
- `platform_api/routers/callbacks.py`
- `platform_api/routers/v2_credits.py`
- `platform_api/services/web_music_service.py`
- `platform_api/main.py`
- `platform_api/tests/test_web_music_credit_hardening.py`

## Remaining (P1)

- Refund subscriber credits back to monthly pool (not top-up)
- Unique DB index on refund transactions
- Stop parallel `credit_wallets` updates from v2 paths
