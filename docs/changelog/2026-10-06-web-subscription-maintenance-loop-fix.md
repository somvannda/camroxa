# Web-subscription maintenance loop was silently crashing — 2026-10-06

**Surfaces:** `platform_api/` (startup maintenance + v2 SubscriptionService).

## Why

The 15-minute web-subscription maintenance loop never actually ran in production:

- `main.py` started it with `SubscriptionService(db_pool)` using the **raw asyncpg
  pool**.
- `SubscriptionService` talks to `self._db.fetch_one()` / `fetch_all()`, which only
  exist on `AsyncpgPoolAdapter` (`db/asyncpg_adapter.py`). The router dependency
  already passed `wrap_pool(get_db_pool())`; the startup loop did not.
- Confirmed live on production:
  `process_due_subscriptions RAISED: AttributeError: 'Pool' object has no attribute 'fetch_all'`.

Consequences:
- The loop's `except Exception` swallowed the error every 15 minutes — so the
  **stop-free-auto-renewal hotfix (PR #353) was inert**: it is called by this loop.
- Ended subscriptions stayed `status='active'` with `current_period_end` in the
  past, and those stale rows **block re-subscription** (`create_subscription()`
  guards on the latest row's `status == 'active'` regardless of the period).

## What changed

- `platform_api/services/v2/subscription_service.py` — `SubscriptionService.__init__`
  now wraps a raw pool with `wrap_pool` when it lacks `fetch_all`, so no caller can
  reintroduce the mismatch. Adapters are left untouched.
- `platform_api/main.py` — the maintenance loop now passes
  `wrap_pool(db_pool)` explicitly.

## Verification

- New `test_subscription_service_wraps_raw_pool` and
  `test_subscription_service_keeps_existing_adapter`.
- Focused suite (`test_web_music_subscription_credit_reset`,
  `test_web_music_owned_checkout`): 26 passed.
- Production diagnostic reproduced the `AttributeError` before the fix.

## Follow-ups

- Once deployed, the loop expires stale `active` rows at their ended period, which
  also unblocks those users' next purchase. A one-off sweep may be run for
  immediacy.
- Build the web renewal flow (option C): KHQR checkout before expiry, extend only
  on a verified payment, `renewal_alert` + reminder banner/email.
