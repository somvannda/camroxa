# Credits-only public cards and unpublished dual-profile packs

**Date:** 2026-08-22  
**Surfaces:** website, user_portal, music_web, platform_api  
**Flag:** `credits_only_v3_charge` stays Off. No leftover mint. Production not touched.

## Item 15

Public pricing advertises only Starter / Creator / Studio (`is_active AND is_public`).

- Dual-channel desktop is a bullet on every card, not the plan name.
- Prices stay $10 / $30 / $60 with 1,000 / 3,500 / 8,000 credits.
- Song hint is `floor(monthly_credits / 10)` (never x2).
- Hidden $79 (`7900` cents) is filtered even if it leaked.
- Free card renders only when a public Free row exists.
- Website quota comparison table and public channel-addon table are unmounted.
- User-portal onboarding uses the same three cards (monthly / yearly checkout).
- music_web `/pricing`, pricing modal, and available-plans grid match.

## Item 16

$5 / $10 dual-profile packs stay unpublished checkout SKUs.

- No new Stripe products.
- `GET /api/v1/plans/public/profile-addon-quote` returns 404 unless the addon row is public.
- Fulfillment still only adds pending profile slots (no credit mint).
- Monthly song meters no longer scale with `profile_addon_slots`.

## Not in this change

Charge flip, leftover conversion apply, production catalog copy, desktop item 14, admin credits-only UI.
