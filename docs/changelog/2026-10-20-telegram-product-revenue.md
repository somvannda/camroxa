# Ops Telegram: proven product attribution and cross-product revenue

**Branch:** `feat/telegram-product-revenue`
**Stacked on:** `perf/telegram-reporting` (PR #413)
**Date:** 2026-10-20

## Why

The burn report could only prove web music from `ref_id → suno_tasks`; image,
lyric, title, album and style charges used by both products stayed in a
`shared` bucket. Revenue in the 22:00 digest covered platform
`billing_payments` only, which has no fulfilled rows, while the real money
(ChmabaPay credit packs) lives in the musicapi database.

## Changes

### Charge-time product tag

- `CreditsOnlyBillingService.charge()` / `refund()` accept `product` and write
  it to `credit_transactions.metadata["product"]`.
- Web music (`WebMusicChargeBridge`) tags `product="web_music"` on charge and
  refund.
- The v1/desktop charge path (`UsageEnforcementService._charge_via_v3`) tags
  `product="desktop"`, or `"web_music"` for `web_music_*` operation names.
- `_BURN_SQL` now prefers `metadata->>'product'`, then falls back to the older
  signals: `ref_id → suno_tasks` (web), `v3_music` (studio), otherwise shared.
  Historical rows keep reporting exactly as before.

### Optional musicapi revenue

- New `PLATFORM_MUSICAPI_DATABASE_URL` (read-only DSN, default empty).
- `fetch_musicapi_revenue()` reads `payment_transactions` where
  `status='paid'`, grouped by currency, for today and the last 7 days.
- The daily digest line becomes:
  `revenue today: platform $0.00 (7d $0.00) · musicapi KHR 12,000 (7d 40,000)`.
- Unset or unreachable DSN degrades to platform-only; the report never fails
  because of a cross-product read.
- Deploy plumbing: `.deploy/secrets*.env.example`, `deploy_production.py`,
  production and sandbox remote `.env` writers.

## No migration

Product tagging uses the existing `credit_transactions.metadata` JSONB column,
and revenue only reads the musicapi `payment_transactions` table.

## Tests

```
python -m pytest platform_api/tests/test_telegram_ops_alert_service.py \
  platform_api/tests/test_v3_credits_only.py \
  platform_api/tests/test_web_music_v3_charge.py \
  platform_api/tests/test_v3_generate_charge.py -q
# 66 passed
```

## Rollout

1. Set `PLATFORM_MUSICAPI_DATABASE_URL` in `.deploy/secrets.production.env`
   (read-only user recommended) if musicapi revenue should appear.
2. Deploy; no `alembic upgrade` needed for this change.
3. Verify new tags after the first generation:
   ```sql
   SELECT metadata->>'product', count(*)
   FROM credit_transactions
   WHERE reason LIKE 'v3_%' AND created_at > now() - interval '1 day'
   GROUP BY 1;
   ```
   Expect `web_music` for web generations and `desktop` for desktop/API.
4. The 22:00 digest should show the product split and the musicapi currency
   totals once the DSN is configured.
