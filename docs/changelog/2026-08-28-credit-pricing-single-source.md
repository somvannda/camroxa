# 2026-08-28 — Credits page is the only generate charge rate

Sandbox only until production is requested.

## Summary

Generate quote/charge always uses Admin **Credits** (`credit_pricing`). Plan `music_credits` / `lyric_credits` / … no longer set the price. Plans still grant monthly/daily credits and store pricing-card copy. Song hints already count two songs per generate (PR #119); they now follow the Credits-page music list price instead of a hardcoded 10 when that rate is not 10.

## Product impact

- Changing music / lyric / style on `/credits` changes what every plan is charged.
- Admin `/plans` no longer has per-op cost fields. Edit costs on Credits.
- Public `≈ songs` follows the current music list price (`floor(grant / music cost) × 2`).
- Setting an op to 0 on a plan no longer makes that op free. To include an op, set it to 0 on the Credits page.

## Technical impact

- `CreditsOnlyBillingService.quote()` ignores plan op columns. `source` is `credit_pricing` (or `waive`).
- New `platform_api/services/v3/list_prices.py` resolves named provider fallbacks, then scans `get_all_pricing()` by operation alias.
- Public `/api/v1/plans/public`, `/api/v3/plans/public`, and `/api/v2/subscriptions/plans` expose `credits_per_generate` from the music list price.
- Plan grants (`monthly_credits` / `daily_credits`) are unchanged.

## Files touched

- `platform_api/services/v3/list_prices.py`
- `platform_api/services/v3/credits_only_billing_service.py`
- `platform_api/routers/v3_billing.py`, `plans.py`, `v2_subscriptions.py`
- `platform_api/tests/test_v3_credits_only.py`
- `admin_portal/src/pages/plans/credits-only-plan-fields.tsx`
- `admin_portal/src/pages/plans/credits-only-section.tsx`
- `admin_portal/src/pages/plans/index.tsx`

## Migration/deploy

```
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/sync_admin_portal_sandbox.py
```

No new Alembic revision.

## Tests

- `platform_api/tests/test_v3_credits_only.py`

## Follow-ups

- Production after the user asks.
