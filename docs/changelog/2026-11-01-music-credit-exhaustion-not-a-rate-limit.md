# Music provider credit stop must not park the whole key pool

**Date:** 2026-11-01
**Branch:** `fix/music-credit-exhaustion`
**Surfaces:** platform_api

## Summary

On 2026-11-01 the reseller account behind `musicapi.camxora.com` ran out of
credits. That single billing condition took the whole music pipeline down for
about an hour and produced 19 automatic refunds:

1. `musicapi` answers `402 Insufficient credits.` and remaps it to **429** on the
   public `/api/v1/*` surface (`musicapi/src/server.ts:717-722`).
2. platform_api saw `429` in `execute_with_failover` and called
   `_handle_rate_limited`, marking **every** key `rate_limited` and retrying the
   next one — the pool was emptied inside one request.
3. `active_suno_key_values()` (the Suno submit path) selects `status='active'`
   straight from the database and never runs the pool's cooldown recovery, so
   the keys stayed dead after their 60 s cooldown and every submission failed
   with `No active Suno API key configured.` → 5 retries per song → refund.

## Changes

**`platform_api/services/key_pool_service.py`**

- `is_billing_exhausted_response()` recognises credit-exhaustion bodies.
- A `429` whose body says the account is out of credits now raises
  `ExternalServiceError(reason="provider_credits_exhausted")` immediately:
  no key is marked, the remaining attempts are not burned, and an ops alert is
  posted. Rate limits that really are throttling behave exactly as before.

**`platform_api/services/suno_audio_resolver.py`**

- `_keys_outside_cooldown()` is applied in `active_suno_key_values()`: keys are
  read with `status IN ('active','rate_limited')`, keys still inside their Redis
  cooldown are skipped, and expired ones are flipped back to `active`.
  A 60 s cooldown is now a 60 s cooldown instead of a permanent outage.

## Product impact

- A zero balance fails fast with "Provider is out of credits" instead of
  poisoning the pool for every later request.
- Keys recover on their own; nobody has to reset `api_key_entries` by hand.
- Credits, refunds and billing behaviour are unchanged.

## Files touched

- `platform_api/services/key_pool_service.py`
- `platform_api/services/suno_audio_resolver.py`
- `platform_api/tests/test_key_pool_service.py`
- `platform_api/tests/test_suno_audio_resolver.py`

## Verification

```
python -m pytest platform_api/tests/test_key_pool_service.py \
  platform_api/tests/test_key_pool_router.py \
  platform_api/tests/test_suno_audio_resolver.py \
  platform_api/tests/test_soft_overage_hold.py -q
# 135 passed
```

## Deploy

platform_api only; no migration. Follow-up (separate musicapi branch): tag the
402→429 remap with `x-credit-exhausted` and alert on low credits before zero.
