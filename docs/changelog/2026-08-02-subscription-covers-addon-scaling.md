# Subscription coverage must scale with profile add-ons

**Date:** 2026-08-02  
**Status:** implemented  
**Branch:** `fix/subscription-covers-addon-scaling`

## Problem

Generate for `somvannda@gmail.com` (Monthly · 2-channel + 6 add-on slots) failed with:

`Insufficient credits for this plan. Required 3243880, available 0.`

Wallet was empty (correct). Plan song quota was fine (~212/1200 scaled). The preflight path `subscription_covers_batch` used **unscaled** base plan limits (images **120**). With 111 images used + 16 jobs for the batch → `127 > 120` → treated as soft overage → tried wallet → blocked.

Quota enforcement already scaled limits via entitlements; only the “does subscription cover this?” helpers did not.

The “Required 3243880” figure was micro-units (~324.4 display credits), not a separate bug in pricing.

## Fix

- `monthly_limit_for_operation` / `subscription_covers_operation` / `subscription_covers_batch` accept `addon_slots` and use `scaled_monthly_limit`
- Callers pass `ctx.profile_addon_slots`
- Insufficient-credits reason strings use `units_to_credits(...)`

## Files

- `platform_api/services/billing_mode_service.py`
- `platform_api/services/batch_service.py`
- `platform_api/services/usage_enforcement_service.py`
- `platform_api/tests/test_billing_mode_service.py`
