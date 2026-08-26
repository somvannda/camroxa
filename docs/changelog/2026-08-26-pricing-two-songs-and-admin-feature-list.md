# 2026-08-26 — Pricing song counts ×2 + admin-managed feature lists

Sandbox only. Production not touched.

## Summary

Pricing cards treated 10 credits as 1 song. One generate spends 10 credits and returns **two** songs, so Free 50/day is 10 songs, Starter 1,000 is 200, Creator 3,500 is 700, and Studio 8,000 is 1,600. Feature bullets (Web Create, Desktop studio, …) were hardcoded. Admin Plans now has a textarea per plan; those lines render on `/pricing`.

## Product impact

- Free card shows ≈ 10 songs/day.
- Paid cards show ×2 song hints.
- Admins edit each plan’s bullet list line-by-line. Empty textarea falls back to the current Free/paid defaults.
- Credit-block captions under the big number (`daily credits`, `≈ 10 songs/day`, `Resets at midnight`) are also admin-editable. Empty captions follow daily/monthly credits, so Free with 0 daily credits no longer shows midnight.

## Technical impact

- New `plans.pricing_features TEXT[]` (migration `118`) and `plans.pricing_credit_lines TEXT[]` (migration `119`).
- Public `/plans/public` and `/subscriptions/plans` return stored feature and credit-caption lines, or computed fallbacks.
- Admin v3 plan patch accepts `pricing_features` and `pricing_credit_lines`.
- Display math is `floor(credits / 10) * 2`.

## Files touched

- `platform_api/services/pricing_display.py`
- `platform_api/migrations/versions/118_plan_pricing_features.py`
- `platform_api/migrations/versions/119_plan_pricing_credit_lines.py`
- `platform_api/services/v3/store.py`, `ops.py`, `routers/v3_billing.py`
- `platform_api/routers/plans.py`, `v2_subscriptions.py`, `v2_topups.py`
- `admin_portal/src/pages/plans/credits-only-plan-fields.tsx`
- `website/src/app/pricing/pricing-cards.tsx`
- `music_web/src/components/pricing-page-client.tsx`

## Migration/deploy

```
python scripts/deploy/sync_platform_api_sandbox.py
python scripts/deploy/run_alembic_upgrade_sandbox.py
python scripts/deploy/sync_admin_portal_sandbox.py
python scripts/deploy/rebuild_music_web_sandbox.py
```

Then rebuild website/user-portal pricing sources on sandbox.

## Tests

- `platform_api/tests/test_pricing_display.py`
- `camxora_python/tests/test_upgrade_plans_dialog.py`

## Follow-ups

- Production after the user asks.
