# Credit-pack purchase 500: stale NOT NULL on topup_purchases

**Date:** 2026-10-21  
**Surfaces:** platform_api, music_web

## Summary

Every credit-pack purchase on `music.camxora.com` by a user without an active
web subscription returned HTTP 500 (`An unexpected error occurred.`). Nginx
showed repeated `POST /api/v3/topups/purchase 500` responses, and
`topup_purchases` had no rows for those attempts.

Root cause: production still declared
`topup_purchases.web_subscription_id` as `NOT NULL`, while
`TopupService.purchase_topup` intentionally inserts `NULL` now that
subscriptions are retired and packs are the only product. The INSERT raised an
`asyncpg` not-null violation before any gateway call, so nothing was written and
nothing was charged.

## Product impact

**Before:** "Buy credits" failed with a generic error for every non-subscriber —
which is effectively every new buyer.

**After:** The purchase row is created and checkout proceeds to the configured
KHQR provider as designed. `web_subscription_id` is linked only for
grandfathered subscribers.

## Technical impact

- `topup_purchases.web_subscription_id` is nullable again, matching the original
  `091_topup_purchases` definition and the current service code.
- No application code changed: the code was already correct; the database had
  drifted.
- CutLuy reachability was verified separately (`/v1/payments` answers 401 as
  expected without a key), ruling out a provider outage.

## Files touched

- `platform_api/migrations/versions/146_topup_purchase_subscription_nullable.py`

## Migration/deploy

Applied to production on 2026-10-21 as a single idempotent statement:

```sql
ALTER TABLE topup_purchases
    ALTER COLUMN web_subscription_id DROP NOT NULL;
```

Verified by re-reading `information_schema.columns` (`is_nullable = YES`) and by
running the exact INSERT shape inside a transaction with `NULL`, then rolling
back.

## Tests

- Migration file compiles; revision chain `145 → 146` is linear.
- Production probe: insert with `web_subscription_id = NULL` succeeds.
- `GET /health` on the API returns 200.

## Follow-ups

- Add a purchase-path integration test that asserts a non-subscriber checkout
  reaches the gateway (would have caught this without a live DB drift).
- `camxora-platform-healthcheck` / `camxora-musicapi-healthcheck` timers on
  production fail with status 127 because
  `/opt/camxora/repo/scripts/deploy/*-healthcheck.sh` were never uploaded by the
  deploy. Those scripts exist in the repo; the deploy needs to ship them.
- `camxora-api` receives SIGTERM roughly every 10–15 minutes from an unknown
  external caller. Requests in flight during a stop lose their connection;
  identify the caller before the next payment incident.
